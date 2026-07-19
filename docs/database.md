# Database and catalog

SQLite is the local default at `backend/data/pokelens.db`; PostgreSQL is supported through the same async SQLAlchemy records.

Each card ID includes provider, language, set, and source card identity. Stored fields
include raw and normalized name/collector number, printed total, source/set IDs,
rarity/language, nullable marketplace mapping, reference asset, pHash, and float32
MobileNet embedding bytes. The normalized collector/name index drives bounded text
retrieval. The visual features are loaded into an in-memory matrix at startup; ORB
descriptors are produced lazily for the final shortlist. Legacy imported prices
live in `card_prices`; exact product mappings and TCGplayer condition-price cache
entries live in `tcgplayer_quotes`. Feedback never references image storage.

Catalog setup is deliberately offline:

```bash
python scripts/build_catalog.py --language en --output data/catalog-en.json
python scripts/prepare_catalog_assets.py data/catalog-en.json
python scripts/import_catalog.py data/catalog-en.json
```

The versioned JSON export can be imported into either SQLite or PostgreSQL. Isolated unavailable reference assets do not abort the entire build. Recognition never downloads catalog assets. Marketplace enrichment is a bounded, cached, non-fatal request for only the selected result.
