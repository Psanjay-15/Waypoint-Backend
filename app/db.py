"""MongoDB (Atlas) connection — single Motor client, lazily created."""

from __future__ import annotations

import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        kwargs: dict = {"serverSelectionTimeoutMS": 8000}
        # Atlas (mongodb+srv / TLS) needs an explicit CA bundle on macOS Python.
        if "mongodb+srv" in settings.mongodb_uri or "tls=true" in settings.mongodb_uri.lower():
            kwargs["tlsCAFile"] = certifi.where()
        _client = AsyncIOMotorClient(settings.mongodb_uri, **kwargs)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongodb_db]


async def ping() -> bool:
    await get_client().admin.command("ping")
    return True


async def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


# Collection accessors — keep names in one place.
def states_col():
    return get_db()["states"]


def chat_logs_col():
    return get_db()["chat_logs"]
