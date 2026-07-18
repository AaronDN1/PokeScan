# Benchmarks and model promotion

Accuracy must be measurable before model artifacts serve traffic. Dataset files live outside Git; manifests and aggregate reports are versioned.

## Dataset slices

The held-out benchmark must contain licensed, consented real photographs across:

- modern and vintage layouts;
- standard, full-art, rainbow, gold, and holographic treatments;
- sleeves and unsleeved cards;
- controlled, dim, warm, and mixed light;
- perspective, rotation, partial shadow, and realistic device compression;
- confusing reprints with the same name/artwork but different set or number;
- non-card images, multiple cards, blur, glare, and partial-card negatives.

Do not split multiple photos of one physical card across training and held-out sets.

## Required metrics

- exact card top-1 accuracy;
- top-3 recall for ambiguous results;
- false-confident rate (wrong result returned as `matched`);
- correct rejection rate for negatives and unusable images;
- localization success and corner error;
- OCR exact name and exact collector-number rates;
- p50, p95, and p99 end-to-end CPU latency;
- results by every capture-condition slice.

## Initial promotion gates

- false-confident rate ≤ 0.2%;
- exact top-1 ≥ 97% on recognized, usable single-card photos;
- unusable-image rejection ≥ 95%;
- p95 server recognition ≤ 1.0 s on the declared production CPU;
- no critical slice more than five percentage points below aggregate accuracy.

These are product gates, not claims about the untrained repository checkout.

## Report metadata

Every report records Git commit, model semantic version and SHA-256, dataset manifest digest, catalog snapshot, hardware, ONNX Runtime version, confidence thresholds, raw confusion counts, and slice tables. Threshold changes require the same review as model changes.
