# Recognition benchmark data

Benchmark images are not committed to avoid redistributing card artwork and user photographs. Place consented, licensed data under versioned dataset directories such as `v1/images/`, with a `manifest.jsonl` containing only relative paths, expected card IDs, capture conditions, and consent/license provenance.

The benchmark runner and promotion gates are documented in `../../docs/benchmarks.md`. Never use production uploads as training or benchmark data unless a user explicitly opts in.
