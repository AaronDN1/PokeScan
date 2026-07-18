# Database schema

PostgreSQL is the production database. SQLite is supported only for low-friction local development and tests.

```mermaid
erDiagram
  CARDS ||--o| CARD_PRICES : "has cached"
  CARDS {
    string id PK
    string name
    string normalized_name
    string collector_number
    string printed_total
    string set_name
    string rarity
    string language
    text reference_image_url
    string marketplace_id UK
    text marketplace_url
    bytes visual_embedding
  }
  CARD_PRICES {
    string card_id PK,FK
    float amount
    string currency
    string source
    datetime updated_at
  }
  RECOGNITION_FEEDBACK {
    int id PK
    string recognition_id
    string predicted_card_id
    string correct_card_id
    boolean is_correct
    datetime created_at
  }
```

`cards(collector_number, normalized_name)` is indexed for bounded candidate retrieval. Marketplace identifiers are unique. Embeddings are stored as contiguous float32 bytes and decoded only for the already-bounded candidate set.

Catalog ingestion uses `backend/scripts/import_catalog.py`. Production imports should run into a staging database, validate counts, uniqueness, URLs, embedding dimensions, and set/number coverage, then swap or promote transactionally. Recognition never imports or refreshes catalog data inline.

Price refresh is a separate scheduled worker responsibility. It writes the latest successful value and timestamp; expired or missing prices render as unavailable while recognition remains functional.
