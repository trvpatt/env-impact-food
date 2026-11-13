import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.errors import register_error_handlers
from app.routers import (
    assistant,
    auth,
    billing,
    content,
    foods,
    get_involved,
    home,
    local_produce,
    recipes,
    reference,
    reports,
    restaurants,
    shopping_lists,
    support,
    survey,
    users,
)

API_PREFIX = "/api/v1"
ROUTERS = [
    auth,
    users,
    survey,
    reference,
    billing,
    home,
    reports,
    shopping_lists,
    foods,
    restaurants,
    recipes,
    local_produce,
    get_involved,
    content,
    assistant,
    support,
]


def _configure_logging(level: str) -> None:
    # Twelve-factor: an unbuffered event stream on stdout; the platform handles routing.
    logging.basicConfig(
        stream=sys.stdout,
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    _configure_logging(settings.log_level)
    app = FastAPI(
        title="Rooted Web App API",
        version="0.1.0",
        lifespan=lifespan,
        # operationId = handler function name, matching openapi.yaml.
        generate_unique_id_function=lambda route: route.name,
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    register_error_handlers(app)
    for module in ROUTERS:
        app.include_router(module.router, prefix=API_PREFIX)
    return app


app = create_app()
