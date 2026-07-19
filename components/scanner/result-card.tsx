"use client";

import { ArrowUpRight, CheckCircle2, RotateCcw, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { RecognitionResponse } from "@/lib/contracts";
import { formatCollectorNumber, formatUsd } from "@/lib/utils";

interface ResultCardProps {
  result: RecognitionResponse;
  onReset: () => void;
}

export function ResultCard({ result, onReset }: ResultCardProps) {
  const card = result.card;
  if (!card) return null;

  const confidence = Math.round(result.confidence * 100);

  return (
    <section className="[animation:result-enter_360ms_ease-out]" aria-live="polite">
      <div className="mb-4 flex items-center justify-between px-1">
        <div className="flex items-center gap-2 text-[13px] font-medium text-[#7ce0b0]">
          <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
          Match confirmed
        </div>
        <span className="text-[12px] text-[#778391]">{Math.round(result.processing_ms)} ms</span>
      </div>

      <div className="overflow-hidden rounded-[24px] border border-white/[0.1] bg-[#0d1118] shadow-[0_24px_80px_rgba(0,0,0,0.3)]">
        <div className="grid sm:grid-cols-[minmax(210px,0.78fr)_1.22fr]">
          <div className="relative min-h-[360px] overflow-hidden bg-[#090c11] p-7 sm:min-h-[520px] sm:p-9">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,rgba(118,169,238,0.15),transparent_42%),radial-gradient(circle_at_80%_100%,rgba(217,189,125,0.1),transparent_42%)]" />
            {/* The catalog image is remote by design; the API owns and validates its URL. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={card.image_url}
              alt={`${card.name} from ${card.set_name}`}
              className="relative mx-auto h-full max-h-[450px] w-full max-w-[320px] rounded-[14px] object-contain drop-shadow-[0_22px_30px_rgba(0,0,0,0.45)]"
            />
          </div>

          <div className="flex flex-col p-6 sm:p-9">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-[#70d7a5]/25 bg-[#70d7a5]/8 px-3 py-1 text-[11px] font-semibold text-[#84dfb6]">
                {confidence}% confidence
              </span>
              <span className="rounded-full border border-white/[0.09] px-3 py-1 text-[11px] font-medium text-[#9aa5b3]">{card.language}</span>
            </div>

            <h2 className="mt-6 text-[32px] font-semibold leading-[1.08] tracking-[-0.045em] text-white sm:text-[40px]">{card.name}</h2>
            <p className="mt-2 text-[15px] text-[#a2adbb]">{card.set_name}</p>

            <dl className="mt-8 grid grid-cols-2 gap-x-5 gap-y-6 border-y border-white/[0.08] py-6">
              <div>
                <dt className="text-[11px] font-medium uppercase tracking-[0.12em] text-[#66717f]">Collector no.</dt>
                <dd className="mt-1.5 text-[14px] font-medium text-[#dce3ec]">{formatCollectorNumber(card.collector_number, card.printed_total)}</dd>
              </div>
              <div>
                <dt className="text-[11px] font-medium uppercase tracking-[0.12em] text-[#66717f]">Rarity</dt>
                <dd className="mt-1.5 text-[14px] font-medium text-[#dce3ec]">{card.rarity ?? "Unknown"}</dd>
              </div>
            </dl>

            <div className="mt-7">
              <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[#66717f]">Current market price</p>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-[34px] font-semibold tracking-[-0.04em] text-[#f5f7fa]">{formatUsd(card.price.amount)}</span>
                {card.price.amount !== null ? <span className="text-[12px] text-[#778391]">USD</span> : null}
              </div>
              {card.price.updated_at ? <p className="mt-1 text-[11px] text-[#66717f]">Cached {new Date(card.price.updated_at).toLocaleDateString()}</p> : null}
            </div>

            <div className="mt-auto grid gap-3 pt-8">
              {card.marketplace_url ? (
                <a
                  href={card.marketplace_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex min-h-12 items-center justify-center gap-2 rounded-[12px] bg-[#f2f6fc] px-5 text-[14px] font-semibold text-[#0a0e14] transition-colors hover:bg-white"
                >
                  View marketplace listing
                  <ArrowUpRight aria-hidden="true" className="h-4 w-4" />
                </a>
              ) : null}
              <Button variant="secondary" onClick={onReset}>
                <RotateCcw aria-hidden="true" className="h-4 w-4" />
                Scan another card
              </Button>
            </div>

            <p className="mt-5 flex items-center justify-center gap-1.5 text-[11px] text-[#697482]">
              <ShieldCheck aria-hidden="true" className="h-3.5 w-3.5" />
              Text and artwork evidence independently checked
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
