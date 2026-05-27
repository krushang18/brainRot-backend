import os
from dotenv import load_dotenv

load_dotenv()

# --- Database ---
MONGODB_URI = os.getenv("MONGODB_URI", "DB_URL_NOT_SET")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "BrainRot")

# --- JWT ---
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

# --- OTP & Password Reset ---
OTP_EXPIRE_MINUTES = 2
RESET_TOKEN_EXPIRE_MINUTES = 10

# --- Email ---
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# --- CORS & Frontend ---
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "none" if COOKIE_SECURE else "lax")
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",")]
