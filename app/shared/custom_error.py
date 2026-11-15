from typing import NoReturn, Optional

from fastapi import HTTPException
from pydantic import BaseModel


class CustomError(BaseModel):
    status_code: int
    message: str
    error: Optional[str] = None


def raise_custom_error(status_code: int, message: str, error: Optional[str] = None) -> NoReturn:
    """Raise an HTTPException carrying a :class:`CustomError` as the ``detail``.

    The registered exception handler returns that detail as-is, so every error
    the client sees has the shape ``{status_code, message, error}``.

    Args:
        status_code: HTTP status code for the response.
        message: Human-readable error message.
        error: Optional additional error detail.

    Raises:
        HTTPException: Always, carrying the serialized :class:`CustomError`.
    """
    detail = CustomError(status_code=status_code, message=message, error=error)
    raise HTTPException(status_code=status_code, detail=detail.model_dump())
