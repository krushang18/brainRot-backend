from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import MONGODB_URI, MONGODB_DATABASE

client: AsyncIOMotorClient = None
db: AsyncIOMotorDatabase = None

async def connect_to_db():
    global client, db
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[MONGODB_DATABASE]
    await client.admin.command("ping")
    await db["sessions"].create_index("expires", expireAfterSeconds=0)
    await db["revoked_devices"].create_index("expires", expireAfterSeconds=0)
    await db["oauth_states"].create_index("expires", expireAfterSeconds=0)
    await db["oauth_codes"].create_index("expires", expireAfterSeconds=0)
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
