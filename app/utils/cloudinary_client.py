import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

from app.config import CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, CLOUDINARY_CLOUD_NAME

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
)


async def upload_image(file: UploadFile) -> dict:
    contents = await file.read()
    result = cloudinary.uploader.upload(contents, folder="brainrot/notes", resource_type="image")
    return {"url": result["secure_url"], "public_id": result["public_id"]}


def delete_image(public_id: str) -> None:
    try:
        cloudinary.uploader.destroy(public_id)
    except Exception:
        pass
