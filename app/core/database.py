import certifi
from typing import Optional, Tuple
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError
import dns.resolver

from app.core.config import settings
from app.core.logging import logger

# Force dnspython to use public DNS to prevent SRV timeouts with buggy local routers (e.g. 192.168.1.254)
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ['8.8.8.8', '8.8.4.4', '1.1.1.1']

class DatabaseManager:
    """Centralized lifecycle manager for MongoDB client and database access."""

    def __init__(self) -> None:
        self._client: Optional[MongoClient] = None
        self._database: Optional[Database] = None

    def connect(self) -> None:
        """Initialize MongoDB client if connection URI is provided."""
        if not settings.MONGODB_URI or not settings.MONGODB_URI.strip():
            logger.warning("MongoDB URI is not configured. Database operations will be unavailable.")
            return

        try:
            self._client = MongoClient(
                settings.MONGODB_URI,
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
            )
            self._database = self._client[settings.MONGODB_DATABASE]
            logger.info("MongoDB client initialized.")
        except Exception as exc:
            # Never log the URI or credentials in the exception
            logger.error(f"Failed to initialize MongoDB client ({type(exc).__name__}): {str(exc)}")
            self._client = None
            self._database = None

    def close(self) -> None:
        """Close MongoDB client connection cleanly."""
        if self._client is not None:
            self._client.close()
            self._client = None
            self._database = None
            logger.info("MongoDB connection closed.")

    def get_database(self) -> Optional[Database]:
        """Return active MongoDB database instance if connected."""
        if self._database is None and settings.MONGODB_URI and settings.MONGODB_URI.strip():
            self.connect()
        return self._database

    def get_client(self) -> Optional[MongoClient]:
        """Return active MongoDB client instance if connected."""
        if self._client is None and settings.MONGODB_URI and settings.MONGODB_URI.strip():
            self.connect()
        return self._client

    def ping(self) -> Tuple[bool, str]:
        """
        Verify database connectivity.
        Returns a tuple of (is_healthy, status_message).
        """
        if not settings.MONGODB_URI or not settings.MONGODB_URI.strip():
            return False, "Database connection not configured"

        if self._client is None or self._database is None:
            # Try connecting if client wasn't connected yet
            self.connect()

        if self._client is None:
            return False, "Database client unavailable"

        try:
            # Ping MongoDB admin / database
            self._client.admin.command("ping")
            return True, "connected"
        except PyMongoError:
            # Do not expose internal details or credentials
            return False, "Database connection unreachable"
        except Exception:
            return False, "Database connection error"


db_manager = DatabaseManager()


def get_db() -> Optional[Database]:
    """Provide database accessor function."""
    return db_manager.get_database()
