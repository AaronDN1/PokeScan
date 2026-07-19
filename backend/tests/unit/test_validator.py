import io

import pytest
from PIL import Image

from app.domain.errors import ImageTooLargeError, InvalidImageError
from app.infrastructure.imaging.validator import PillowImageValidator


def _image() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (400, 400), "white").save(buffer, format="JPEG")
    return buffer.getvalue()


def _mpo_image() -> bytes:
    buffer = io.BytesIO()
    first = Image.new("RGB", (400, 400), "white")
    second = Image.new("RGB", (400, 400), "black")
    first.save(buffer, format="MPO", save_all=True, append_images=[second])
    return buffer.getvalue()


def test_rejects_unsupported_declared_image_type() -> None:
    validator = PillowImageValidator(max_bytes=1_000_000, max_pixels=1_000_000)
    with pytest.raises(InvalidImageError):
        validator.validate(_image(), "application/pdf")


def test_rejects_oversized_image_bytes() -> None:
    payload = _image()
    validator = PillowImageValidator(max_bytes=len(payload) - 1, max_pixels=1_000_000)
    with pytest.raises(ImageTooLargeError):
        validator.validate(payload, "image/jpeg")


def test_accepts_phone_camera_mpo_without_recompressing_it() -> None:
    validator = PillowImageValidator(max_bytes=1_000_000, max_pixels=1_000_000)
    payload = _mpo_image()
    normalized = validator.validate(payload, "image/jpeg")

    assert normalized == payload
    with Image.open(io.BytesIO(normalized)) as image:
        assert image.format == "MPO"
        assert image.size == (400, 400)


def test_converts_heif_to_opencv_compatible_jpeg() -> None:
    payload = io.BytesIO()
    Image.new("RGB", (400, 400), "white").save(payload, format="HEIF")
    validator = PillowImageValidator(max_bytes=1_000_000, max_pixels=1_000_000)

    normalized = validator.validate(payload.getvalue(), "image/heic")

    with Image.open(io.BytesIO(normalized)) as image:
        assert image.format == "JPEG"
        assert image.size == (400, 400)


def test_accepts_missing_browser_mime_when_contents_are_valid() -> None:
    validator = PillowImageValidator(max_bytes=1_000_000, max_pixels=1_000_000)
    normalized = validator.validate(_image(), "application/octet-stream")

    assert normalized.startswith(b"\xff\xd8\xff")
