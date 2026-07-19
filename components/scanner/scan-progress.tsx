"use client";

import { Check, ScanLine } from "lucide-react";
import type { ScanStage } from "@/lib/contracts";

const stages: Array<{ id: ScanStage; label: string }> = [
  { id: "preparing", label: "Preparing image" },
  { id: "locating", label: "Finding card" },
  { id: "reading", label: "Reading details" },
  { id: "matching", label: "Verifying artwork" },
];

interface ScanProgressProps {
  previewUrl: string;
  stage: ScanStage;
  onCancel: () => void;
}

export function ScanProgress({ previewUrl, stage, onCancel }: ScanProgressProps) {
  const activeIndex = stages.findIndex((item) => item.id === stage);

  return (
    <section className="rounded-[24px] border border-white/[0.09] bg-[#0d1118] p-4 shadow-[0_24px_80px_rgba(0,0,0,0.28)] sm:p-6" aria-live="polite">
      <div className="grid gap-7 sm:grid-cols-[minmax(180px,0.8fr)_1.2fr] sm:items-center sm:gap-10">
        <div className="relative mx-auto aspect-[3/4] w-full max-w-[248px] overflow-hidden rounded-[16px] border border-white/[0.13] bg-black shadow-[0_18px_44px_rgba(0,0,0,0.35)]">
          {/* The browser owns this temporary object URL; it never leaves the device except in the upload request. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={previewUrl} alt="Card being scanned" className="h-full w-full object-cover opacity-65" />
          <div className="absolute inset-3 rounded-[11px] border border-[#79adf8]/55" />
          <div className="absolute inset-x-3 top-3 h-px bg-gradient-to-r from-transparent via-[#9bc5ff] to-transparent shadow-[0_0_18px_4px_rgba(110,168,254,0.52)] [animation:scanner-line_2.1s_ease-in-out_infinite]" />
        </div>

        <div>
          <div className="mb-2 flex items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.16em] text-[#75aaf5]">
            <ScanLine aria-hidden="true" className="h-4 w-4" />
            Analyzing photo
          </div>
          <h2 className="text-[26px] font-semibold tracking-[-0.03em] text-white sm:text-[30px]">Finding the exact match</h2>
          <p className="mt-2 text-[14px] leading-6 text-[#8f9aa8]">CPU recognition can take several seconds while OCR and artwork matching run.</p>

          <ol className="mt-7 space-y-4">
            {stages.map((item, index) => {
              const isComplete = index < activeIndex;
              const isActive = index === activeIndex;
              return (
                <li key={item.id} className="flex items-center gap-3">
                  <span
                    className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border text-[11px] ${
                      isComplete
                        ? "border-[#70d7a5]/35 bg-[#70d7a5]/10 text-[#7ce0b0]"
                        : isActive
                          ? "border-[#6ea8fe]/50 bg-[#6ea8fe]/12 text-[#8fbcff]"
                          : "border-white/[0.09] bg-white/[0.025] text-[#687382]"
                    }`}
                  >
                    {isComplete ? <Check aria-hidden="true" className="h-3.5 w-3.5" /> : index + 1}
                  </span>
                  <span className={`text-[14px] ${isActive ? "font-medium text-[#edf3fb]" : "text-[#808b99]"}`}>{item.label}</span>
                  {isActive ? <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[#78adf8] [animation:pulse-soft_1.1s_ease-in-out_infinite]" /> : null}
                </li>
              );
            })}
          </ol>

          <button type="button" onClick={onCancel} className="mt-8 text-[13px] font-medium text-[#7f8997] transition-colors hover:text-white">
            Cancel scan
          </button>
        </div>
      </div>
    </section>
  );
}
