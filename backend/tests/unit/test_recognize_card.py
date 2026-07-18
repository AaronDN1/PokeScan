from app.application.confidence import WeightedConfidenceEngine
from app.application.recognize_card import RecognizeCard
from app.domain.models import Card, NormalizedCardImage, OcrReading, Price, RecognitionStatus


class Validator:
    def validate(self, payload: bytes, declared_mime: str) -> bytes:
        assert declared_mime == "image/jpeg"
        return payload


class Locator:
    def normalize(self, payload: bytes) -> NormalizedCardImage:
        return NormalizedCardImage(744, 1039, payload, b"top", b"bottom", b"art", 100.0)


class Ocr:
    def read_name(self, region_jpeg: bytes) -> OcrReading:
        return OcrReading("Pikachu ex", 0.98)

    def read_collector_number(self, region_jpeg: bytes) -> OcrReading:
        return OcrReading("057/182", 0.99)


class Cards:
    card = Card(
        id="sv-test-057",
        name="Pikachu ex",
        normalized_name="pikachu ex",
        collector_number="57",
        printed_total="182",
        set_name="Test Set",
        rarity="Double Rare",
        language="English",
        image_url="https://example.com/card.webp",
        marketplace_url="https://example.com/marketplace",
        visual_embedding=(0.1, 0.2),
    )

    async def search(self, **_kwargs):
        return [self.card]

    async def get(self, card_id: str):
        return self.card if card_id == self.card.id else None


class Artwork:
    def score(self, artwork_jpeg: bytes, card: Card) -> float:
        return 0.98


class Prices:
    async def get_price(self, card: Card) -> Price:
        return Price(42.5, source="fixture")


async def test_pipeline_returns_only_a_verified_high_confidence_match() -> None:
    use_case = RecognizeCard(
        validator=Validator(),
        locator=Locator(),
        ocr=Ocr(),
        cards=Cards(),
        artwork=Artwork(),
        prices=Prices(),
        confidence=WeightedConfidenceEngine(),
    )
    result = await use_case.execute(payload=b"image", declared_mime="image/jpeg")
    assert result.status is RecognitionStatus.MATCHED
    assert result.card is not None
    assert result.card.id == "sv-test-057"
    assert result.price.amount == 42.5
    assert result.confidence >= 0.82
