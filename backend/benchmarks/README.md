# Recognition benchmark data

Copy `manifest.example.json` to `manifest.json`, place consented real photographs under `photos/`, and map each relative path to its exact imported TCGdex card ID. Photos and generated results are ignored by Git.

```bash
python scripts/benchmark_recognition.py --manifest benchmarks/manifest.json --output benchmarks/results.json
```

The report includes localization, exact name/collector OCR, top-1/top-3 card accuracy, false-confident, ambiguous and unrecognized rates, plus median and p95 latency. Do not use production uploads without explicit user consent.
