from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from app.config import JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_MINUTES


def _create_token(data: dict, expires_minutes: int) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: str, email: str, device_id: str = "") -> str:
    return _create_token({"sub": user_id, "email": email, "type": "access", "did": device_id}, ACCESS_TOKEN_EXPIRE_MINUTES)


def create_refresh_token(user_id: str) -> str:
    return _create_token({"sub": user_id, "type": "refresh"}, REFRESH_TOKEN_EXPIRE_MINUTES)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
