"""JWT issuing and the signed-in / admin-only route guards."""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.shared.constants import HTTPCodes
from app.shared.custom_error import raise_custom_error
from app.shared.custom_messages import CustomMessages

_bearer = HTTPBearer(auto_error=False)


def create_access_token(subject: str) -> tuple[str, int]:
    """Issue a signed JWT for a user id.

    The token carries no role: admin is re-checked against ``ALLOWED_ADMIN_EMAILS``
    on every request, so removing an email takes effect without waiting for expiry.

    Returns:
        tuple[str, int]: The token and its lifetime in seconds.
    """
    lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + lifetime}
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


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """FastAPI dependency: require a valid Bearer token for any signed-in user.

    Returns:
        UserPublic: The signed-in user.
    """
    # Imported here to avoid a services ↔ shared import cycle.
    from app.services.auth_service import AuthService

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.auth_header_missing)
    payload = decode_access_token(credentials.credentials)
    return await AuthService().get_active_user(payload["sub"])


async def require_admin(user=Depends(get_current_user)):
    """FastAPI dependency: require a signed-in user whose email is in ``ALLOWED_ADMIN_EMAILS``.

    Raises:
        HTTPException: 403 for a signed-in customer who is not an admin.
    """
    if not user.is_admin:
        raise_custom_error(HTTPCodes.FORBIDDEN, CustomMessages.admin_required)
    return user
