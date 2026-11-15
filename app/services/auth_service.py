"""Admin login against ``ADMIN_USERNAME`` / ``ADMIN_PASSWORD`` from the environment.

There is a single admin account and no customer accounts: shoppers browse and
order on WhatsApp as guests.
"""

import hashlib
import hmac
import logging
import time
from collections import deque

from app.core.config import settings
from app.models.auth_model import AdminPublic, LoginRequest, LoginResult
from app.shared.constants import AuthConstants, HTTPCodes
from app.shared.custom_error import raise_custom_error
from app.shared.custom_messages import CustomMessages
from app.shared.security import create_access_token

# Failed login timestamps per client IP, plus all of them together (per worker),
# for brute-force throttling. The global bucket guards against spoofed IPs.
_failures: dict[str, deque] = {}
_GLOBAL = "*"


def credentials_version() -> str:
    """A short fingerprint of the admin credentials, embedded in every token.

    Changing ``ADMIN_USERNAME`` or ``ADMIN_PASSWORD`` changes it, which signs
    out every existing session.
    """
    material = f"{settings.admin_username}\0{settings.admin_password}".encode()
    return hmac.new(settings.jwt_secret_key.encode(), material, hashlib.sha256).hexdigest()[:16]


def _recent_failures(client_ip: str) -> deque:
    window_start = time.monotonic() - AuthConstants.LOGIN_WINDOW_SECONDS
    attempts = _failures.setdefault(client_ip, deque())
    while attempts and attempts[0] < window_start:
        attempts.popleft()
    return attempts


def _matches(given: str, expected: str) -> bool:
    """Constant-time comparison (no timing leak of how much matched)."""
    return hmac.compare_digest(given.encode(), expected.encode())


class AuthService:
    """Admin login and token checks."""

    def login(self, body: LoginRequest, client_ip: str) -> LoginResult:
        """Check the admin username/password and issue a JWT.

        Raises:
            HTTPException: 503 if no admin is configured, 429 after too many
                failed attempts from this IP, 401 for a wrong username or password.
        """
        if not settings.admin_login_enabled:
            raise_custom_error(HTTPCodes.SERVICE_UNAVAILABLE, CustomMessages.admin_not_configured)

        attempts = _recent_failures(client_ip)
        everyone = _recent_failures(_GLOBAL)
        if len(attempts) >= AuthConstants.MAX_FAILED_LOGINS or len(everyone) >= AuthConstants.MAX_FAILED_LOGINS_GLOBAL:
            raise_custom_error(HTTPCodes.TOO_MANY_REQUESTS, CustomMessages.too_many_attempts)

        # Evaluate both so a wrong username costs the same as a wrong password.
        username_ok = _matches(body.username.strip().lower(), settings.admin_username.strip().lower())
        password_ok = _matches(body.password, settings.admin_password)
        if not (username_ok and password_ok):
            now = time.monotonic()
            attempts.append(now)
            everyone.append(now)
            logging.warning("Admin login failed from %s (%s recent failures)", client_ip, len(attempts))
            raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.invalid_credentials)

        attempts.clear()
        token, expires_in = create_access_token(AuthConstants.ADMIN_SUBJECT, credentials_version())
        logging.info("Admin login success from %s", client_ip)
        return LoginResult(access_token=token, expires_in=expires_in, admin=AdminPublic(username=settings.admin_username))
