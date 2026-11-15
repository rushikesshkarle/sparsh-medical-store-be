import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

# Load .env for local development. In Docker the values come from env_file (.env)
# via docker-compose, so this is a no-op there.
load_dotenv()


def _split_csv(value: str) -> list[str]:
    """Split a comma-separated env value into trimmed, non-empty items."""
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


def _parse_cloudinary_url(value: str) -> tuple[str, str, str]:
    """Split ``cloudinary://key:secret@cloud`` into (key, secret, cloud); blanks if unset/invalid."""
    parsed = urlparse(value.strip())
    if parsed.scheme != "cloudinary" or not parsed.hostname:
        return "", "", ""
    return unquote(parsed.username or ""), unquote(parsed.password or ""), parsed.hostname


class Settings:
    """Application configuration, read from environment variables.

    Plain ``os.getenv`` access, one attribute per variable. Every secret has an
    unsafe dev default; ``validate_for_production`` refuses to start with them
    when ``APP_ENV=production``.
    """

    def __init__(self) -> None:
        """Load database, auth, CORS and media settings from the environment."""
        self.app_env = os.getenv("APP_ENV", "development").lower()

        # MongoDB — product catalogue.
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.mongo_db = os.getenv("MONGO_DB", "sparsh-medical")

        # JWT — issued to the admin after a username/password login.
        self.jwt_secret_key = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))

        # The one admin account. Customers have no accounts (they shop as guests).
        # Empty password = admin login disabled.
        self.admin_username = os.getenv("ADMIN_USERNAME", "admin").strip()
        self.admin_password = os.getenv("ADMIN_PASSWORD", "")

        # CORS — browser origins allowed to call the API (comma-separated).
        self.cors_allow_origins = os.getenv(
            "CORS_ALLOW_ORIGINS", "http://localhost:5173,http://localhost:8080"
        )

        # Product images — stored on disk under MEDIA_DIR and served at /media.
        # In Docker this is a named volume so uploads survive a redeploy.
        self.media_dir = Path(os.getenv("MEDIA_DIR", "media")).resolve()
        self.max_image_size_mb = int(os.getenv("MAX_IMAGE_SIZE_MB", "5"))

        # Cloudinary — when all three are set, product images are stored there
        # (needed on hosts whose disk is wiped on restart, e.g. Render free).
        # Unset = images stay on local disk under MEDIA_DIR. Either set
        # CLOUDINARY_URL (cloudinary://<api_key>:<api_secret>@<cloud_name>, as the
        # dashboard shows it) or the three separate variables (these win).
        url_key, url_secret, url_cloud = _parse_cloudinary_url(os.getenv("CLOUDINARY_URL", ""))
        self.cloudinary_cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip() or url_cloud
        self.cloudinary_api_key = os.getenv("CLOUDINARY_API_KEY", "").strip() or url_key
        self.cloudinary_api_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip() or url_secret
        self.cloudinary_folder = os.getenv("CLOUDINARY_FOLDER", "sparsh-medical/products").strip("/ ")

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
    def use_cloudinary(self) -> bool:
        """Return True when Cloudinary credentials are configured."""
        return bool(self.cloudinary_cloud_name and self.cloudinary_api_key and self.cloudinary_api_secret)

    @property
    def max_image_size_bytes(self) -> int:
        """Return the upload limit for one product image, in bytes."""
        return self.max_image_size_mb * 1024 * 1024

    def validate_for_production(self) -> None:
        """Fail fast when production is started with a dev-only secret or a weak admin password.

        Raises:
            RuntimeError: If ``JWT_SECRET_KEY`` is the default or shorter than 32
                characters, or ``ADMIN_PASSWORD`` is shorter than 12 characters.
        """
        if not self.is_production:
            return
        if self.jwt_secret_key == "change-me-in-production" or len(self.jwt_secret_key) < 32:
            raise RuntimeError(
                "JWT_SECRET_KEY must be set to a random value of at least 32 characters in production"
            )
        if len(self.admin_password) < 12:
            raise RuntimeError("ADMIN_PASSWORD must be set to at least 12 characters in production")


# Singleton instance used across the app.
settings = Settings()
