import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure

from app.core.config import settings


class MongoDB:
    def __init__(self) -> None:
        """Initialize the wrapper with no active client or database."""
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None

    async def connect(self) -> None:
        """Open a pooled Motor client and verify it with a ping.

        Raises:
            ConnectionFailure: If MongoDB cannot be reached.
        """
        try:
            self._client = AsyncIOMotorClient(
                settings.mongo_uri,
                maxPoolSize=20,
                minPoolSize=1,
                serverSelectionTimeoutMS=5000,
                tz_aware=True,
            )
            await self._client.admin.command("ping")
            self._db = self._client[settings.mongo_db]
            # Never log the URI: it can carry credentials.
            logging.info("Connected to MongoDB database '%s'", settings.mongo_db)
        except ConnectionFailure as e:
            logging.error("MongoDB connection failed: %s", type(e).__name__)
            raise

    async def get_database(self) -> AsyncIOMotorDatabase:
        """Return the database, connecting first if needed."""
        if self._db is None:
            await self.connect()
        return self._db

    async def ping(self) -> None:
        """Run a ping against the server (used by the health probe)."""
        db = await self.get_database()
        await db.command("ping")

    async def close(self) -> None:
        """Close the MongoDB connection if one is open."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None


# Singleton instance used across the app.
mongodb = MongoDB()
