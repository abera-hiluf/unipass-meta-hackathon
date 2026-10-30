from __future__ import annotations

from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.services.storage import StorageError


def validate_document_content(content: bytes, extension: str) -> None:
    """Validate readability and basic dimensions without retaining image bytes."""
    if extension == ".pdf":
        if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-1024:]:
            raise StorageError("Document is not a readable PDF")
        return

    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            width, height = image.size
            if width < 100 or height < 100 or width > 10000 or height > 10000:
                raise StorageError("Document image dimensions are unsupported")
            image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise StorageError("Document image is corrupt or unreadable") from exc
