"""Safe image upload validation."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.domain.errors import ImageTooLargeError, InvalidImageError

_ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "HEIC", "HEIF"}


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
                if image.format not in _ALLOWED_FORMATS:
                    raise InvalidImageError(
                        "The file contents do not match a supported image format."
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
        except (UnidentifiedImageError, OSError, ValueError) as error:
            raise InvalidImageError("The uploaded file is not a readable image.") from error
        return payload
