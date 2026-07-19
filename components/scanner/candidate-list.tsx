"use client";

import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { RecognitionResponse } from "@/lib/contracts";

interface CandidateListProps {
  result: RecognitionResponse;
  onReset: () => void;
}

export function CandidateList({ result, onReset }: CandidateListProps) {
  const hasCandidates = result.candidates.length > 0;
  return (
    <section className="rounded-[24px] border border-white/[0.09] bg-[#0d1118] p-5 shadow-[0_24px_80px_rgba(0,0,0,0.28)] sm:p-8" aria-live="polite">
      <span className="text-[12px] font-semibold uppercase tracking-[0.16em] text-[#e1bd71]">
        {hasCandidates ? "Possible matches" : "No reliable match"}
      </span>
      <h2 className="mt-3 text-[28px] font-semibold tracking-[-0.035em] text-white">
        {hasCandidates ? "Closest card printings" : "This scan did not contain enough evidence"}
      </h2>
      <p className="mt-2 max-w-[560px] text-[14px] leading-6 text-[#929dab]">{result.message ?? "Choose the exact printing, or take another photo with the collector number clearly visible."}</p>

      {hasCandidates ? <div className="mt-7 grid gap-3 sm:grid-cols-3">
        {result.candidates.slice(0, 3).map(({ card, confidence }) => (
          <article
            key={card.id}
            className="rounded-[16px] border border-white/[0.08] bg-white/[0.025] p-3"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={card.image_url} alt="" className="aspect-[3/4] w-full rounded-[10px] bg-black object-contain" />
            <h3 className="mt-3 truncate text-[14px] font-semibold text-white">{card.name}</h3>
            <p className="mt-0.5 truncate text-[12px] text-[#7f8997]">{card.set_name} · {card.collector_number}</p>
            <p className="mt-2 text-[11px] font-medium text-[#8dbaff]">{Math.round(confidence * 100)}% match</p>
          </article>
        ))}
      </div> : null}

      <Button className="mt-6 w-full sm:w-auto" variant="secondary" onClick={onReset}>
        <RotateCcw aria-hidden="true" className="h-4 w-4" />
        Scan another card
      </Button>
    </section>
  );
}
