from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NoteCategory(str, Enum):
    GENIUS   = "genius"
    YAPS     = "yaps"
    HIGH_ROT = "high-rot"
    SERIOUS  = "serious"
    REMINDER = "reminder"
    GENERAL  = "general"


class RemoveImageRequest(BaseModel):
    image_url: str


class NoteResponse(BaseModel):
    id: str
    title: str
    category: str
    content: str
    tags: list[str]
    image_urls: list[str]
    is_favorite: bool
    created_at: datetime
    updated_at: datetime


class NoteListResponse(BaseModel):
    notes: list[NoteResponse]
    has_more: bool
    next_cursor: Optional[str]


class NoteSearchResponse(BaseModel):
    notes: list[NoteResponse]
    total: int
    page: int
    limit: int
    has_more: bool
