# Benchmarks

No production accuracy or latency claim is made for this pretrained baseline without representative evidence.

Copy `backend/benchmarks/manifest.example.json` to `manifest.json`, add licensed/consented real photographs under `backend/benchmarks/photos/`, and map each file to an exact imported card ID. Include modern/vintage layouts, repeated names/artwork, sleeves, glare, rotations, perspective, device compression, and unusable negatives.

```bash
cd backend
python scripts/benchmark_recognition.py --manifest benchmarks/manifest.json --output benchmarks/results.json --stress
```

The optional `--stress` flag adds deterministic phone-like JPEG compression, dim
light, and soft-focus variants without saving derived photos. These variants expose
regressions but do not turn one source photo into four independent accuracy samples.

The runner uses the real composition root and reports source-photo and evaluated
variant counts, localization success, exact name and collector OCR accuracy,
top-1/top-3 exact-card accuracy, false-confident match rate,
ambiguous/unrecognized rates, median latency, and p95 latency. Keep hardware, Git
commit, catalog snapshot, dependency versions, and threshold configuration with
promoted reports. Do not tune and evaluate on the same photographs.
