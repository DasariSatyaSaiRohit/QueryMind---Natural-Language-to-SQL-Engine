from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    pass


def _build_database_url(raw: str) -> str:
    """Normalise to postgresql+asyncpg:// and fix SSL params for asyncpg."""
    url = raw
    # Replace scheme
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            url = url.replace(prefix, "postgresql+asyncpg://", 1)
            break

    # asyncpg uses ssl= not sslmode=
    url = url.replace("sslmode=require", "ssl=require")
    url = url.replace("sslmode=disable", "ssl=disable")
    url = url.replace("sslmode=prefer", "ssl=prefer")
    url = url.replace("sslmode=allow", "ssl=allow")

    # asyncpg doesn't support channel_binding
    url = url.replace("&channel_binding=require", "")
    url = url.replace("&channel_binding=disable", "")
    url = url.replace("?channel_binding=require&", "?")
    url = url.replace("?channel_binding=require", "")

    return url


engine = create_async_engine(
    _build_database_url(settings.DATABASE_URL),
    echo=settings.is_debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        "timeout": settings.QUERY_TIMEOUT,  # asyncpg uses "timeout" not "command_timeout"
        "server_settings": {
            "application_name": "querymind-service",
        },
    },
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()