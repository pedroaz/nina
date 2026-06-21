from __future__ import annotations

from fastapi import FastAPI

import nina_core

from .auth import TokenAuthMiddleware
from .routers import ROUTERS


def create_app() -> FastAPI:
    application = FastAPI(title="Nina Daemon", version=nina_core.__version__)
    application.add_middleware(TokenAuthMiddleware)
    for router in ROUTERS:
        application.include_router(router)
    return application


app = create_app()
