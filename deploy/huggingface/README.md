---
title: PokéLens Recognition API
emoji: 🔎
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 7860
fullWidth: true
---

# PokéLens Recognition API

This Docker Space runs the FastAPI, OpenCV, OCR, and visual-matching backend for
the PokéLens mobile web app. The source application is maintained in
[AaronDN1/PokeScan](https://github.com/AaronDN1/PokeScan).

The public health endpoint is `/health`. Uploaded card images are processed in
memory and are not retained.
