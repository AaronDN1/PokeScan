import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

test("ships the focused scanner experience without starter metadata", async () => {
  const [page, layout, scanner, manifest, packageJson] = await Promise.all([
    readFile(new URL("app/page.tsx", root), "utf8"),
    readFile(new URL("app/layout.tsx", root), "utf8"),
    readFile(new URL("components/scanner/scanner-app.tsx", root), "utf8"),
    readFile(new URL("app/manifest.ts", root), "utf8"),
    readFile(new URL("package.json", root), "utf8"),
  ]);

  assert.match(page, /ScannerApp/);
  assert.match(layout, /PokéLens/);
  assert.doesNotMatch(layout, /codex-preview|Starter Project/);
  assert.match(scanner, /Take photo|UploadPanel/);
  assert.match(scanner, /Scanner ready/);
  assert.match(scanner, /Scanner offline/);
  assert.match(scanner, /Scanner setup needed/);
  assert.match(scanner, /mutation\.data\.card \?/);
  assert.match(scanner, /!mutation\.data\.card \?/);
  assert.match(scanner, /mutation\.isPending/);
  assert.match(scanner, /mutation\.isError/);
  assert.match(scanner, /disabled=\{!scannerReady\}/);
  assert.match(manifest, /standalone/);
  assert.match(packageJson, /@tanstack\/react-query/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
});

test("renders optional pricing and marketplace data honestly", async () => {
  const [contracts, resultCard, candidates] = await Promise.all([
    readFile(new URL("lib/contracts.ts", root), "utf8"),
    readFile(new URL("components/scanner/result-card.tsx", root), "utf8"),
    readFile(new URL("components/scanner/candidate-list.tsx", root), "utf8"),
  ]);
  assert.match(contracts, /price_status/);
  assert.match(contracts, /near_mint/);
  assert.match(contracts, /lightly_played/);
  assert.match(contracts, /moderately_played/);
  assert.match(contracts, /marketplace_url: z\.string\(\)\.url\(\)\.nullable\(\)/);
  assert.match(resultCard, /card\.marketplace_url \?/);
  assert.match(resultCard, /Open in TCGplayer/);
  assert.match(resultCard, /not endorsed or certified by TCGplayer/);
  assert.doesNotMatch(candidates, /card\.marketplace_url \?/);
});

test("does not retain uploaded card images in browser storage", async () => {
  const files = await Promise.all([
    readFile(new URL("components/scanner/scanner-app.tsx", root), "utf8"),
    readFile(new URL("lib/api.ts", root), "utf8"),
    readFile(new URL("public/sw.js", root), "utf8"),
  ]);
  const source = files.join("\n");

  assert.doesNotMatch(source, /localStorage|sessionStorage|indexedDB/);
  assert.match(source, /FormData/);
  assert.match(source, /startsWith\("\/api\/"\)/);
});

test("repairs a partial Python environment before setup", async () => {
  const launcher = await readFile(new URL("local-app.mjs", root), "utf8");

  assert.match(launcher, /existsSync\(venvConfig\)/);
  assert.match(launcher, /Repairing an incomplete local Python environment/);
  assert.match(launcher, /rmSync\(venvRoot, \{ recursive: true, force: true \}\)/);
});
