import {
  healthResponseSchema,
  recognitionResponseSchema,
  type HealthResponse,
  type RecognitionResponse,
} from "@/lib/contracts";

const configuredApiOrigin =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_URL;

function resolveApiOrigin(): { origin: string; error: string | null } {
  const raw = configuredApiOrigin?.trim() ||
    (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
  if (!raw) {
    return {
      origin: "",
      error: "Set NEXT_PUBLIC_API_BASE_URL to the public FastAPI URL before building the frontend.",
    };
  }
  try {
    const parsed = new URL(raw);
    if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error("Unsupported protocol");
    return { origin: raw.replace(/\/$/, ""), error: null };
  } catch {
    return {
      origin: "",
      error: "NEXT_PUBLIC_API_BASE_URL must be an absolute http:// or https:// URL.",
    };
  }
}

const apiConfiguration = resolveApiOrigin();

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function recognizeCard(image: File, signal?: AbortSignal): Promise<RecognitionResponse> {
  if (apiConfiguration.error) throw new ApiError(apiConfiguration.error, 503, "api_url_invalid");
  const body = new FormData();
  body.append("image", image, image.name || "card-photo.jpg");

  let response: Response;
  try {
    response = await fetch(`${apiConfiguration.origin}/api/v1/recognitions`, {
      method: "POST",
      body,
      signal,
      headers: { Accept: "application/json" },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("The scanner is temporarily unavailable. Please try again shortly.", 503);
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = typeof payload?.detail === "string" ? payload.detail : null;
    throw new ApiError(detail ?? "We could not process that photo.", response.status, payload?.code);
  }

  return recognitionResponseSchema.parse(await response.json());
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  if (apiConfiguration.error) throw new ApiError(apiConfiguration.error, 503, "api_url_invalid");
  let response: Response;
  try {
    response = await fetch(`${apiConfiguration.origin}/health`, {
      signal,
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiError(
      `The recognition API at ${apiConfiguration.origin} could not be reached.`,
      503,
      "backend_offline",
    );
  }
  if (!response.ok) throw new ApiError("The recognition service is offline.", response.status);
  return healthResponseSchema.parse(await response.json());
}
