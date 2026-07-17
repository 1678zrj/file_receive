from fastapi import FastAPI

from app.core.config import settings
from app.api.v1.router import api_router as v1_router

from contextlib import asynccontextmanager
from app.db.session import create_db_and_tables, init_test_data





@asynccontextmanager
async def lifespan(app: FastAPI):

    await create_db_and_tables()
    await init_test_data()
    yield




app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    debug=settings.debug,
)

app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
