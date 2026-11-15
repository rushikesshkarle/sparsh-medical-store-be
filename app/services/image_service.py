"""Product image storage on local disk (``MEDIA_DIR``), served at ``/media``.

Images are validated by decoding them with Pillow — the client's filename and
Content-Type are never trusted — and saved under a random name.
"""

import io
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.shared.constants import HTTPCodes, ImageConstants
from app.shared.custom_error import raise_custom_error
from app.shared.custom_messages import CustomMessages

Image.MAX_IMAGE_PIXELS = ImageConstants.MAX_PIXELS


class ImageService:
    def __init__(self) -> None:
        self.upload_dir: Path = settings.media_dir / ImageConstants.UPLOAD_SUBDIR

    async def save(self, upload: UploadFile) -> str:
        """Validate and store an uploaded image.

        Returns:
            str: The stored path relative to ``MEDIA_DIR`` (e.g. ``products/<uuid>.webp``).

        Raises:
            HTTPException: 413 if too large, 415 if not an allowed image, 500 if the write fails.
        """
        # Read one byte past the limit so an oversized file is detected without
        # buffering all of it.
        data = await upload.read(settings.max_image_size_bytes + 1)
        if len(data) > settings.max_image_size_bytes:
            raise_custom_error(
                HTTPCodes.REQUEST_ENTITY_TOO_LARGE,
                CustomMessages.image_too_large,
                f"Maximum size is {settings.max_image_size_mb} MB",
            )

        extension = self._detect_extension(data)
        relative = f"{ImageConstants.UPLOAD_SUBDIR}/{uuid.uuid4().hex}.{extension}"
        try:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            (settings.media_dir / relative).write_bytes(data)
        except OSError:
            logging.exception("Failed to write product image")
            raise_custom_error(HTTPCodes.INTERNAL_SERVER_ERROR, CustomMessages.image_save_failed)
        return relative

    def delete(self, relative: Optional[str]) -> None:
        """Remove a stored image; missing files and paths outside MEDIA_DIR are ignored."""
        if not relative:
            return
        target = (settings.media_dir / relative).resolve()
        if settings.media_dir not in target.parents:
            logging.warning("Refusing to delete image outside MEDIA_DIR: %s", relative)
            return
        try:
            target.unlink(missing_ok=True)
        except OSError:
            logging.exception("Failed to delete product image %s", relative)

    @staticmethod
    def public_url(relative: Optional[str]) -> Optional[str]:
        """Return the URL a browser loads the image from."""
        if not relative:
            return None
        return f"{settings.public_base_url}{ImageConstants.MEDIA_URL_PREFIX}/{relative}"

    @staticmethod
    def _detect_extension(data: bytes) -> str:
        """Decode ``data`` as an image and return its extension, or raise 415."""
        try:
            with Image.open(io.BytesIO(data)) as img:
                img.verify()
                image_format = img.format
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
            raise_custom_error(HTTPCodes.UNSUPPORTED_MEDIA_TYPE, CustomMessages.image_invalid)
        extension = ImageConstants.ALLOWED_FORMATS.get(image_format or "")
        if not extension:
            raise_custom_error(HTTPCodes.UNSUPPORTED_MEDIA_TYPE, CustomMessages.image_invalid)
        return extension
