from datetime import datetime
import uuid

from pydantic import BaseModel


class IdentityDocumentResponse(BaseModel):
    id: uuid.UUID
    document_type: str
    status: str
    reason_code: str | None
    created_at: datetime
    updated_at: datetime
