class GlobalConstants:
    log_file_path = "app.log"
    # Reported by ``GET /health`` and as the OpenAPI version.
    app_version = "1.1.0"


class HealthConstants:
    """Verdicts reported by ``GET /health``."""

    STATUS_UP = "up"
    STATUS_DOWN = "down"
    STATUS_HEALTHY = "healthy"
    STATUS_DEGRADED = "degraded"
    LATENCY_DECIMALS = 2


class CollectionNames:
    PRODUCTS = "products"


class AuthConstants:
    """Admin login rules."""

    # JWT subject for the single admin account.
    ADMIN_SUBJECT = "admin"
    # Brute-force throttle: this many failed logins per IP within the window → 429.
    MAX_FAILED_LOGINS = 5
    # Across ALL IPs (client IPs can be spoofed via X-Forwarded-For): this many → 429.
    MAX_FAILED_LOGINS_GLOBAL = 30
    LOGIN_WINDOW_SECONDS = 15 * 60


class ProductConstants:
    """Rules a product must follow, enforced on create and update."""

    NAME_MAX_LENGTH = 200
    CATEGORY_MAX_LENGTH = 100
    DESCRIPTION_MAX_LENGTH = 5000
    # Same bound as the Django model: DecimalField(max_digits=10, decimal_places=2).
    PRICE_MAX = 99_999_999.99
    SEARCH_MAX_LENGTH = 100

    # Categories shown on the storefront's "Shop by Category" cards. A product's
    # category is free text (as in the Django model); these are the suggestions.
    SUGGESTED_CATEGORIES = (
        "Medicines",
        "Vitamins",
        "Personal Care",
        "Hair Care",
        "Healthcare",
    )

    DEFAULT_PAGE_SIZE = 24
    MAX_PAGE_SIZE = 100

    # Public storefront listings/categories are cached this long per worker.
    PUBLIC_CACHE_TTL_SECONDS = 60
    PUBLIC_CACHE_MAX_ENTRIES = 500

    # At or below this stock (and above 0) a product counts as "low stock".
    LOW_STOCK_THRESHOLD = 5


class ProductSort:
    """Sort orders for product listings (``?sort=``)."""

    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"


class ProductStatus:
    """Admin listing filter (``?status=``)."""

    ALL = "all"
    LIVE = "live"
    HIDDEN = "hidden"
    LOW_STOCK = "low_stock"


class ImageConstants:
    """Accepted product image formats (checked by decoding, not by extension)."""

    # Pillow format name → file extension written to disk.
    ALLOWED_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif"}
    UPLOAD_SUBDIR = "products"
    MEDIA_URL_PREFIX = "/media"
    # Reject decompression bombs before Pillow allocates the pixels.
    MAX_PIXELS = 40_000_000

    # Every upload is re-encoded: longest side capped, saved as WebP. Keeps
    # storage and (on Cloudinary's free plan) bandwidth credits low.
    MAX_DIMENSION = 1200
    WEBP_QUALITY = 82
    STORED_EXTENSION = "webp"

    # Stored image reference prefix for Cloudinary-hosted images.
    CLOUDINARY_PREFIX = "cloudinary:"
    CLOUDINARY_API = "https://api.cloudinary.com/v1_1"
    # f_auto/q_auto: Cloudinary serves WebP/AVIF at an automatic quality.
    CLOUDINARY_DELIVERY = "https://res.cloudinary.com/{cloud}/image/upload/f_auto,q_auto/{public_id}"
    CLOUDINARY_TIMEOUT_SECONDS = 30


class HTTPCodes:
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    REQUEST_ENTITY_TOO_LARGE = 413
    UNSUPPORTED_MEDIA_TYPE = 415
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503
