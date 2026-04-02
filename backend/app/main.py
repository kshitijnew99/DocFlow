from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.database import engine, Base
from app.core.config import get_settings
from app.api.routes import router
import app.models.models  # ensure models are registered

settings = get_settings()


def _parse_cors_origins(origins: str) -> list[str]:
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In production use Alembic migrations instead of create_all.
    if settings.ENVIRONMENT.lower() == "development" and settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="DocFlow — Async Document Processing API",
    version="1.0.0",
    description="Upload, process, review, and export documents asynchronously.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(settings.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "service": "DocFlow API",
        "version": "1.0.0",
        "docs": "/docs",
    }
