from eixo_api.routers.documents import router as documents_router
from eixo_api.routers.extractions import router as extractions_router
from eixo_api.routers.diagnostic_lab import router as diagnostic_lab_router
from eixo_api.routers.health import router as health_router

__all__ = [
    "diagnostic_lab_router",
    "documents_router",
    "extractions_router",
    "health_router",
]
