from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class NoteCategory(str, Enum):
    GENIUS   = "genius"
    YAPS     = "yaps"
    HIGH_ROT = "high-rot"
    SERIOUS  = "serious"
    REMINDER = "reminder"
    GENERAL  = "general"


class NoteImage(BaseModel):
    url: str
    caption: Optional[str] = None


class RemoveImageRequest(BaseModel):
    image_url: str


class UpdateImageCaptionRequest(BaseModel):
    image_url: str
    caption: Optional[str] = None


class NoteResponse(BaseModel):
    id: str
    title: str
    category: str
    content: str
    tags: list[str]
    images: list[NoteImage]
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
