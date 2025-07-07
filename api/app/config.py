import os

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")