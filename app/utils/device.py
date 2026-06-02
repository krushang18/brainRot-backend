import random
import uuid

from fastapi import Request, Response

from app.config import COOKIE_SAMESITE, COOKIE_SECURE

DEVICE_COOKIE = "device_id"


def get_or_create_device_id(request: Request, response: Response, client_device_id: str | None = None) -> str:
    device_id = client_device_id or request.cookies.get(DEVICE_COOKIE)
    if not device_id:
        device_id = str(uuid.uuid4())
    response.set_cookie(
        DEVICE_COOKIE,
        device_id,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=365 * 24 * 3600,
    )
    return device_id


def generate_otp() -> str:
    return str(random.randint(100000, 999999))


def parse_device_name(user_agent: str) -> str:
    ua = user_agent.lower()
    os_ = (
        "Windows" if "windows" in ua else
        "macOS"   if "mac os"  in ua else
        "iPhone"  if "iphone"  in ua else
        "Android" if "android" in ua else
        "Linux"
    )
    browser = (
        "Chrome"  if "chrome"  in ua and "edg" not in ua else
        "Edge"    if "edg"     in ua else
        "Firefox" if "firefox" in ua else
        "Safari"  if "safari"  in ua else
        "Browser"
    )
    return f"{browser} on {os_}"
