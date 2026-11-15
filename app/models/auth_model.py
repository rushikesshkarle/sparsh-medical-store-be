from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Body of ``POST /auth/login``."""

    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=256)


class AdminPublic(BaseModel):
    """The signed-in admin as it leaves the API."""

    username: str


class LoginResult(BaseModel):
    """Result of a successful admin login."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    admin: AdminPublic
