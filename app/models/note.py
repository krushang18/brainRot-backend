from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NoteImageInDB(BaseModel):
    url: str
    public_id: str
    caption: Optional[str] = None


class NoteInDB(BaseModel):
    user_id: str
    title: str
    category: str
    content: str
    tags: list[str] = []
    images: list[NoteImageInDB] = []
    is_favorite: bool = False
    created_at: datetime
    updated_at: datetime
