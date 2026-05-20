from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.schemas.token_schema import TokenResponse
from app.schemas.user_schema import SignupRequest, UserInDB
from app.utils.jwt import create_access_token, create_refresh_token
from app.utils.security import hash_password

router = APIRouter()


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(user: SignupRequest, db=Depends(get_db)):
    if user.password != user.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    existing = await db["users"].find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user_doc = UserInDB(
        full_name=user.full_name,
        email=user.email,
        hashed_password=hash_password(user.password),
    )
    result = await db["users"].insert_one(user_doc.model_dump())

    user_id = str(result.inserted_id)
    return TokenResponse(
        access_token=create_access_token(user_id, user.email),
        refresh_token=create_refresh_token(user_id),
    )
