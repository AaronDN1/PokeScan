"""Process-scoped vector and pHash shortlist over the local card catalog."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.models import Card
from app.infrastructure.database.models import CardRecord
from app.infrastructure.database.repositories import SqlAlchemyCardRepository
from app.infrastructure.models.composite_artwork import CompositeArtworkMatcher

FloatArray = NDArray[np.float32]
BoolArray = NDArray[np.bool_]


class CatalogVisualCandidateFinder:
    """Use vectorized coarse features to make OCR-independent retrieval bounded."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        cards: SqlAlchemyCardRepository,
        matcher: CompositeArtworkMatcher,
    ) -> None:
        self._sessions = sessions
        self._cards = cards
        self._matcher = matcher
        self._ids: tuple[str, ...] = ()
        self._hashes: tuple[int | None, ...] = ()
        self._embeddings: FloatArray | None = None
        self._embedding_mask: BoolArray | None = None
        self._loaded = False
        self._load_lock = asyncio.Lock()

    @property
    def indexed_count(self) -> int:
        """Return the number of catalog entries with at least one visual feature."""
        return len(self._ids)

    async def start(self) -> None:
        """Warm the visual index once so the first scan does not pay setup latency."""
        await self._ensure_loaded()

    async def search(self, card_jpeg: bytes, *, limit: int) -> Sequence[Card]:
        """Return top coarse visual candidates for exact candidate-only verification."""
        await self._ensure_loaded()
        if not self._ids or limit <= 0:
            return ()

        observed = self._matcher.features(card_jpeg)
        weighted = np.zeros(len(self._ids), dtype=np.float32)
        weights = np.zeros(len(self._ids), dtype=np.float32)

        if observed.embedding and self._embeddings is not None:
            query = np.asarray(observed.embedding, dtype=np.float32)
            if query.size == self._embeddings.shape[1]:
                similarities = np.clip((self._embeddings @ query + 1.0) / 2.0, 0.0, 1.0)
                mask = self._embedding_mask
                if mask is not None:
                    weighted[mask] += 0.82 * similarities[mask]
                    weights[mask] += 0.82

        try:
            observed_hash = int(observed.perceptual_hash, 16)
        except ValueError:
            observed_hash = -1
        if observed_hash >= 0:
            hash_scores = np.fromiter(
                (
                    1.0 - (observed_hash ^ expected).bit_count() / 64
                    if expected is not None
                    else 0.0
                    for expected in self._hashes
                ),
                dtype=np.float32,
                count=len(self._hashes),
            )
            hash_mask = np.fromiter(
                (item is not None for item in self._hashes),
                dtype=np.bool_,
                count=len(self._hashes),
            )
            weighted[hash_mask] += 0.18 * hash_scores[hash_mask]
            weights[hash_mask] += 0.18

        available = weights > 0
        if not bool(np.any(available)):
            return ()
        scores = np.full(len(self._ids), -1.0, dtype=np.float32)
        scores[available] = weighted[available] / weights[available]
        take = min(limit, int(np.count_nonzero(available)))
        if take <= 0:
            return ()
        indices = np.argpartition(scores, -take)[-take:]
        ordered = indices[np.argsort(scores[indices])[::-1]]
        return await self._cards.get_many([self._ids[int(index)] for index in ordered])

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        async with self._load_lock:
            if self._loaded:
                return
            statement = select(
                CardRecord.id,
                CardRecord.perceptual_hash,
                CardRecord.visual_embedding,
            ).where(
                or_(
                    CardRecord.perceptual_hash.is_not(None),
                    CardRecord.visual_embedding.is_not(None),
                )
            )
            async with self._sessions() as session:
                rows = (await session.execute(statement)).all()

            self._ids = tuple(str(row.id) for row in rows)
            parsed_hashes: list[int | None] = []
            dimension = next(
                (
                    len(row.visual_embedding) // 4
                    for row in rows
                    if row.visual_embedding and len(row.visual_embedding) % 4 == 0
                ),
                0,
            )
            embeddings = np.zeros((len(rows), dimension), dtype=np.float32)
            embedding_mask = np.zeros(len(rows), dtype=np.bool_)
            for index, row in enumerate(rows):
                try:
                    parsed_hashes.append(
                        int(row.perceptual_hash, 16) if row.perceptual_hash else None
                    )
                except ValueError:
                    parsed_hashes.append(None)
                if not row.visual_embedding or dimension == 0:
                    continue
                values = np.frombuffer(row.visual_embedding, dtype=np.float32)
                if values.size != dimension:
                    continue
                norm = float(np.linalg.norm(values))
                if norm <= 0:
                    continue
                embeddings[index] = values / norm
                embedding_mask[index] = True
            self._hashes = tuple(parsed_hashes)
            self._embeddings = embeddings if dimension else None
            self._embedding_mask = embedding_mask if dimension else None
            self._loaded = True
