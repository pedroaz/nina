from .config import router as config_router
from .health import router as health_router
from .integrations import router as integrations_router
from .jobs import router as jobs_router
from .llm import router as llm_router
from .meetings import router as meetings_router
from .notes import router as notes_router
from .repositories import router as repositories_router
from .codex import router as codex_router
from .search import router as search_router
from .sessions import router as sessions_router
from .tasks import router as tasks_router
from .voice import router as voice_router
from .workflows import router as workflows_router

ROUTERS = [
    health_router,
    config_router,
    tasks_router,
    search_router,
    llm_router,
    sessions_router,
    notes_router,
    repositories_router,
    workflows_router,
    jobs_router,
    meetings_router,
    voice_router,
    integrations_router,
    codex_router,
]


__all__ = ["ROUTERS"]
