from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routes.auth import router as auth_router
from app.database import connect_to_db, close_db_connection

@asynccontextmanager
async def lifespan(_app: FastAPI):
    await connect_to_db()
    yield
    await close_db_connection()

app = FastAPI(lifespan=lifespan)
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