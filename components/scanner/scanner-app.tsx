"use client";

import { useMutation } from "@tanstack/react-query";
import { AlertCircle, ScanLine } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { CandidateList } from "@/components/scanner/candidate-list";
import { ResultCard } from "@/components/scanner/result-card";
import { ScanProgress } from "@/components/scanner/scan-progress";
import { UploadPanel } from "@/components/scanner/upload-panel";
import { Button } from "@/components/ui/button";
import { ApiError, recognizeCard } from "@/lib/api";
import type { ScanStage } from "@/lib/contracts";

const MAX_UPLOAD_BYTES = 12 * 1024 * 1024;
const stageOrder: ScanStage[] = ["preparing", "locating", "reading", "matching"];

export function ScannerApp() {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [stage, setStage] = useState<ScanStage>("preparing");
  const [validationError, setValidationError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const mutation = useMutation({
    mutationFn: ({ file, signal }: { file: File; signal: AbortSignal }) => recognizeCard(file, signal),
  });

  useEffect(() => {
    if (!mutation.isPending) return;
    const interval = window.setInterval(() => {
      setStage((current) => stageOrder[Math.min(stageOrder.indexOf(current) + 1, stageOrder.length - 1)]);
    }, 420);
    return () => window.clearInterval(interval);
  }, [mutation.isPending]);

  useEffect(() => () => {
    abortRef.current?.abort();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setStage("preparing");
    setValidationError(null);
    mutation.reset();
  }, [mutation, previewUrl]);

  const selectFile = (file: File) => {
    setValidationError(null);
    if (!file.type.startsWith("image/")) {
      setValidationError("Choose a JPEG, PNG, WebP, or HEIC image.");
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setValidationError("That photo is larger than 12 MB. Choose a smaller image and try again.");
      return;
    }

    abortRef.current?.abort();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    const nextPreview = URL.createObjectURL(file);
    const controller = new AbortController();
    abortRef.current = controller;
    setPreviewUrl(nextPreview);
    setStage("preparing");
    mutation.mutate({ file, signal: controller.signal });
  };

  const errorMessage = validationError ?? (
    mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error
        ? "Something went wrong while analyzing the photo. Please try again."
        : null
  );

  return (
    <div className="min-h-screen">
      <header className="border-b border-white/[0.065]">
        <div className="mx-auto flex h-[68px] max-w-[1120px] items-center justify-between px-5 sm:px-8">
          <Link href="/" className="flex items-center gap-2.5" aria-label="PokéLens home">
            <span className="relative grid h-8 w-8 place-items-center rounded-[10px] border border-white/[0.12] bg-white/[0.04]">
              <ScanLine aria-hidden="true" className="h-[17px] w-[17px] text-[#77aefa]" strokeWidth={1.8} />
              <span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-[#d9bd7d] shadow-[0_0_9px_rgba(217,189,125,0.8)]" />
            </span>
            <span className="text-[15px] font-semibold tracking-[-0.025em] text-[#eef3fa]">PokéLens</span>
          </Link>
          <div className="flex items-center gap-2 text-[11px] font-medium text-[#778391]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#70d7a5] shadow-[0_0_8px_rgba(112,215,165,0.55)]" />
            Scanner ready
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[880px] px-4 pb-10 pt-8 sm:px-8 sm:pb-16 sm:pt-12">
        {mutation.isIdle ? <UploadPanel onSelect={selectFile} /> : null}
        {mutation.isPending && previewUrl ? (
          <ScanProgress previewUrl={previewUrl} stage={stage} onCancel={reset} />
        ) : null}
        {mutation.isSuccess && mutation.data.status === "matched" ? (
          <ResultCard result={mutation.data} onReset={reset} />
        ) : null}
        {mutation.isSuccess && mutation.data.status !== "matched" ? (
          <CandidateList result={mutation.data} onReset={reset} />
        ) : null}
        {mutation.isError ? <UploadPanel onSelect={selectFile} /> : null}

        {errorMessage ? (
          <div className="mt-4 flex items-start gap-3 rounded-[14px] border border-[#ff8d8d]/20 bg-[#ff8d8d]/[0.065] p-4 text-[13px] leading-5 text-[#efaaaa]" role="alert">
            <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="flex-1">
              <p>{errorMessage}</p>
              {mutation.isError ? <Button className="mt-3 min-h-9 px-3 text-[12px]" variant="secondary" onClick={reset}>Clear</Button> : null}
            </div>
          </div>
        ) : null}

        {mutation.isIdle ? (
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            {[
              ["01", "One card only", "Keep other cards out of frame."],
              ["02", "Use even light", "Avoid glare across the artwork."],
              ["03", "Show the edges", "Leave a small border around the card."],
            ].map(([number, title, copy]) => (
              <div key={number} className="rounded-[14px] border border-white/[0.06] bg-white/[0.018] px-4 py-3.5">
                <span className="font-mono text-[10px] text-[#5f6a78]">{number}</span>
                <p className="mt-1 text-[12px] font-semibold text-[#acb6c3]">{title}</p>
                <p className="mt-0.5 text-[11px] leading-4 text-[#687381]">{copy}</p>
              </div>
            ))}
          </div>
        ) : null}
      </main>

      <footer className="mx-auto flex max-w-[1120px] items-center justify-between border-t border-white/[0.055] px-5 py-6 text-[11px] text-[#596471] sm:px-8">
        <span>© {new Date().getFullYear()} PokéLens</span>
        <span>Images are not retained</span>
      </footer>
    </div>
  );
}
