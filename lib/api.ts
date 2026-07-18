import { recognitionResponseSchema, type RecognitionResponse } from "@/lib/contracts";

const API_ORIGIN = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

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
  const body = new FormData();
  body.append("image", image, image.name || "card-photo.jpg");

  let response: Response;
  try {
    response = await fetch(`${API_ORIGIN}/api/v1/recognitions`, {
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
