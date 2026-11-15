"""Google sign-in: trade a popup authorization code for a verified Google identity."""

import asyncio
import logging

import requests
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import settings
from app.models.auth_model import GoogleUserInfo
from app.shared.constants import AuthConstants, HTTPCodes
from app.shared.custom_error import raise_custom_error
from app.shared.custom_messages import CustomMessages

# Reused across logins; google-auth caches Google's signing keys on it.
_google_request = google_requests.Request()


class GoogleOAuthService:
    """Exchange a GIS popup code for an ID token and verify it.

    The frontend opens Google's popup (auth-code flow) and sends us the code.
    We exchange it with our client secret (``redirect_uri="postmessage"``, so no
    redirect URIs are registered in the Google console), then verify the ID
    token's signature, audience, expiry, issuer and ``email_verified``.
    """

    def _require_config(self) -> None:
        if not settings.google_client_id or not settings.google_client_secret:
            raise_custom_error(HTTPCodes.SERVICE_UNAVAILABLE, CustomMessages.oauth_not_configured)

    async def exchange_code(self, code: str) -> str:
        """Exchange an authorization code for a Google ID token.

        Raises:
            HTTPException: 503 if OAuth is not configured; 401 if Google rejects the code.
        """
        self._require_config()

        def _post() -> requests.Response:
            return requests.post(
                AuthConstants.GOOGLE_TOKEN_URI,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": AuthConstants.POPUP_REDIRECT_URI,
                },
                timeout=AuthConstants.TOKEN_EXCHANGE_TIMEOUT_SECONDS,
            )

        try:
            response = await asyncio.to_thread(_post)
        except requests.RequestException as exc:
            logging.warning("Google token endpoint unreachable: %s", type(exc).__name__)
            raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.google_code_exchange_failed)

        if response.status_code != 200:
            # Google's error code (e.g. invalid_grant, redirect_uri_mismatch) is not
            # secret and is what makes a failed sign-in diagnosable.
            try:
                reason = str(response.json().get("error", "unknown"))[:64]
            except ValueError:
                reason = "unknown"
            logging.warning("Google code exchange rejected (status=%s, error=%s)", response.status_code, reason)
            raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.google_code_exchange_failed, error=reason)

        token = response.json().get("id_token")
        if not token:
            raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.google_code_exchange_failed)
        return token

    async def verify_id_token(self, token: str) -> GoogleUserInfo:
        """Verify a Google ID token and return the signed-in person's profile.

        Raises:
            HTTPException: 401 on a bad/expired token, wrong audience or issuer,
                an unverified email, or missing claims.
        """
        self._require_config()
        try:
            # Blocking network call (fetches Google's keys) — keep it off the event loop.
            claims = await asyncio.to_thread(
                google_id_token.verify_oauth2_token, token, _google_request, settings.google_client_id
            )
        except ValueError as exc:
            logging.warning("Google ID token rejected: %s", str(exc)[:200])
            raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.invalid_google_token, error=str(exc)[:120])
        except Exception:  # noqa: BLE001 — any library failure is a failed sign-in
            logging.exception("Google token verification failed unexpectedly")
            raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.invalid_google_token)

        if claims.get("iss") not in AuthConstants.ALLOWED_ISSUERS:
            raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.unexpected_token_issuer)
        if not claims.get("email_verified", False):
            raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.email_not_verified)
        if not claims.get("email") or not claims.get("sub"):
            raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.google_payload_missing)

        return GoogleUserInfo(
            sub=claims["sub"],
            email=claims["email"].lower(),
            name=claims.get("name", ""),
            picture=claims.get("picture", ""),
        )
