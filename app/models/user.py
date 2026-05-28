from typing import Optional

from pydantic import BaseModel, EmailStr


class UserInDB(BaseModel):
    full_name: str
    email: EmailStr
    hashed_password: Optional[str] = None
    github_id: Optional[str] = None
