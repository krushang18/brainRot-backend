from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserInDB(BaseModel):
    full_name: str

    email: EmailStr
    hashed_password: Optional[str] = None

    auth_provider: str = "local"
    
    github_id: Optional[str] = None
    google_id: Optional[str] = None

    trusted_devices: list = []

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
