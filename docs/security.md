# Security and privacy

- Uploads are allowlisted by declared MIME and decoded format, capped by compressed bytes and decompressed pixels, and verified before OpenCV.
- Only one file is read, with a hard upper bound. Image bytes are cleared from the request scope and never persisted by the application.
- CORS origins are explicit. Credentials are disabled because the initial product has no accounts.
- Recognition is rate limited per client address, coordinated by Redis in production.
- Marketplace credentials belong only in backend environment/secret management. The browser receives a public product URL, never API secrets.
- Structured logs contain request IDs, route, status, and timings. They must not contain raw images, crops, embeddings, OCR screenshots, multipart bodies, or credentials.
- Feedback is identifier-only. Failed scans are not retained; a future opt-in retention flow requires a separate encrypted object store, retention policy, deletion job, and consent UI.
- Containers run non-root users and expose only required ports.
- Production disables interactive API documentation and enables TLS at the ingress.

Before launch, add dependency/container scanning, a restrictive Content Security Policy aligned with the catalog image host, abuse monitoring, secret rotation, database backups, and an incident/deletion runbook.
