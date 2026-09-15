from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from app.core.config import settings


# worker使用的连接池应该与FastAPI后端使用的连接池区分开
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    # 这是默认的连接数量
    pool_size=5,
    # 这是超出默认连接数量之后可再增加的连接数量
    max_overflow=15,
    pool_pre_ping=True,
    pool_recycle=1800,

    connect_args = {
        "timeout": 10,
        "command_timeout": 30
    }
)
AsyncSessionWorker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


