from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.kernel import models as kernel_models  # noqa: F401 - registers kernel ORM models
from app.kernel.admin.routes import router as admin_router
from app.kernel.admin.service import load_runtime_settings
from app.kernel.agent.routes import router as agent_router
from app.kernel.agent.ws import ws_router
from app.kernel.audit.routes import router as audit_router
from app.kernel.auth.routes import router as auth_router
from app.kernel.config import get_settings
from app.kernel.context import build_kernel_context, set_kernel_context
from app.kernel.database import Base, engine
from app.kernel.database import SessionLocal
from app.kernel.plugins import PluginManager, load_plugins
from app.kernel.redis import ensure_redis_available
from app.kernel.middleware import RateLimitMiddleware
from app.kernel.responses import GENERIC_SERVER_ERROR_MESSAGE, error, ok


def create_app() -> FastAPI:
    settings = get_settings()
    context = build_kernel_context(settings)
    set_kernel_context(context)
    plugin_manager = load_plugins(settings.plugin_module_list, context)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        settings.validate_startup_config()
        ensure_redis_available(context.capabilities.redis)
        Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
        if settings.auto_create_tables:
            Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            load_runtime_settings(db, settings)
        # 注册插件工具到 ToolRegistry
        for tool in plugin_manager.collect_tools():
            context.capabilities.tool_registry.register(tool)
        yield

    app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
    app.state.kernel_context = context
    app.state.plugin_manager = plugin_manager
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        RateLimitMiddleware,
        redis=context.capabilities.redis,
        per_ip_limit=settings.rate_limit_per_ip,
        per_user_limit=settings.rate_limit_per_user,
        upload_limit=settings.rate_limit_upload,
        window_seconds=settings.rate_limit_window_seconds,
    )
    app.include_router(_build_api_router(plugin_manager))
    _register_error_handlers(app)

    @app.get("/")
    async def root():
        return {"status": "ok", "service": settings.app_name, "docs": "/docs"}

    return app


def _build_api_router(plugin_manager: PluginManager) -> APIRouter:
    api_router = APIRouter(prefix="/api")
    api_router.include_router(auth_router)
    api_router.include_router(admin_router)
    api_router.include_router(audit_router)
    api_router.include_router(agent_router)
    api_router.include_router(ws_router)

    @api_router.get("/plugins", tags=["kernel"])
    def list_plugins():
        return ok(plugin_manager.describe())

    plugin_manager.register_routers(api_router)
    return api_router


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error_handler(_: Request, exc: HTTPException):
        return _http_error_response(exc)

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_error_handler(_: Request, exc: StarletteHTTPException):
        return _http_error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error(4220, "请求参数校验失败", {"errors": jsonable_encoder(exc.errors())}),
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(_: Request, __: SQLAlchemyError):
        return JSONResponse(status_code=500, content=error(5001, "数据库操作失败"))

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, __: Exception):
        return JSONResponse(status_code=500, content=error(5000, GENERIC_SERVER_ERROR_MESSAGE))


def _http_error_response(exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code >= 500:
        message = GENERIC_SERVER_ERROR_MESSAGE
        data = None
    elif isinstance(exc.detail, str):
        message = exc.detail
        data = None
    else:
        message = "请求未能完成"
        data = {"detail": exc.detail}
    return JSONResponse(status_code=exc.status_code, content=error(exc.status_code, message, data), headers=exc.headers)
