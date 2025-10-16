import logging
import threading
import asyncpg
import asyncio
from typing import Optional, Callable, Awaitable, TypeVar
from asyncpg import Pool
import redis

T = TypeVar('T')

from src.config import settings
from src.common.exceptions import DatabaseException

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.pool: Optional[Pool] = None
        self._initialized = False
        self._init_lock = asyncio.Lock()
        self._connection_semaphore = asyncio.Semaphore(10)

    async def initialize(self) -> None:
        async with self._init_lock:
            if self._initialized:
                return
            try:
                logger.info(f"Connecting to database: {settings.db_host}:{settings.db_port}")
                self.pool = await asyncpg.create_pool(
                    host=settings.db_host,
                    port=settings.db_port,
                    user=settings.db_user,
                    password=settings.db_password,
                    database=settings.db_name,
                    ssl='require',
                    statement_cache_size=0,
                    min_size=2,
                    max_size=10,
                    command_timeout=30,
                    max_inactive_connection_lifetime=60,
                    server_settings={
                        'application_name': 'insurance_chatbot',
                        'statement_timeout': '30s'
                    }
                )
                async with self.pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                self._initialized = True
                logger.info("Database connection pool initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize database: {str(e)}")
                self.pool = None
                self._initialized = False

    def _is_transient(self, e: Exception) -> bool:
        transient_types = (
            asyncpg.InterfaceError,
            asyncpg.PostgresConnectionError,
            asyncpg.CannotConnectNowError,
            asyncpg.ConnectionDoesNotExistError,
        )
        return isinstance(e, transient_types)

    async def _with_retry(self, op: Callable[[], Awaitable[T]], retries: int = 3) -> T:
        last_exc: Optional[Exception] = None
        base_delay = 0.2
        for attempt in range(retries + 1):
            try:
                async with self._connection_semaphore:
                    if not self.pool or self.pool.is_closing():
                        raise DatabaseException("Database pool is not initialized or is closed.")
                    return await op()
            except Exception as e:
                last_exc = e
                error_msg = str(e).lower()
                transient = (self._is_transient(e) or
                           'another operation is in progress' in error_msg or
                           'connection was closed' in error_msg)

                if transient and attempt < retries:
                    logger.warning(
                        "DB retry %d/%d (%s): %s",
                        attempt + 1, retries + 1, e.__class__.__name__, str(e)
                    )
                    delay = base_delay * (2 ** attempt)
                    jitter = 0.05 * (attempt + 1)
                    await asyncio.sleep(delay + jitter)
                    continue
                raise
        assert last_exc
        raise last_exc


    async def fetch_one(self, query: str, params: list = None):
        async def _op():
            async with self.pool.acquire() as conn:
                if params:
                    return await conn.fetchrow(query, *params)
                return await conn.fetchrow(query)
        return await self._with_retry(_op)

    async def fetch_all(self, query: str, params: list = None):
        async def _op():
            async with self.pool.acquire() as conn:
                if params:
                    return await conn.fetch(query, *params)
                return await conn.fetch(query)
        return await self._with_retry(_op)

    async def execute(self, query: str, params: list = None):
        async def _op():
            async with self.pool.acquire() as conn:
                if params:
                    return await conn.execute(query, *params)
                return await conn.execute(query)
        return await self._with_retry(_op)

    async def get_pool(self) -> Pool:
        if not self.pool:
            raise DatabaseException("Database pool not initialized")
        return self.pool

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            self._initialized = False
            logger.info("Database connection pool closed")


class RedisManager:
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._init_lock = threading.Lock()

    def initialize(self):
        with self._init_lock:
            if self._client is not None:
                return
            try:
                if not settings.redis_url:
                    raise ConnectionError("REDIS_URL is not configured in your settings/.env file.")
                
                logger.info(f"Connecting to Redis at {settings.redis_url}")
                self._client = redis.from_url(settings.redis_url)
                self._client.ping()
                logger.info("Redis connection successful.")
            except Exception as e:
                logger.error(f"Failed to initialize Redis: {e}", exc_info=True)
                self._client = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self.initialize()
        if self._client is None:
            raise ConnectionError("Redis client is not initialized.")
        return self._client
    
    def close(self):
        """Safely closes the Redis client connection."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Redis connection closed.")

redis_manager = RedisManager()
db_manager = DatabaseManager()