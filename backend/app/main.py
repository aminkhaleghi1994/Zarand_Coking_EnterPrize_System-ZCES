import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.common.bus import bus
from app.common.schemas import HealthStatus
from app.core.config import Settings, get_settings
from app.core.database import check_database_health, dispose_engine, get_engine, init_engine
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.tracing import new_trace_id, set_trace_id
from app.modules.audit.router import router as audit_router
from app.modules.loan.router import router as loan_router
from app.modules.notification.relay import start_relay, stop_relay
from app.modules.notification.router import router as notification_router
from app.modules.user.router import admin_router as user_admin_router
from app.modules.user.router import router as user_router
from app.modules.warehouse.router import router as warehouse_router

TRACE_HEADER = "X-Request-ID"


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get(TRACE_HEADER, "").strip()
        trace_id = incoming or new_trace_id()
        set_trace_id(trace_id)
        response = await call_next(request)
        response.headers[TRACE_HEADER] = trace_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = app.state.settings
    init_engine(settings)
    bus.attach_loop(asyncio.get_running_loop())
    relay = start_relay()
    yield
    stop_relay(relay)
    dispose_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    setup_logging(resolved.LOG_LEVEL)

    app = FastAPI(
        title=resolved.APP_NAME,
        version=resolved.APP_VERSION,
        lifespan=lifespan,
    )
    app.state.settings = resolved

    if resolved.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(TraceMiddleware)
    register_exception_handlers(app)

    async def health_status() -> HealthStatus:
        from starlette.concurrency import run_in_threadpool

        database = await run_in_threadpool(check_database_health, get_engine())
        return HealthStatus(
            app=resolved.APP_NAME,
            env=resolved.APP_ENV,
            version=resolved.APP_VERSION,
            components={"database": database},
        )

    @app.get("/healthz", response_model=HealthStatus, tags=["health"])
    async def healthz() -> HealthStatus:
        return await health_status()

    @app.get(f"{resolved.API_V1_PREFIX}/healthz", response_model=HealthStatus, tags=["health"])
    async def api_healthz() -> HealthStatus:
        return await health_status()

    app.include_router(user_router, prefix=resolved.API_V1_PREFIX)
    app.include_router(user_admin_router, prefix=resolved.API_V1_PREFIX)
    app.include_router(audit_router, prefix=resolved.API_V1_PREFIX)
    app.include_router(warehouse_router, prefix=resolved.API_V1_PREFIX)
    app.include_router(loan_router, prefix=resolved.API_V1_PREFIX)
    app.include_router(notification_router, prefix=resolved.API_V1_PREFIX)

    return app


app = create_app()
