# Database and catalog

SQLite is the local default at `backend/data/pokelens.db`; PostgreSQL is supported through the same async SQLAlchemy records.

Each card ID includes provider, language, set, and source card identity. Stored fields include raw and normalized name/collector number, printed total, source/set IDs, rarity/language, nullable marketplace mapping, reference asset, pHash, ORB descriptor bytes, and float32 MobileNet embedding bytes. The normalized collector/name index drives bounded retrieval. Optional cached prices live in `card_prices`; feedback never references image storage.

Catalog setup is deliberately offline:

```bash
python scripts/build_catalog.py --language en --output data/catalog-en.json
python scripts/prepare_catalog_assets.py data/catalog-en.json
python scripts/import_catalog.py data/catalog-en.json
```

The versioned JSON export can be imported into either SQLite or PostgreSQL. Isolated unavailable reference assets do not abort the entire build. Recognition performs no provider download or live price request.
