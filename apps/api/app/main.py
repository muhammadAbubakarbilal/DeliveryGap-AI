import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app.analysis_routes import router as analysis_router
from app.config import get_settings
from app.evidence_routes import router as evidence_router
from app.operation_routes import router as operation_router
from app.requirement_routes import router as requirement_router
from app.routes import router
from app.security import DB
from app.source_routes import router as source_router

logger = logging.getLogger("deliverygap")
app = FastAPI(title="DeliveryGap AI", version="0.1.0")
app.include_router(router)
app.include_router(source_router)
app.include_router(requirement_router)
app.include_router(analysis_router)
app.include_router(evidence_router)
app.include_router(operation_router)


def error(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", "unknown"),
                "details": {},
            }
        },
    )


@app.middleware("http")
async def request_boundary(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request.state.request_id = str(uuid4())
    start = time.monotonic()
    response: Response
    if request.method not in {"GET", "HEAD", "OPTIONS"} and (
        request.headers.get("origin") != get_settings().app_origin
    ):
        # Fail closed: browser and script mutations must send the configured Origin.
        response = error(request, 403, "INVALID_ORIGIN", "Request origin is not allowed")
    else:
        try:
            response = await call_next(request)
        except Exception:
            # Deliberately omit exception text because DB/provider messages can contain secrets.
            logger.error("request_failed request_id=%s", request.state.request_id)
            response = error(request, 500, "INTERNAL_ERROR", "An unexpected error occurred")
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    logger.info(
        "request_complete request_id=%s status=%s elapsed_ms=%.1f",
        request.state.request_id,
        response.status_code,
        (time.monotonic() - start) * 1000,
    )
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    codes = {
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "UPLOAD_TOO_LARGE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        503: "DEPENDENCY_UNAVAILABLE",
    }
    return error(
        request, exc.status_code, codes.get(exc.status_code, "REQUEST_ERROR"), str(exc.detail)
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Never echo submitted password/cookie/input values from Pydantic errors.
    return error(request, 422, "VALIDATION_ERROR", "Check the submitted fields and try again")


@app.exception_handler(IntegrityError)
async def conflict_error(request: Request, exc: IntegrityError) -> JSONResponse:
    return error(request, 409, "CONFLICT", "This record already exists or conflicts with another")


@app.exception_handler(OperationalError)
async def dependency_error(request: Request, exc: OperationalError) -> JSONResponse:
    return error(
        request, 503, "DEPENDENCY_UNAVAILABLE", "Database is unavailable. Try again later."
    )


@app.get("/api/v1/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/health/ready")
def ready(db: DB) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except OperationalError as exc:
        raise HTTPException(503, "Database is unavailable") from exc
    return {"status": "ready"}
