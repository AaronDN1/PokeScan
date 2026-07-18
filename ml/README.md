# Machine-learning workspace

Training uses PyTorch; serving uses ONNX Runtime through narrow backend ports. The artwork model learns embeddings, not a fixed class per card, so catalog additions require embedding generation rather than retraining a giant classifier.

The checked-in module defines the deployment-compatible artwork network, batch-hard triplet loss, and ONNX export. OCR models follow the CTC contracts in `../backend/models/README.md`; their dataset pipelines belong in a separately versioned, provenance-tracked training repository once licensed data is selected.

Model promotion requires reproducible dataset manifests, held-out real-photo results, latency measurements on the target CPU, and the confidence calibration gates in `../docs/benchmarks.md`.
