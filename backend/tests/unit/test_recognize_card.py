from app.application.confidence import WeightedConfidenceEngine
from app.application.recognize_card import RecognizeCard
from app.domain.models import (
    ArtworkEvidence,
    Card,
    NormalizedCardImage,
    OcrReading,
    OrientationResult,
    Price,
    RecognitionStatus,
)


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


class Orientation:
    def resolve(self, image: NormalizedCardImage) -> OrientationResult:
        return OrientationResult(
            image=image,
            name=OcrReading("Pikachu ex", 0.98),
            collector_number=OcrReading("057/182", 0.99),
            score=0.99,
        )


class Cards:
    card = Card(
        id="sv-test-057",
        name="Pikachu ex",
        normalized_name="pikachu ex",
        collector_number="57",
        normalized_collector_number="57",
        printed_total="182",
        source="tcgdex",
        source_card_id="sv-test-057",
        set_id="sv-test",
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

    def score_many(self, artwork_jpeg: bytes, cards: list[Card]):
        return {
            card.id: ArtworkEvidence(
                perceptual_hash_score=0.95,
                orb_score=0.97,
                embedding_score=0.96,
                combined_score=0.98,
            )
            for card in cards
        }


class VisualCandidates:
    async def search(self, card_jpeg: bytes, *, limit: int):
        assert card_jpeg == b"image"
        assert limit == 8
        return [Cards.card]


class Prices:
    async def get_price(self, card: Card) -> Price:
        return Price(42.5, source="fixture")


async def test_pipeline_returns_only_a_verified_high_confidence_match() -> None:
    use_case = RecognizeCard(
        validator=Validator(),
        locator=Locator(),
        orientation=Orientation(),
        cards=Cards(),
        visual_candidates=VisualCandidates(),
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


class EmptyCards(Cards):
    async def search(self, **_kwargs):
        return []


class EmptyOrientation(Orientation):
    def resolve(self, image: NormalizedCardImage) -> OrientationResult:
        return OrientationResult(
            image=image,
            name=OcrReading("", 0.0),
            collector_number=OcrReading("", 0.0),
            score=0.0,
        )


async def test_pipeline_can_match_from_a_clear_global_visual_fallback() -> None:
    use_case = RecognizeCard(
        validator=Validator(),
        locator=Locator(),
        orientation=EmptyOrientation(),
        cards=EmptyCards(),
        visual_candidates=VisualCandidates(),
        artwork=Artwork(),
        prices=Prices(),
        confidence=WeightedConfidenceEngine(),
    )

    result = await use_case.execute(payload=b"image", declared_mime="image/jpeg")

    assert result.status is RecognitionStatus.MATCHED
    assert result.card is not None
    assert result.card.id == Cards.card.id
