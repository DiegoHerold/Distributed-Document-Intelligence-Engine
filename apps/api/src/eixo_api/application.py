from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from eixo.engine import DocumentEngine
from eixo_api.configuration import ApiConfig
from eixo_api.error_handlers import register_error_handlers
from eixo_api.lifecycle import ApiState, api_lifespan
from eixo_api.middleware import CorrelationIdMiddleware
from eixo_api.routers import documents_router, extractions_router, health_router


def create_app(
    *,
    config: ApiConfig | None = None,
    engine: DocumentEngine | None = None,
) -> FastAPI:
    resolved_config = config or ApiConfig()
    app = FastAPI(
        title=resolved_config.title,
        description=resolved_config.description,
        version=resolved_config.version,
        debug=resolved_config.debug,
        docs_url="/docs" if resolved_config.docs_enabled else None,
        redoc_url="/redoc" if resolved_config.docs_enabled else None,
        openapi_url="/openapi.json" if resolved_config.docs_enabled else None,
        lifespan=api_lifespan,
    )
    app.state.eixo = ApiState(config=resolved_config, engine=engine)
    if resolved_config.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved_config.cors_allowed_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["X-Correlation-ID", "Content-Type"],
        )
    app.add_middleware(CorrelationIdMiddleware)
    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(documents_router)
    app.include_router(extractions_router)
    return app


__all__ = ["create_app"]
