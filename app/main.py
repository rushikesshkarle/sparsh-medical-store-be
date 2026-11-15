import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.routes import router as api_router
from app.core.config import settings
from app.services.product_service import ensure_product_indexes
from app.shared.constants import GlobalConstants, ImageConstants
from app.shared.db_connections.mongo import mongodb
from app.shared.exception_filter import ExceptionFilter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(GlobalConstants.log_file_path), logging.StreamHandler()],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Connect to MongoDB and ensure indexes; close on shutdown."""
    logging.info("Starting up Sparsh Medical API...")
    await mongodb.connect()
    await ensure_product_indexes()
    logging.info("Startup complete")
    yield
    logging.info("Shutting down Sparsh Medical API...")
    await mongodb.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Registers the versioned API under ``/api/v1``, serves product images from
    ``/media``, enables CORS for the configured origins and attaches the
    exception handlers.
    """
    settings.validate_for_production()

    app = FastAPI(
        title="sparsh-medical-api",
        version=GlobalConstants.app_version,
        description="Sparsh Medical store backend — product catalogue and admin API",
        # Interactive docs are a dev convenience; hidden in production.
        docs_url=None if settings.is_production else "/api/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(api_router, prefix="/api/v1")

    settings.media_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        ImageConstants.MEDIA_URL_PREFIX,
        StaticFiles(directory=settings.media_dir),
        name="media",
    )

    ExceptionFilter.register(app)
    return app


app = create_app()
