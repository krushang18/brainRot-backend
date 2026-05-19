from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import MONGODB_URI, MONGODB_DATABASE

client: AsyncIOMotorClient = None
db: AsyncIOMotorDatabase = None

async def connect_to_db():
    global client, db
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[MONGODB_DATABASE]
    await client.admin.command("ping")
    print(f"✓ Connected to MongoDB: {MONGODB_DATABASE}")

async def close_db_connection():
    global client
    if client:
        client.close()
        print("✓ Closed MongoDB connection")

def get_db() -> AsyncIOMotorDatabase:
    if db is None:
        raise RuntimeError("Database not initialized. Call connect_to_db() first.")
    return db
