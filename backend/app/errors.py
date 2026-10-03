"""Standard error responses — api-contract-spec.md §2."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.base import to_camel

logger = logging.getLogger("app.errors")


class AppError(Exception):
    def __init__(
        self, code: str, status: int, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.message = message
        self.details = details


def error_response(
    status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status, content={"error": body})


_HTTP_CODES = {
    401: ("UNAUTHORIZED", "Please log in."),
    404: ("NOT_FOUND", "Not found."),
    405: ("METHOD_NOT_ALLOWED", "This method is not allowed here."),
    413: ("PAYLOAD_TOO_LARGE", "Request body is too large."),
}


def _field_path(loc: tuple[Any, ...]) -> str:
    # ("body", "end_date") -> "endDate"; ("body", "days", 0, "time") -> "days.0.time"
    parts = [p for p in loc if p not in ("body", "query", "path")]
    return ".".join(to_camel(p) if isinstance(p, str) else str(p) for p in parts) or "body"


def _validation_message(err: dict[str, Any]) -> str:
    msg = str(err.get("msg", "Invalid value"))
    return msg.removeprefix("Value error, ")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, str] = {}
        for err in exc.errors():
            fields.setdefault(_field_path(tuple(err.get("loc", ()))), _validation_message(err))
        first = next(iter(fields.values()), "Invalid request.")
        return error_response(400, "VALIDATION_ERROR", first, {"fields": fields})

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _HTTP_CODES.get(exc.status_code, ("HTTP_ERROR", str(exc.detail)))
        return error_response(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled error", extra={"request_id": getattr(request.state, "request_id", None)}
        )
        return error_response(500, "INTERNAL_ERROR", "Something went wrong. Please try again.")
