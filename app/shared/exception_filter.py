"""Global exception handlers.

Every error the client sees is normalized to the standard envelope
``{ status_code, message, error }``. Register all handlers via
:meth:`ExceptionFilter.register`.
"""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.constants import HTTPCodes
from app.shared.custom_messages import CustomMessages


def _envelope(status_code: int, message: str, error=None) -> JSONResponse:
    """Build a JSONResponse in the standard ``{status_code, message, error}`` shape."""
    return JSONResponse(
        status_code=status_code,
        content={"status_code": status_code, "message": message, "error": error},
    )


class ExceptionFilter:
    @staticmethod
    async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle HTTPException (incl. ``raise_custom_error``) in the standard envelope.

        ``raise_custom_error`` sets ``detail`` to the envelope dict — passed
        through as-is. A plain-string ``detail`` (e.g. a framework 404) is wrapped.
        """
        detail = exc.detail
        if isinstance(detail, dict):
            return JSONResponse(status_code=exc.status_code, content=detail)
        return _envelope(exc.status_code, str(detail))

    @staticmethod
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors (422), reduced to ``{field, msg}`` per error.

        Pydantic's ``input`` and ``ctx`` are left out: they echo the request back
        and ``ctx`` can hold an exception object JSONResponse cannot serialize.
        """
        logging.warning(
            "Validation error on %s %s: %s", request.method, request.url.path, exc.errors()
        )
        errors = [
            {
                "field": ".".join(str(part) for part in error.get("loc", ())[1:]) or None,
                "msg": str(error.get("msg", "")).replace("Value error, ", ""),
            }
            for error in exc.errors()
        ]
        return _envelope(HTTPCodes.UNPROCESSABLE_ENTITY, CustomMessages.validation_failed, errors)

    @staticmethod
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Catch-all for unexpected exceptions; logs the trace, returns a sanitized 500."""
        logging.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return _envelope(HTTPCodes.INTERNAL_SERVER_ERROR, CustomMessages.internal_server_error)

    @staticmethod
    def register(app: FastAPI) -> None:
        """Attach all handlers to the application."""
        app.add_exception_handler(StarletteHTTPException, ExceptionFilter.custom_http_exception_handler)
        app.add_exception_handler(HTTPException, ExceptionFilter.custom_http_exception_handler)
        app.add_exception_handler(RequestValidationError, ExceptionFilter.validation_exception_handler)
        app.add_exception_handler(Exception, ExceptionFilter.unhandled_exception_handler)
