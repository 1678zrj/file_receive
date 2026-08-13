from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import ORJSONResponse, JSONResponse

from app.core.config import settings
from app.redis.redis_client import RedisManager
from app.api.v1.router import api_router as v1_router

from contextlib import asynccontextmanager
from app.db.session import create_db_and_tables, init_test_data



@asynccontextmanager
async def lifespan(app: FastAPI):

    await create_db_and_tables()
    await init_test_data()
    await RedisManager.init()
    redis = RedisManager.get_client()
    await redis.set("test:perf", "hello")
    yield
    await RedisManager.close()




app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    debug=settings.debug,
    default_response_class=ORJSONResponse
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