from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str


class MessageResponse(BaseModel):
    message: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str


class LoginResponse(BaseModel):
    otp_required: bool
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    device_id: Optional[str] = None


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str
    device_id: Optional[str] = None


class DeviceInfo(BaseModel):
    device_id: str
    name: str
    ip: str
    added_at: datetime
    last_used: datetime


class LogoutRequest(BaseModel):
    refresh_token: str


class ResendOTPRequest(BaseModel):
    email: EmailStr
    device_id: Optional[str] = None
