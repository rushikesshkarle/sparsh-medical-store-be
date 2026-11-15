"""JWT issuing and the admin-only route guard."""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.shared.constants import AuthConstants, HTTPCodes
from app.shared.custom_error import raise_custom_error
from app.shared.custom_messages import CustomMessages

_bearer = HTTPBearer(auto_error=False)


def create_access_token(subject: str, credentials_version: str) -> tuple[str, int]:
    """Issue a signed JWT.

    ``cv`` ties the token to the current admin credentials, so changing the
    admin password in the environment signs every session out.

    Returns:
        tuple[str, int]: The token and its lifetime in seconds.
    """
    lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "cv": credentials_version, "iat": now, "exp": now + lifetime}
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> dict:
    """Verify a JWT and return its payload, raising the envelope error on failure."""
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"]},
        )
    except jwt.ExpiredSignatureError:
        raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.token_expired)
    except jwt.PyJWTError:
        raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.token_invalid)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """FastAPI dependency: require a valid admin Bearer token.

    Returns:
        AdminPublic: The signed-in admin.
    """
    # Imported here to avoid a services ↔ shared import cycle.
    from app.models.auth_model import AdminPublic
    from app.services.auth_service import credentials_version

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.auth_header_missing)
    payload = decode_access_token(credentials.credentials)
    if payload.get("sub") != AuthConstants.ADMIN_SUBJECT or payload.get("cv") != credentials_version():
        raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.token_invalid)
    return AdminPublic(username=settings.admin_username)
