import secrets
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.config import RESET_TOKEN_EXPIRE_MINUTES
from app.database import get_db
from app.models.user import UserInDB
from app.schemas.auth_schema import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.user_schema import SignupRequest
from app.utils.dependencies import get_current_user
from app.utils.email import send_reset_email
from app.utils.jwt import create_access_token, create_refresh_token, decode_token
from app.utils.security import hash_password, verify_password

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


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db=Depends(get_db)):
    user = await db["users"].find_one({"email": request.email})
    if not user or not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    user_id = str(user["_id"])
    return TokenResponse(
        access_token=create_access_token(user_id, user["email"]),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest, db=Depends(get_db)):
    payload = decode_token(request.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user = await db["users"].find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user_id = str(user["_id"])
    return TokenResponse(
        access_token=create_access_token(user_id, user["email"]),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(request: ForgotPasswordRequest, db=Depends(get_db)):
    user = await db["users"].find_one({"email": request.email})
    if user:
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
        await db["users"].update_one(
            {"_id": user["_id"]},
            {"$set": {"reset_token": token, "reset_token_expires": expires}},
        )
        await send_reset_email(user["email"], token)
    return MessageResponse(message="If that email is registered, you'll receive a reset link shortly.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(request: ResetPasswordRequest, db=Depends(get_db)):
    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    user = await db["users"].find_one({
        "reset_token": request.token,
        "reset_token_expires": {"$gt": datetime.now(timezone.utc)},
    })
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    await db["users"].update_one(
        {"_id": user["_id"]},
        {
            "$set": {"hashed_password": hash_password(request.new_password)},
            "$unset": {"reset_token": "", "reset_token_expires": ""},
        },
    )
    return MessageResponse(message="Password reset successful.")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    if not verify_password(request.current_password, current_user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    await db["users"].update_one(
        {"_id": current_user["_id"]},
        {"$set": {"hashed_password": hash_password(request.new_password)}},
    )
    return MessageResponse(message="Password changed successfully.")
