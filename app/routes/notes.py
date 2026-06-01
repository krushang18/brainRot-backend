import asyncio
import json
from datetime import datetime, timezone
from itertools import zip_longest
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.config import MAX_NOTE_IMAGES
from app.database import get_db
from app.models.note import NoteImageInDB, NoteInDB
from app.schemas.note_schema import (
    NoteCategory,
    NoteImage,
    NoteListResponse,
    NoteResponse,
    NoteSearchResponse,
    RemoveImageRequest,
    UpdateImageCaptionRequest,
)
from app.utils.cloudinary_client import delete_image, upload_image
from app.utils.dependencies import get_current_user

router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────

def _serialize(doc: dict) -> NoteResponse:
    return NoteResponse(
        id=str(doc["_id"]),
        title=doc["title"],
        category=doc["category"],
        content=doc["content"],
        tags=doc.get("tags", []),
        images=[
            NoteImage(url=i["url"], caption=i.get("caption"))
            for i in doc.get("images", [])
        ],
        is_favorite=doc.get("is_favorite", False),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def _to_oid(note_id: str) -> ObjectId:
    try:
        return ObjectId(note_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid note id")


def _parse_json_list(raw: Optional[str], field: str) -> list:
    if not raw or raw.strip() in ("[]", ""):
        return []
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise HTTPException(status_code=400, detail=f"{field} must be a JSON array")
        return parsed
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail=f"{field} must be a JSON array")


def _validate_image(img: UploadFile) -> None:
    if not img.content_type:
        raise HTTPException(
            status_code=400,
            detail=f"Could not detect file type for '{img.filename}'. Please upload a valid image file (JPEG, PNG, WebP, GIF).",
        )
    if not img.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=f"'{img.filename}' is not an image (received '{img.content_type}'). Only image files are allowed (JPEG, PNG, WebP, GIF).",
        )


async def _get_own_note(note_id: str, user_id: str, db) -> dict:
    doc = await db["notes"].find_one({"_id": _to_oid(note_id), "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Note not found")
    return doc


async def _upload_images(
    files: list[UploadFile],
    captions: list,
) -> list[NoteImageInDB]:
    result = []
    for img, caption in zip_longest(files, captions):
        _validate_image(img)
        uploaded = await upload_image(img)
        result.append(NoteImageInDB(
            url=uploaded["url"],
            public_id=uploaded["public_id"],
            caption=caption if isinstance(caption, str) and caption.strip() else None,
        ))
    return result


# ── List ───────────────────────────────────────────────────────────────────

@router.get("/", response_model=NoteListResponse)
async def list_notes(
    limit: int = Query(default=15, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    tag: Optional[str] = Query(default=None),
    is_favorite: Optional[bool] = Query(default=None),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    query: dict = {"user_id": str(current_user["_id"])}
    if cursor:
        try:
            query["_id"] = {"$lt": ObjectId(cursor)}
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cursor")
    if category is not None:
        query["category"] = category
    if tag is not None:
        query["tags"] = tag
    if is_favorite is not None:
        query["is_favorite"] = is_favorite

    docs = await db["notes"].find(query).sort("_id", -1).limit(limit + 1).to_list(limit + 1)
    has_more = len(docs) > limit
    notes = docs[:limit]
    return NoteListResponse(
        notes=[_serialize(n) for n in notes],
        has_more=has_more,
        next_cursor=str(notes[-1]["_id"]) if has_more else None,
    )


# ── Create ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    title: str = Form(...),
    category: NoteCategory = Form(...),
    content: str = Form(""),
    tags: str = Form("[]"),
    is_favorite: bool = Form(False),
    images: list[UploadFile] = File(default=[]),
    captions: str = Form("[]"),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    if len(images) > MAX_NOTE_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot attach more than {MAX_NOTE_IMAGES} images per note.",
        )

    caption_list = _parse_json_list(captions, "captions")
    image_docs = await _upload_images(images, caption_list)

    now = datetime.now(timezone.utc)
    note_doc = NoteInDB(
        user_id=str(current_user["_id"]),
        title=title,
        category=category.value,
        content=content,
        tags=_parse_json_list(tags, "tags"),
        images=image_docs,
        is_favorite=is_favorite,
        created_at=now,
        updated_at=now,
    )
    result = await db["notes"].insert_one(note_doc.model_dump())
    created = await db["notes"].find_one({"_id": result.inserted_id})
    return _serialize(created)


# ── Search ─────────────────────────────────────────────────────────────────

@router.get("/search", response_model=NoteSearchResponse)
async def search_notes(
    q: str = Query(..., min_length=2, description="Full-text search query"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=15, ge=1, le=100),
    category: Optional[str] = Query(default=None),
    tag: Optional[str] = Query(default=None),
    is_favorite: Optional[bool] = Query(default=None),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    query: dict = {
        "user_id": str(current_user["_id"]),
        "$text": {"$search": q},
    }
    if category is not None:
        query["category"] = category
    if tag is not None:
        query["tags"] = tag
    if is_favorite is not None:
        query["is_favorite"] = is_favorite

    projection = {"score": {"$meta": "textScore"}}
    total, docs = await asyncio.gather(
        db["notes"].count_documents(query),
        db["notes"]
        .find(query, projection)
        .sort([("score", {"$meta": "textScore"})])
        .skip((page - 1) * limit)
        .limit(limit)
        .to_list(limit),
    )
    return NoteSearchResponse(
        notes=[_serialize(d) for d in docs],
        total=total,
        page=page,
        limit=limit,
        has_more=(page * limit) < total,
    )


# ── Read ───────────────────────────────────────────────────────────────────

@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    return _serialize(await _get_own_note(note_id, str(current_user["_id"]), db))


# ── Update ─────────────────────────────────────────────────────────────────

@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: str,
    title: Optional[str] = Form(None),
    category: Optional[NoteCategory] = Form(None),
    content: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    is_favorite: Optional[bool] = Form(None),
    images: list[UploadFile] = File(default=[]),
    captions: str = Form("[]"),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    oid = _to_oid(note_id)
    existing = await _get_own_note(note_id, str(current_user["_id"]), db)

    updates: dict = {}
    if title is not None:
        updates["title"] = title
    if category is not None:
        updates["category"] = category.value
    if content is not None:
        updates["content"] = content
    if tags is not None:
        updates["tags"] = _parse_json_list(tags, "tags")
    if is_favorite is not None:
        updates["is_favorite"] = is_favorite

    if images:
        current_count = len(existing.get("images", []))
        if current_count + len(images) > MAX_NOTE_IMAGES:
            raise HTTPException(
                status_code=400,
                detail=f"This note already has {current_count} image(s). Adding {len(images)} more would exceed the {MAX_NOTE_IMAGES}-image limit.",
            )
        caption_list = _parse_json_list(captions, "captions")
        new_image_docs = await _upload_images(images, caption_list)
        await db["notes"].update_one(
            {"_id": oid},
            {"$push": {"images": {"$each": [img.model_dump() for img in new_image_docs]}}},
        )

    if not updates and not images:
        return _serialize(existing)

    updates["updated_at"] = datetime.now(timezone.utc)
    await db["notes"].update_one({"_id": oid}, {"$set": updates})
    return _serialize(await db["notes"].find_one({"_id": oid}))


# ── Delete note ────────────────────────────────────────────────────────────

@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    doc = await db["notes"].find_one_and_delete(
        {"_id": _to_oid(note_id), "user_id": str(current_user["_id"])}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Note not found")
    for img in doc.get("images", []):
        delete_image(img["public_id"])


# ── Image sub-resource ─────────────────────────────────────────────────────

@router.post("/{note_id}/images", response_model=NoteResponse)
async def add_images(
    note_id: str,
    images: list[UploadFile] = File(...),
    captions: str = Form("[]"),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    oid = _to_oid(note_id)
    existing = await _get_own_note(note_id, str(current_user["_id"]), db)

    current_count = len(existing.get("images", []))
    if current_count + len(images) > MAX_NOTE_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"This note already has {current_count} image(s). Adding {len(images)} more would exceed the {MAX_NOTE_IMAGES}-image limit.",
        )

    caption_list = _parse_json_list(captions, "captions")
    new_image_docs = await _upload_images(images, caption_list)

    await db["notes"].update_one(
        {"_id": oid},
        {
            "$push": {"images": {"$each": [img.model_dump() for img in new_image_docs]}},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
    return _serialize(await db["notes"].find_one({"_id": oid}))


@router.patch("/{note_id}/images", response_model=NoteResponse)
async def update_image_caption(
    note_id: str,
    body: UpdateImageCaptionRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    oid = _to_oid(note_id)
    existing = await _get_own_note(note_id, str(current_user["_id"]), db)

    if not any(i["url"] == body.image_url for i in existing.get("images", [])):
        raise HTTPException(status_code=404, detail="Image URL not found on this note.")

    await db["notes"].update_one(
        {"_id": oid, "images.url": body.image_url},
        {"$set": {"images.$.caption": body.caption, "updated_at": datetime.now(timezone.utc)}},
    )
    return _serialize(await db["notes"].find_one({"_id": oid}))


@router.delete("/{note_id}/images", response_model=NoteResponse)
async def remove_image(
    note_id: str,
    body: RemoveImageRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    oid = _to_oid(note_id)
    existing = await _get_own_note(note_id, str(current_user["_id"]), db)

    img_to_delete = next(
        (i for i in existing.get("images", []) if i["url"] == body.image_url), None
    )
    if not img_to_delete:
        raise HTTPException(status_code=404, detail="Image URL not found on this note.")

    delete_image(img_to_delete["public_id"])

    await db["notes"].update_one(
        {"_id": oid},
        {
            "$pull": {"images": {"url": body.image_url}},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
    return _serialize(await db["notes"].find_one({"_id": oid}))
