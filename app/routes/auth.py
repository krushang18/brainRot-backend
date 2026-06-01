import secrets
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from authlib.integrations.starlette_client import OAuth
from app.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    OTP_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_MINUTES,
    RESET_TOKEN_EXPIRE_MINUTES,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
)
from app.database import get_db
from app.models.user import UserInDB
from app.schemas.auth_schema import (
    ChangePasswordRequest,
    DeviceInfo,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    ResendOTPRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyOTPRequest,
)
from app.schemas.user_schema import SignupRequest
from app.utils.dependencies import get_current_user
from app.utils.device import generate_otp, get_or_create_device_id, parse_device_name
from app.utils.email import send_otp_email, send_reset_email
from app.utils.jwt import create_access_token, create_refresh_token, decode_token
from app.utils.security import hash_password, verify_password

router = APIRouter()
print("AUTH FILE LOADED")
oauth = OAuth()
print(GOOGLE_CLIENT_ID)
print(GOOGLE_CLIENT_SECRET)
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    },
)


print("GOOGLE OAUTH REGISTERED")

async def _save_session(db, user_id, device_id: str, refresh_token: str) -> None:
    await db["sessions"].insert_one({
        "user_id": user_id,
        "device_id": device_id,
        "refresh_token": refresh_token,
        "expires": datetime.now(timezone.utc) + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES),
        "created_at": datetime.now(timezone.utc),
    })


@router.post("/signup", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def signup(user: SignupRequest, request: Request, response: Response, db=Depends(get_db)):
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

    device_id = get_or_create_device_id(request, response)
    ua = request.headers.get("user-agent", "")
    now = datetime.now(timezone.utc)
    device_doc = {
        "device_id": device_id,
        "name": parse_device_name(ua),
        "ip": request.client.host,
        "added_at": now,
        "last_used": now,
    }
    await db["users"].update_one(
        {"_id": result.inserted_id},
        {"$push": {"trusted_devices": device_doc}},
    )

    refresh = create_refresh_token(user_id)
    await _save_session(db, result.inserted_id, device_id, refresh)
    return LoginResponse(
        otp_required=False,
        access_token=create_access_token(user_id, user.email, device_id),
        refresh_token=refresh,
        device_id=device_id,
    )


@router.post("/login", response_model=LoginResponse)
async def login(request_body: LoginRequest, request: Request, response: Response, db=Depends(get_db)):
    user = await db["users"].find_one({"email": request_body.email})
    if user and user.get("auth_provider") == "google":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please continue with Google login",
    )
    if not user or not verify_password(request_body.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    device_id = get_or_create_device_id(request, response, request_body.device_id)
    trusted = next(
        (d for d in user.get("trusted_devices", []) if d["device_id"] == device_id),
        None,
    )

    if trusted:
        await db["users"].update_one(
            {"_id": user["_id"], "trusted_devices.device_id": device_id},
            {"$set": {"trusted_devices.$.last_used": datetime.now(timezone.utc)}},
        )
        await db["revoked_devices"].delete_many({"user_id": user["_id"], "device_id": device_id})
        user_id = str(user["_id"])
        refresh = create_refresh_token(user_id)
        await _save_session(db, user["_id"], device_id, refresh)
        return LoginResponse(
            otp_required=False,
            access_token=create_access_token(user_id, user["email"], device_id),
            refresh_token=refresh,
            device_id=device_id,
        )

    otp = generate_otp()
    expires = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
    await db["users"].update_one(
        {"_id": user["_id"]},
        {"$set": {"pending_otp": {"code": otp, "device_id": device_id, "expires": expires}}},
    )
    await send_otp_email(user["email"], otp)
    return LoginResponse(otp_required=True, device_id=device_id)


@router.post("/verify-otp", response_model=LoginResponse)
async def verify_otp(
    request_body: VerifyOTPRequest,
    request: Request,
    response: Response,
    db=Depends(get_db),
):
    device_id = request_body.device_id or request.cookies.get("device_id")
    if not device_id:
        raise HTTPException(status_code=400, detail="No device cookie found")

    user = await db["users"].find_one({
        "email": request_body.email,
        "pending_otp.code": request_body.otp,
        "pending_otp.device_id": device_id,
        "pending_otp.expires": {"$gt": datetime.now(timezone.utc)},
    })
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    ua = request.headers.get("user-agent", "")
    now = datetime.now(timezone.utc)
    device_doc = {
        "device_id": device_id,
        "name": parse_device_name(ua),
        "ip": request.client.host,
        "added_at": now,
        "last_used": now,
    }
    await db["users"].update_one(
        {"_id": user["_id"]},
        {"$push": {"trusted_devices": device_doc}, "$unset": {"pending_otp": ""}},
    )
    await db["revoked_devices"].delete_many({"user_id": user["_id"], "device_id": device_id})

    user_id = str(user["_id"])
    refresh = create_refresh_token(user_id)
    await _save_session(db, user["_id"], device_id, refresh)
    return LoginResponse(
        otp_required=False,
        access_token=create_access_token(user_id, user["email"], device_id),
        refresh_token=refresh,
        device_id=device_id,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest, db=Depends(get_db)):
    payload = decode_token(request.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    session = await db["sessions"].find_one({"refresh_token": request.refresh_token})
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = await db["users"].find_one({"_id": session["user_id"]})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    device_id = session["device_id"]
    await db["sessions"].delete_one({"_id": session["_id"]})
    user_id = str(user["_id"])
    refresh = create_refresh_token(user_id)
    await _save_session(db, user["_id"], device_id, refresh)
    return TokenResponse(
        access_token=create_access_token(user_id, user["email"], device_id),
        refresh_token=refresh,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(request_body: LogoutRequest, request: Request, db=Depends(get_db)):
    await db["sessions"].delete_one({"refresh_token": request_body.refresh_token})

    device_id = request.cookies.get("device_id", "")
    payload = decode_token(request_body.refresh_token)
    if device_id and payload:
        await db["revoked_devices"].insert_one({
            "user_id": ObjectId(payload["sub"]),
            "device_id": device_id,
            "expires": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        })

    return MessageResponse(message="Logged out successfully.")


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


@router.post("/resend-otp", response_model=MessageResponse)
async def resend_otp(request_body: ResendOTPRequest, request: Request, db=Depends(get_db)):
    device_id = request_body.device_id or request.cookies.get("device_id")
    if not device_id:
        raise HTTPException(status_code=400, detail="No device cookie found")
    user = await db["users"].find_one({"email": request_body.email})
    if user:
        otp = generate_otp()
        expires = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
        await db["users"].update_one(
            {"_id": user["_id"]},
            {"$set": {"pending_otp": {"code": otp, "device_id": device_id, "expires": expires}}},
        )
        await send_otp_email(user["email"], otp)
    return MessageResponse(message="If a login was pending, a new OTP has been sent.")

@router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = "https://localhost:8000/auth/google/callback"

    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
    )

@router.get("/google/callback")
async def google_callback(
    request: Request,
    response: Response,
    db=Depends(get_db),
):
    token = await oauth.google.authorize_access_token(request)

    user_info = token.get("userinfo")

    email = user_info["email"]
    full_name = user_info.get("name", "")
    google_id = user_info.get("sub")

    user = await db["users"].find_one({"email": email})

    if not user:
        user_doc = UserInDB(
            full_name=full_name,
            email=email,
            hashed_password=None,
            auth_provider="google",
            google_id=google_id,
        )
        result = await db["users"].insert_one(user_doc.model_dump())

        user = await db["users"].find_one({
            "_id": result.inserted_id
        })

    user_id = str(user["_id"])

    device_id = get_or_create_device_id(request, response)

    ua = request.headers.get("user-agent", "")
    now = datetime.now(timezone.utc)

    trusted = next(
        (
            d for d in user.get("trusted_devices", [])
            if d["device_id"] == device_id
        ),
        None
    )

    if not trusted:
        device_doc = {
            "device_id": device_id,
            "name": parse_device_name(ua),
            "ip": request.client.host,
            "added_at": now,
            "last_used": now,
        }

        await db["users"].update_one(
            {"_id": user["_id"]},
            {"$push": {"trusted_devices": device_doc}},
        )

    refresh = create_refresh_token(user_id)

    await _save_session(
        db,
        user["_id"],
        device_id,
        refresh,
    )

    return LoginResponse(
        otp_required=False,
        access_token=create_access_token(
            user_id,
            email,
            device_id,
        ),
        refresh_token=refresh,
        device_id=device_id,
    )

@router.get("/devices", response_model=list[DeviceInfo])
async def list_devices(current_user=Depends(get_current_user)):
    return current_user.get("trusted_devices", [])


@router.delete("/devices", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all_devices(current_user=Depends(get_current_user), db=Depends(get_db)):
    device_ids = [d["device_id"] for d in current_user.get("trusted_devices", [])]
    await db["users"].update_one(
        {"_id": current_user["_id"]},
        {"$set": {"trusted_devices": []}},
    )
    await db["sessions"].delete_many({"user_id": current_user["_id"]})
    if device_ids:
        expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        await db["revoked_devices"].insert_many([
            {"user_id": current_user["_id"], "device_id": did, "expires": expires}
            for did in device_ids
        ])


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_device(
    device_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    await db["users"].update_one(
        {"_id": current_user["_id"]},
        {"$pull": {"trusted_devices": {"device_id": device_id}}},
    )
    await db["sessions"].delete_many({"user_id": current_user["_id"], "device_id": device_id})
    await db["revoked_devices"].insert_one({
        "user_id": current_user["_id"],
        "device_id": device_id,
        "expires": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    })

