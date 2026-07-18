"""Errors that describe expected recognition failures."""


class RecognitionError(Exception):
    """Base class for safe, user-facing recognition failures."""

    code = "recognition_failed"


class InvalidImageError(RecognitionError):
    """Raised when an upload is not a valid supported image."""

    code = "invalid_image"


class ImageTooLargeError(RecognitionError):
    """Raised when an image exceeds the configured byte or pixel limit."""

    code = "image_too_large"


class BlurryImageError(RecognitionError):
    """Raised when the card is too blurry for a safe identification."""

    code = "image_too_blurry"


class CardNotFoundError(RecognitionError):
    """Raised when no card-shaped subject can be localized."""

    code = "card_not_found"


class MultipleCardsError(RecognitionError):
    """Raised when the image contains more than one likely card."""

    code = "multiple_cards"


class RecognitionUnavailableError(RecognitionError):
    """Raised when required local model artifacts are unavailable."""

    code = "recognition_unavailable"
