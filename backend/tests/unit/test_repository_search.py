import numpy as np
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.infrastructure.database.models import Base, CardRecord
from app.infrastructure.database.repositories import SqlAlchemyCardRepository
from app.infrastructure.models.composite_artwork import VisualFeatures
from app.infrastructure.models.visual_index import CatalogVisualCandidateFinder


def _record(card_id: str, name: str, embedding: tuple[float, float]) -> CardRecord:
    return CardRecord(
        id=card_id,
        name=name,
        normalized_name=name.casefold(),
        collector_number="25",
        normalized_collector_number="25",
        printed_total="198",
        source="tcgdex",
        source_card_id=card_id,
        set_id="test",
        set_name="Test Set",
        rarity=None,
        language="English",
        reference_image_url=f"https://example.com/{card_id}.webp",
        marketplace_id=None,
        marketplace_url=None,
        reference_asset=None,
        perceptual_hash="0123456789abcdef" if card_id == "pikachu" else "ffffffffffffffff",
        orb_descriptors=None,
        visual_embedding=np.asarray(embedding, dtype=np.float32).tobytes(),
    )


async def _repository():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        session.add_all(
            [
                _record("pikachu", "Pikachu", (1.0, 0.0)),
                _record("charizard", "Charizard", (0.0, 1.0)),
            ]
        )
        await session.commit()
    return engine, sessions, SqlAlchemyCardRepository(sessions)


async def test_repository_fuzzy_name_fallback_survives_one_bad_ocr_character() -> None:
    engine, _sessions, repository = await _repository()
    try:
        cards = await repository.search(
            normalized_name="pikachv",
            collector_number=None,
            limit=8,
        )
    finally:
        await engine.dispose()

    assert cards
    assert cards[0].id == "pikachu"


class _VisualMatcher:
    def features(self, _card_jpeg: bytes) -> VisualFeatures:
        return VisualFeatures(
            perceptual_hash="0123456789abcdef",
            orb_descriptors=None,
            embedding=(1.0, 0.0),
        )


async def test_global_visual_index_finds_a_card_when_ocr_has_no_candidates() -> None:
    engine, sessions, repository = await _repository()
    try:
        finder = CatalogVisualCandidateFinder(sessions, repository, _VisualMatcher())  # type: ignore[arg-type]
        cards = await finder.search(b"scan", limit=1)
    finally:
        await engine.dispose()

    assert [card.id for card in cards] == ["pikachu"]
