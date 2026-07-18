import { z } from "zod";

export const priceSchema = z.object({
  amount: z.number().nullable(),
  currency: z.string().default("USD"),
  source: z.string().nullable(),
  updated_at: z.string().nullable(),
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
  marketplace_url: z.string().url(),
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
});

export type Card = z.infer<typeof cardSchema>;
export type RecognitionResponse = z.infer<typeof recognitionResponseSchema>;

export type ScanStage = "preparing" | "locating" | "reading" | "matching";
