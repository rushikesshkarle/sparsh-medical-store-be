"""Product image storage: Cloudinary when configured, else local disk (``MEDIA_DIR``).

Images are validated by decoding them with Pillow — the client's filename and
Content-Type are never trusted — then resized (longest side ``MAX_DIMENSION``)
and re-encoded as WebP before they are stored under a random name.

A product's stored ``image`` value is either a local path relative to
``MEDIA_DIR`` (``products/<hex>.webp``, served at ``/media``) or a Cloudinary
reference (``cloudinary:<public_id>``). Both kinds keep working side by side.
"""

import asyncio
import hashlib
import io
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

import requests
from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings
from app.shared.constants import HTTPCodes, ImageConstants
from app.shared.custom_error import raise_custom_error
from app.shared.custom_messages import CustomMessages

Image.MAX_IMAGE_PIXELS = ImageConstants.MAX_PIXELS


def _cloudinary_signature(params: dict) -> str:
    """Sign upload/destroy params as Cloudinary requires (sorted, SHA-1 with the secret)."""
    to_sign = "&".join(f"{key}={params[key]}" for key in sorted(params))
    return hashlib.sha1(f"{to_sign}{settings.cloudinary_api_secret}".encode()).hexdigest()


class ImageService:
    def __init__(self) -> None:
        self.upload_dir: Path = settings.media_dir / ImageConstants.UPLOAD_SUBDIR

    async def save(self, upload: UploadFile) -> str:
        """Validate, compress and store an uploaded image.

        Returns:
            str: The stored reference — ``products/<hex>.webp`` on disk or
            ``cloudinary:<public_id>`` on Cloudinary.

        Raises:
            HTTPException: 413 if too large, 415 if not an allowed image, 500 if storing fails.
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
        self._validate(data)
        webp = await asyncio.to_thread(self._compress, data)
        name = uuid.uuid4().hex

        if settings.use_cloudinary:
            return await self._upload_to_cloudinary(webp, name)

        relative = f"{ImageConstants.UPLOAD_SUBDIR}/{name}.{ImageConstants.STORED_EXTENSION}"
        try:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            (settings.media_dir / relative).write_bytes(webp)
        except OSError:
            logging.exception("Failed to write product image")
            raise_custom_error(HTTPCodes.INTERNAL_SERVER_ERROR, CustomMessages.image_save_failed)
        return relative

    def delete(self, stored: Optional[str]) -> None:
        """Remove a stored image. Failures are logged, never raised (the product change already succeeded)."""
        if not stored:
            return
        if stored.startswith(ImageConstants.CLOUDINARY_PREFIX):
            public_id = stored.removeprefix(ImageConstants.CLOUDINARY_PREFIX)
            try:
                # A network call: run it in a worker thread so the request isn't held up.
                asyncio.get_running_loop().run_in_executor(None, self._delete_from_cloudinary, public_id)
            except RuntimeError:  # no event loop (e.g. a script) — just do it inline
                self._delete_from_cloudinary(public_id)
            return
        target = (settings.media_dir / stored).resolve()
        if settings.media_dir not in target.parents:
            logging.warning("Refusing to delete image outside MEDIA_DIR: %s", stored)
            return
        try:
            target.unlink(missing_ok=True)
        except OSError:
            logging.exception("Failed to delete product image %s", stored)

    @staticmethod
    def public_url(stored: Optional[str]) -> Optional[str]:
        """Return the URL a browser loads the image from."""
        if not stored:
            return None
        if stored.startswith(ImageConstants.CLOUDINARY_PREFIX):
            return ImageConstants.CLOUDINARY_DELIVERY.format(
                cloud=settings.cloudinary_cloud_name,
                public_id=stored.removeprefix(ImageConstants.CLOUDINARY_PREFIX),
            )
        return f"{settings.public_base_url}{ImageConstants.MEDIA_URL_PREFIX}/{stored}"

    # ---- helpers -------------------------------------------------------------

    @staticmethod
    def _validate(data: bytes) -> None:
        """Decode ``data`` as an image of an allowed format, or raise 415."""
        try:
            with Image.open(io.BytesIO(data)) as img:
                img.verify()
                image_format = img.format
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
            raise_custom_error(HTTPCodes.UNSUPPORTED_MEDIA_TYPE, CustomMessages.image_invalid)
        if (image_format or "") not in ImageConstants.ALLOWED_FORMATS:
            raise_custom_error(HTTPCodes.UNSUPPORTED_MEDIA_TYPE, CustomMessages.image_invalid)

    @staticmethod
    def _compress(data: bytes) -> bytes:
        """Fix rotation, cap the longest side and re-encode as WebP (first frame of a GIF)."""
        try:
            with Image.open(io.BytesIO(data)) as img:
                img = ImageOps.exif_transpose(img)
                img.thumbnail((ImageConstants.MAX_DIMENSION, ImageConstants.MAX_DIMENSION))
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA" if "transparency" in img.info or img.mode in ("LA", "PA") else "RGB")
                out = io.BytesIO()
                img.save(out, format="WEBP", quality=ImageConstants.WEBP_QUALITY, method=4)
                return out.getvalue()
        except (OSError, ValueError, Image.DecompressionBombError):
            raise_custom_error(HTTPCodes.UNSUPPORTED_MEDIA_TYPE, CustomMessages.image_invalid)

    async def _upload_to_cloudinary(self, webp: bytes, name: str) -> str:
        """Signed upload to Cloudinary; returns ``cloudinary:<public_id>``."""
        params = {"folder": settings.cloudinary_folder, "public_id": name, "timestamp": int(time.time())}
        form = {**params, "api_key": settings.cloudinary_api_key, "signature": _cloudinary_signature(params)}
        url = f"{ImageConstants.CLOUDINARY_API}/{settings.cloudinary_cloud_name}/image/upload"

        def _post() -> requests.Response:
            return requests.post(
                url,
                data=form,
                files={"file": (f"{name}.webp", webp, "image/webp")},
                timeout=ImageConstants.CLOUDINARY_TIMEOUT_SECONDS,
            )

        try:
            response = await asyncio.to_thread(_post)
        except requests.RequestException as exc:
            logging.error("Cloudinary upload failed: %s", type(exc).__name__)
            raise_custom_error(HTTPCodes.INTERNAL_SERVER_ERROR, CustomMessages.image_save_failed)
        if response.status_code != 200:
            logging.error("Cloudinary upload rejected (status=%s): %s", response.status_code, response.text[:300])
            raise_custom_error(HTTPCodes.INTERNAL_SERVER_ERROR, CustomMessages.image_save_failed)
        return f"{ImageConstants.CLOUDINARY_PREFIX}{response.json()['public_id']}"

    @staticmethod
    def _delete_from_cloudinary(public_id: str) -> None:
        """Best-effort delete; a leftover image only costs a little storage."""
        if not settings.use_cloudinary:
            logging.warning("Cloudinary not configured; cannot delete %s", public_id)
            return
        params = {"public_id": public_id, "timestamp": int(time.time())}
        form = {**params, "api_key": settings.cloudinary_api_key, "signature": _cloudinary_signature(params)}
        try:
            response = requests.post(
                f"{ImageConstants.CLOUDINARY_API}/{settings.cloudinary_cloud_name}/image/destroy",
                data=form,
                timeout=ImageConstants.CLOUDINARY_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                logging.warning("Cloudinary delete of %s failed (status=%s)", public_id, response.status_code)
        except requests.RequestException as exc:
            logging.warning("Cloudinary delete of %s failed: %s", public_id, type(exc).__name__)
