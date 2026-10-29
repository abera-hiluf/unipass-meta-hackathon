from __future__ import annotations

from pathlib import Path
import os
import tempfile
from typing import Protocol

from app.core.config import settings


class StorageError(RuntimeError):
    """Raised when a private object cannot be stored or removed."""


class PrivateObjectStorage(Protocol):
    def put_object(self, object_key: str, content: bytes, content_type: str) -> None: ...

    def delete_object(self, object_key: str) -> None: ...


class LocalPrivateObjectStorage:
    """Local-only private storage for development; never exposes public URLs."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def _safe_path(self, object_key: str) -> Path:
        path = (self.root / object_key).resolve()
        if path != self.root and self.root not in path.parents:
            raise StorageError("Invalid storage object key")
        return path

    def put_object(self, object_key: str, content: bytes, content_type: str) -> None:
        target = self._safe_path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".upload-", delete=False) as temporary:
                temporary.write(content)
                temporary_path = temporary.name
            os.replace(temporary_path, target)
        except OSError as exc:
            if temporary_path:
                try:
                    os.unlink(temporary_path)
                except OSError:
                    pass
            raise StorageError("Private object storage failed") from exc

    def delete_object(self, object_key: str) -> None:
        target = self._safe_path(object_key)
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError("Private object cleanup failed") from exc


def get_storage() -> PrivateObjectStorage:
    if settings.document_storage_provider.lower() == "local":
        return LocalPrivateObjectStorage(settings.document_storage_path)
    raise StorageError("Document storage provider is not configured")
