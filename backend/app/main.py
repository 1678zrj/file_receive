from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import ORJSONResponse, JSONResponse

from app.core.config import settings
from app.redis.redis_client import RedisManager
from app.api.v1.router import api_router as v1_router

from contextlib import asynccontextmanager
from app.db.session import create_db_and_tables, init_test_data
from app.core.broker import startup_broker, shutdown_broker
from app.rag.container import RAGContainer


@asynccontextmanager
async def lifespan(app: FastAPI):

    await create_db_and_tables()
    await init_test_data()
    await RedisManager.init()
    rag = RAGContainer()
    await rag.startup()
    app.state.rag = rag
    await startup_broker()

    yield
    await shutdown_broker()
    await rag.shutdown()
    await RedisManager.close()





app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    debug=settings.debug,
    # 已经过时，不再全局启用，但在全局异常处理中可启用
    # default_response_class=ORJSONResponse
)

app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}




from app.redis.cache import get_cache_service, CacheService
from fastapi import Depends
@app.get("/test-cache")
async def test_cache(cache: CacheService = Depends(get_cache_service)):
    # 用一个固定的测试键，值可以预先通过 set 写入
    val = await cache.get("test:perf")
    return {"value": val}