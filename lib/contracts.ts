import { z } from "zod";

export const priceSchema = z.object({
  amount: z.number().nullable(),
  currency: z.string().default("USD"),
  source: z.string().nullable(),
  updated_at: z.string().nullable(),
  near_mint: z.number().nullable(),
  lightly_played: z.number().nullable(),
  moderately_played: z.number().nullable(),
  product_id: z.string().nullable(),
  marketplace_url: z.string().url().nullable(),
  printing_name: z.string().nullable(),
  price_status: z.enum(["available", "unavailable"]),
});

export const cardSchema = z.object({
  id: z.string(),
  name: z.string(),
  set_name: z.string(),
  collector_number: z.string(),
  printed_total: z.string().nullable().optional(),
  rarity: z.string().nullable(),
  language: z.string(),
  image_url: z.string().url(),
  marketplace_url: z.string().url().nullable(),
  price: priceSchema,
});

export const candidateSchema = z.object({
  card: cardSchema,
  confidence: z.number().min(0).max(1),
});

export const recognitionResponseSchema = z.object({
  recognition_id: z.string(),
  status: z.enum(["matched", "ambiguous", "unrecognized"]),
  card: cardSchema.nullable(),
  confidence: z.number().min(0).max(1),
  candidates: z.array(candidateSchema).default([]),
  processing_ms: z.number().nonnegative(),
  message: z.string().nullable(),
  diagnostics: z.record(z.unknown()).nullable().optional(),
});

export const healthResponseSchema = z.object({
  status: z.enum(["ready", "degraded"]),
  version: z.string(),
  database: z.enum(["ready", "unavailable"]),
  recognition_ready: z.boolean(),
  capabilities: z.object({
    card_localization: z.object({ ready: z.boolean(), backend: z.string() }).passthrough(),
    ocr: z.object({ ready: z.boolean(), backend: z.string() }).passthrough(),
    artwork_matching: z.object({ ready: z.boolean(), backend: z.string() }).passthrough(),
    catalog: z.object({
      ready: z.boolean(),
      card_count: z.number().int().nonnegative(),
      source: z.string(),
    }),
    pricing: z.object({
      ready: z.boolean(),
      priced_card_count: z.number().int().nonnegative(),
      mode: z.string(),
      direct_links_ready: z.boolean(),
      condition_prices_ready: z.boolean(),
    }),
    custom_onnx_models: z.boolean(),
  }),
  issues: z.array(z.string()),
});

export type Card = z.infer<typeof cardSchema>;
export type RecognitionResponse = z.infer<typeof recognitionResponseSchema>;
export type HealthResponse = z.infer<typeof healthResponseSchema>;

export type ScanStage = "preparing" | "locating" | "reading" | "matching";
