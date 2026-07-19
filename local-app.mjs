import { spawn, spawnSync } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.dirname(fileURLToPath(import.meta.url));
const backend = path.join(root, "backend");
const venvRoot = path.join(backend, ".venv");
const isWindows = process.platform === "win32";
const venvPython = path.join(
  venvRoot,
  isWindows ? "Scripts/python.exe" : "bin/python",
);
const venvConfig = path.join(venvRoot, "pyvenv.cfg");
const nextBin = path.join(root, "node_modules", "next", "dist", "bin", "next");
const setupOnly = process.argv.includes("--setup");
const quickCatalog = process.argv.includes("--quick");
const children = new Set();
let stopping = false;

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd ?? root,
      env: { ...process.env, PYTHONUNBUFFERED: "1", ...options.env },
      stdio: options.stdio ?? "inherit",
      windowsHide: true,
    });
    child.once("error", reject);
    child.once("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${path.basename(command)} exited with code ${code ?? "unknown"}`));
    });
  });
}

function runCaptured(command, args, options = {}) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd: options.cwd ?? root,
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
      stdio: "ignore",
      windowsHide: true,
    });
    child.once("error", () => resolve(false));
    child.once("exit", (code) => resolve(code === 0));
  });
}

async function createVenv() {
  if (
    existsSync(venvConfig)
    && existsSync(venvPython)
    && await runCaptured(venvPython, ["--version"], { cwd: backend })
  ) return;
  if (existsSync(venvRoot)) {
    console.log("Repairing an incomplete local Python environment...");
    rmSync(venvRoot, { recursive: true, force: true });
  }
  console.log("Preparing the local Python environment (first run only)...");
  if (isWindows) {
    const created = await runCaptured("py", ["-3.12", "-m", "venv", venvRoot]);
    if (!created) {
      throw new Error("Python 3.12 was not found. Install Python 3.12, then run pnpm.cmd setup again.");
    }
  } else {
    await run("python3.12", ["-m", "venv", venvRoot]);
  }
}

async function syncBackendDependencies(force = false) {
  await createVenv();
  const usable = await runCaptured(
    venvPython,
    ["-c", "import uvicorn, PIL, pillow_heif, app.main"],
    { cwd: backend },
  );
  if (usable && !force) return;
  console.log("Installing the recognition backend dependencies...");
  await run(venvPython, ["-m", "pip", "install", "--upgrade", "pip"], { cwd: root });
  await run(venvPython, ["-m", "pip", "install", "-e", `${backend}[dev]`], { cwd: root });
}

async function bootstrap() {
  await syncBackendDependencies();
  const args = ["scripts/bootstrap_dev.py"];
  if (quickCatalog) args.push("--limit", "250");
  console.log(quickCatalog ? "Preparing a 250-card smoke-test catalog..." : "Preparing the complete English card catalog...");
  await run(venvPython, args, { cwd: backend });
}

async function health() {
  try {
    const response = await fetch("http://127.0.0.1:8000/health", {
      signal: AbortSignal.timeout(1500),
      cache: "no-store",
    });
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}

async function webStatus() {
  try {
    const response = await fetch("http://127.0.0.1:5173", {
      signal: AbortSignal.timeout(1500),
      cache: "no-store",
    });
    const body = await response.text();
    return { occupied: true, pokelens: body.includes("PokéLens") };
  } catch {
    return { occupied: false, pokelens: false };
  }
}

async function waitForHealth(child) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (child.exitCode !== null) throw new Error("The recognition API stopped during startup.");
    const current = await health();
    if (current) return current;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("The recognition API did not become ready within 60 seconds.");
}

function startChild(command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: options.cwd ?? root,
    env: { ...process.env, PYTHONUNBUFFERED: "1", ...options.env },
    stdio: "inherit",
    windowsHide: true,
  });
  children.add(child);
  child.once("exit", () => children.delete(child));
  return child;
}

function shutdown(exitCode = 0) {
  if (stopping) return;
  stopping = true;
  process.exitCode = exitCode;
  for (const child of children) {
    if (!child.pid) continue;
    if (isWindows) {
      spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
        stdio: "ignore",
        windowsHide: true,
      });
    } else {
      child.kill("SIGTERM");
    }
  }
  setTimeout(() => process.exit(exitCode), 250);
}

async function startApp() {
  console.log("Starting PokéLens...");
  await syncBackendDependencies();
  let currentHealth = await health();
  let apiChild = null;
  if (!currentHealth) {
    console.log("Starting the recognition API...");
    apiChild = startChild(
      venvPython,
      ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
      { cwd: backend },
    );
    currentHealth = await waitForHealth(apiChild);
  } else {
    console.log("Using the PokéLens recognition API already running on port 8000.");
  }

  if (currentHealth?.recognition_ready !== true) {
    const issues = Array.isArray(currentHealth?.issues) ? currentHealth.issues.join(" ") : "Setup is incomplete.";
    throw new Error(`${issues} Run pnpm.cmd setup, then try again.`);
  }

  console.log(`Recognition ready with ${currentHealth.capabilities.catalog.card_count} catalog cards.`);
  apiChild?.once("exit", (code) => {
    if (!stopping) {
      console.error(`Recognition API stopped unexpectedly (exit ${code ?? "unknown"}).`);
      shutdown(code ?? 1);
    }
  });

  const currentWeb = await webStatus();
  if (currentWeb.pokelens) {
    console.log("Using the PokéLens web app already running on port 5173.");
    console.log("PokéLens is ready at http://127.0.0.1:5173");
    return;
  }
  if (currentWeb.occupied) {
    throw new Error("Port 5173 is already in use by another web app. Stop that app, then try again.");
  }

  console.log("Opening PokéLens at http://127.0.0.1:5173");
  const webChild = startChild(
    process.execPath,
    [nextBin, "dev", "--webpack", "-H", "127.0.0.1", "-p", "5173"],
    { cwd: root },
  );
  webChild.once("exit", (code) => shutdown(code ?? 1));
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

try {
  if (setupOnly) {
    await bootstrap();
    console.log("Setup complete. Run pnpm.cmd dev to start PokéLens.");
  } else {
    await startApp();
  }
} catch (error) {
  console.error(`\nPokéLens could not start: ${error instanceof Error ? error.message : String(error)}`);
  shutdown(1);
}
