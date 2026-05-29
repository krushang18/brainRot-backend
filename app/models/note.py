from datetime import datetime

from pydantic import BaseModel


class NoteInDB(BaseModel):
    user_id: str
    title: str
    category: str
    content: str
    tags: list[str] = []
    image_urls: list[str] = []
    image_public_ids: list[str] = []   # internal; never sent to frontend
    is_favorite: bool = False
    created_at: datetime
    updated_at: datetime
