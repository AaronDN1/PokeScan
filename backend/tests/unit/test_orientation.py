from app.domain.models import OcrReading
from app.infrastructure.imaging.orientation import OcrOrientationResolver


def test_orientation_prefers_a_card_title_over_flavor_text() -> None:
    title_score = OcrOrientationResolver._score(
        OcrReading("Pikachu", 0.91),
        OcrReading("", 0.0),
        portrait=True,
    )
    sentence_score = OcrOrientationResolver._score(
        OcrReading("Several of these Pokémon gather their electricity", 0.97),
        OcrReading("", 0.0),
        portrait=True,
    )

    assert title_score > sentence_score
