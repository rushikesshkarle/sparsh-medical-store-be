from typing import Any, Optional

from pydantic import BaseModel


class CustomResponse(BaseModel):
    """Success envelope returned by every route: ``{status_code, message, result}``."""

    status_code: int
    message: str
    result: Optional[Any] = None
