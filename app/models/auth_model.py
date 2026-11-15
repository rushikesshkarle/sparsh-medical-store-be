from datetime import datetime

from pydantic import BaseModel, Field

from app.shared.constants import AuthConstants


class GoogleAuthRequest(BaseModel):
    """Body of ``POST /auth/google``: the authorization code from the Google popup."""

    code: str = Field(min_length=1, max_length=AuthConstants.CODE_MAX_LENGTH)


class GoogleUserInfo(BaseModel):
    """The verified claims of a Google ID token that we keep."""

    sub: str
    email: str
    name: str = ""
    picture: str = ""


class UserPublic(BaseModel):
    """A user as it leaves the API.

    ``is_admin`` is computed from ``ALLOWED_ADMIN_EMAILS`` on every request, never
    stored, so removing an email from the env revokes admin access immediately.
    """

    id: str
    email: str
    name: str
    picture: str
    is_admin: bool
    created_at: datetime


class LoginResult(BaseModel):
    """Result of a successful sign-in."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic
