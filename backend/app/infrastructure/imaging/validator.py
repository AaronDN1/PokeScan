"""Safe image upload validation."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

from app.domain.errors import ImageTooLargeError, InvalidImageError

register_heif_opener(thumbnails=False)

_ALLOWED_MIME_TYPES = {
    "application/octet-stream",
    "image/heic",
    "image/heif",
    "image/jpeg",
    "image/jpg",
    "image/mpo",
    "image/pjpeg",
    "image/png",
    "image/webp",
    "image/x-png",
}
_ALLOWED_FORMATS = {"HEIF", "JPEG", "MPO", "PNG", "WEBP"}


class PillowImageValidator:
    """Reject oversized, malformed, and mislabeled uploads before OpenCV."""

    def __init__(self, *, max_bytes: int, max_pixels: int) -> None:
        self._max_bytes = max_bytes
        self._max_pixels = max_pixels

    def validate(self, payload: bytes, declared_mime: str) -> bytes:
        """Validate magic bytes and dimensions without retaining the upload."""
        if not payload or declared_mime.lower() not in _ALLOWED_MIME_TYPES:
            raise InvalidImageError("Choose a JPEG, PNG, WebP, or HEIC image.")
        if len(payload) > self._max_bytes:
            raise ImageTooLargeError("The photo exceeds the 12 MB upload limit.")

        try:
            with Image.open(BytesIO(payload)) as image:
                detected_format = image.format
                if detected_format not in _ALLOWED_FORMATS:
                    raise InvalidImageError(
                        f"This {detected_format or 'unknown'} image is not supported. "
                        "Choose a JPEG, PNG, WebP, HEIC, HEIF, or MPO photo."
                    )
                width, height = image.size
                if width < 320 or height < 320:
                    raise InvalidImageError(
                        "The photo is too small. Use an image at least 320 pixels wide."
                    )
                if width * height > self._max_pixels:
                    raise ImageTooLargeError(
                        "The photo dimensions are too large to process safely."
                    )
                image.verify()
            if detected_format == "HEIF":
                with Image.open(BytesIO(payload)) as image:
                    image.seek(0)
                    transposed = ImageOps.exif_transpose(image)
                    if transposed is None:
                        raise InvalidImageError("The uploaded image orientation is invalid.")
                    normalized = transposed.convert("RGB")
                    encoded = BytesIO()
                    normalized.save(encoded, format="JPEG", quality=95, optimize=True)
                return encoded.getvalue()
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as error:
            raise InvalidImageError("The uploaded file is not a readable image.") from error
        return payload
