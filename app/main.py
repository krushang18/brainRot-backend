from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS
from app.database import close_db_connection, connect_to_db
from app.routes.auth import router as auth_router

@asynccontextmanager
async def lifespan(_app: FastAPI):
    await connect_to_db()
    yield
    await close_db_connection()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,

    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    # allow_headers=["Accept", "Accept-Language", "Content-Language", "Content-Type", "Access-Control-Allow-Origin", "Authorization"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth")

@app.get("/")
def home():
    return {"message": "Backend running"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "backend": "running",
        "database": "connected"
    }
