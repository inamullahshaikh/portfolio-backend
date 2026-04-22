"""Async MongoDB client (Motor) and database accessor."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from models import Settings

_client: AsyncIOMotorClient | None = None


def get_settings() -> Settings:
    return Settings()


async def connect_db() -> None:
    global _client
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.MONGODB_URI)


async def close_db() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("Database not initialized")
    return _client[get_settings().DB_NAME]
