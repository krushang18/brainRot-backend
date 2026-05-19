import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "DB_URL_NOT_SET")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "BrainRot")
