from __future__ import annotations

import logging
from asyncio import CancelledError
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import create_api_router, create_compat_router, create_system_router
from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.core.exceptions import AppError
from app.integrations.cache import CacheClient
from app.middleware.rate_limit import enforce_rate_limit
from app.middleware.request_context import (
    reset_request_context,
    set_request_context,
)
from app.observability.metrics import metrics

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_application() -> FastAPI:
    configure_logging()
    settings = get_settings()
    cache = CacheClient(settings)
    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    )

    @app.middleware("http")
    async def request_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request_token, user_token = set_request_context(request_id=request_id)
        request.state.request_id = request_id
        started_at = perf_counter()
        limit_result = None
        response = None
        status_code = 500

        try:
            # Pass OPTIONS (CORS preflight) through immediately so CORSMiddleware
            # can attach the required Access-Control-Allow-* headers before the
            # rate-limit check, which would otherwise strip them.
            if request.method == "OPTIONS":
                response = await call_next(request)
                response.headers["X-Request-ID"] = request_id
                return response

            limit_result = enforce_rate_limit(request, settings, cache)
            if not limit_result.allowed:
                metrics.record_rate_limited()
                logger.warning(
                    "Rate limit exceeded method=%s path=%s bucket=%s limit=%s",
                    request.method,
                    request.url.path,
                    limit_result.bucket,
                    limit_result.limit,
                )
                response = JSONResponse(
                    status_code=429,
                    content={
                        "error_code": "rate_limited",
                        "message": "Rate limit exceeded",
                    },
                )
                response.headers["X-Request-ID"] = request_id
                response.headers["X-RateLimit-Limit"] = str(limit_result.limit)
                response.headers["X-RateLimit-Remaining"] = str(limit_result.remaining)
                response.headers["Retry-After"] = str(limit_result.reset_seconds)
                status_code = response.status_code
                return response

            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            response.headers["X-RateLimit-Limit"] = str(limit_result.limit)
            response.headers["X-RateLimit-Remaining"] = str(limit_result.remaining)
            return response
        except CancelledError:
            status_code = 499
            logger.info(
                "Request cancelled method=%s path=%s",
                request.method,
                request.url.path,
            )
            response = Response(status_code=status_code)
            response.headers["X-Request-ID"] = request_id
            if limit_result:
                response.headers["X-RateLimit-Limit"] = str(limit_result.limit)
                response.headers["X-RateLimit-Remaining"] = str(limit_result.remaining)
            return response
        except RuntimeError as exc:
            if str(exc) != "No response returned.":
                raise

            status_code = 499
            logger.info(
                "Request finished before a response was generated method=%s path=%s",
                request.method,
                request.url.path,
            )
            response = Response(status_code=status_code)
            response.headers["X-Request-ID"] = request_id
            if limit_result:
                response.headers["X-RateLimit-Limit"] = str(limit_result.limit)
                response.headers["X-RateLimit-Remaining"] = str(limit_result.remaining)
            return response
        finally:
            latency_ms = round((perf_counter() - started_at) * 1000, 2)
            if limit_result and limit_result.allowed:
                logger.info(
                    "Handled request method=%s path=%s status=%s latency_ms=%s bucket=%s",
                    request.method,
                    request.url.path,
                    status_code,
                    latency_ms,
                    limit_result.bucket,
                )
            reset_request_context(request_token, user_token)

            metrics.record_request(request.url.path, latency_ms, status_code)

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "Application error path=%s error_code=%s message=%s",
            request.url.path,
            exc.error_code,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": exc.error_code, "message": exc.message},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled application exception path=%s", request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"error_code": "internal_server_error", "message": "Internal server error"},
        )

    app.include_router(create_system_router())
    app.include_router(create_api_router(), prefix=settings.api_v1_prefix)
    app.include_router(create_compat_router(), prefix=settings.api_compat_prefix)
    
    # Import and register the enhanced RAG router
    from enhanced_rag_integration import router as enhanced_rag_router
    app.include_router(enhanced_rag_router)

    return app


app = create_application()

@app.on_event("startup")
async def startup_event():
    try:
        from enhanced_rag_integration import init_enhanced_rag
        await init_enhanced_rag()
        logger.info("Enhanced RAG pipeline initialized.")
    except ImportError:
        logger.warning("Could not initialize Enhanced RAG pipeline (missing dependencies)")
    except Exception as e:
        logger.error(f"Error initializing Enhanced RAG: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    try:
        from enhanced_rag_integration import shutdown_enhanced_rag
        await shutdown_enhanced_rag()
        logger.info("Enhanced RAG pipeline shut down.")
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Error shutting down Enhanced RAG: {e}")
