from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import connect_to_db, close_db_connection
from app.routes.login import router as login_router

@asynccontextmanager
async def lifespan(_app: FastAPI):
    await connect_to_db()
    yield
    await close_db_connection()

app = FastAPI(lifespan=lifespan)
app.include_router(login_router, prefix="/auth")

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