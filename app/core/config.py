import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env for local development. In Docker the values come from env_file (.env)
# via docker-compose, so this is a no-op there.
load_dotenv()


def _split_csv(value: str) -> list[str]:
    """Split a comma-separated env value into trimmed, non-empty items."""
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


class Settings:
    """Application configuration, read from environment variables.

    Plain ``os.getenv`` access, one attribute per variable. Every secret has an
    unsafe dev default; ``validate_for_production`` refuses to start with them
    when ``APP_ENV=production``.
    """

    def __init__(self) -> None:
        """Load database, auth, CORS and media settings from the environment."""
        self.app_env = os.getenv("APP_ENV", "development").lower()

        # MongoDB — product catalogue and user accounts.
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.mongo_db = os.getenv("MONGO_DB", "sparsh-medical")

        # JWT — issued by this API after a successful Google sign-in.
        self.jwt_secret_key = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))

        # Google OAuth (popup/auth-code flow). The client id must match the
        # frontend's VITE_GOOGLE_CLIENT_ID; the secret never leaves the backend.
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

        # Emails that get the admin dashboard (comma-separated). Anyone else who
        # signs in with Google is a normal customer. Empty = nobody is admin.
        self.allowed_admin_emails = os.getenv("ALLOWED_ADMIN_EMAILS", "")

        # CORS — browser origins allowed to call the API (comma-separated).
        self.cors_allow_origins = os.getenv(
            "CORS_ALLOW_ORIGINS", "http://localhost:5173,http://localhost:8080"
        )

        # Product images — stored on disk under MEDIA_DIR and served at /media.
        # In Docker this is a named volume so uploads survive a redeploy.
        self.media_dir = Path(os.getenv("MEDIA_DIR", "media")).resolve()
        self.max_image_size_mb = int(os.getenv("MAX_IMAGE_SIZE_MB", "5"))

        # Public base URL of this API, used to build absolute image URLs. Empty =
        # relative URLs (``/media/...``), fine when the frontend proxies /media.
        self.public_base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

    @property
    def is_production(self) -> bool:
        """Return True when running with ``APP_ENV=production``."""
        return self.app_env == "production"

    @property
    def cors_allow_origins_list(self) -> list[str]:
        """Return the CORS-allowed browser origins."""
        return _split_csv(self.cors_allow_origins)

    @property
    def allowed_admin_emails_set(self) -> set[str]:
        """Return the admin allowlist, lower-cased for case-insensitive matching."""
        return {email.lower() for email in _split_csv(self.allowed_admin_emails)}

    @property
    def max_image_size_bytes(self) -> int:
        """Return the upload limit for one product image, in bytes."""
        return self.max_image_size_mb * 1024 * 1024

    def validate_for_production(self) -> None:
        """Fail fast when production is started with a dev-only secret or no Google client.

        Raises:
            RuntimeError: If ``JWT_SECRET_KEY`` is the default or shorter than 32
                characters, or Google OAuth is not configured.
        """
        if not self.is_production:
            return
        if self.jwt_secret_key == "change-me-in-production" or len(self.jwt_secret_key) < 32:
            raise RuntimeError(
                "JWT_SECRET_KEY must be set to a random value of at least 32 characters in production"
            )
        if not self.google_client_id or not self.google_client_secret:
            raise RuntimeError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in production")


# Singleton instance used across the app.
settings = Settings()
