from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import audit, auth, devices, documents, inspect, operations, recommendations, templates
from app.config import settings

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    log.info("FireManager starting", environment=settings.environment)
    yield
    log.info("FireManager shutting down")


app = FastAPI(
    title="FireManager API",
    description="Plataforma Multivendor de Gestão de Firewalls com IA",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(devices.router, prefix="/devices", tags=["devices"])
app.include_router(operations.router, prefix="/operations", tags=["operations"])
app.include_router(audit.router, prefix="/audit", tags=["audit"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(templates.router, prefix="/templates", tags=["templates"])
app.include_router(inspect.router, prefix="/devices", tags=["inspect"])
app.include_router(recommendations.router, prefix="/devices", tags=["recommendations"])


class FireManagerError(Exception):
    status_code: int = 500
    default_message: str = "Internal server error"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


@app.exception_handler(FireManagerError)
async def firemanager_error_handler(request: Request, exc: FireManagerError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
