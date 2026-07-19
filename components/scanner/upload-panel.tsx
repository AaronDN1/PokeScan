"use client";

import { Camera, ImagePlus, LockKeyhole, ScanLine } from "lucide-react";
import { useRef } from "react";
import { Button } from "@/components/ui/button";

interface UploadPanelProps {
  disabled?: boolean;
  onSelect: (file: File) => void;
}

const ACCEPTED_TYPES =
  ".jpg,.jpeg,.jfif,.png,.webp,.heic,.heif,.mpo,image/jpeg,image/png,image/webp,image/heic,image/heif";

export function UploadPanel({ disabled = false, onSelect }: UploadPanelProps) {
  const cameraRef = useRef<HTMLInputElement>(null);
  const uploadRef = useRef<HTMLInputElement>(null);

  const handleChange = (file?: File) => {
    if (file) onSelect(file);
  };

  return (
    <section className="relative overflow-hidden rounded-[24px] border border-white/[0.09] bg-[#0d1118]/95 p-4 shadow-[0_24px_80px_rgba(0,0,0,0.28)] sm:p-6">
      <div className="pointer-events-none absolute inset-x-12 top-0 h-px bg-gradient-to-r from-transparent via-[#6ea8fe]/60 to-transparent" />

      <div className="flex min-h-[312px] flex-col items-center justify-center rounded-[18px] border border-dashed border-white/[0.14] bg-[radial-gradient(circle_at_50%_25%,rgba(110,168,254,0.075),transparent_58%)] px-5 py-8 text-center sm:min-h-[354px]">
        <div className="relative mb-6 grid h-[116px] w-[84px] place-items-center rounded-[10px] border border-white/[0.18] bg-[#111823] shadow-[0_16px_45px_rgba(0,0,0,0.35)]">
          <div className="absolute left-2 top-2 h-4 w-4 border-l-2 border-t-2 border-[#78aefb]" />
          <div className="absolute right-2 top-2 h-4 w-4 border-r-2 border-t-2 border-[#78aefb]" />
          <div className="absolute bottom-2 left-2 h-4 w-4 border-b-2 border-l-2 border-[#78aefb]" />
          <div className="absolute bottom-2 right-2 h-4 w-4 border-b-2 border-r-2 border-[#78aefb]" />
          <ScanLine aria-hidden="true" className="h-7 w-7 text-[#7faef0]/85" strokeWidth={1.5} />
        </div>

        <h1 className="max-w-[420px] text-balance text-[26px] font-semibold leading-[1.15] tracking-[-0.035em] text-[#f4f7fb] sm:text-[32px]">
          One photo. The right card.
        </h1>
        <p className="mt-3 max-w-[390px] text-pretty text-[14px] leading-6 text-[#929dab] sm:text-[15px]">
          Take a quick photo with one card roughly centered. We’ll handle ordinary rotation, perspective, and phone compression.
        </p>

        <div className="mt-7 grid w-full max-w-[390px] gap-3 sm:grid-cols-2">
          <Button className="w-full" disabled={disabled} onClick={() => cameraRef.current?.click()}>
            <Camera aria-hidden="true" className="h-[17px] w-[17px]" strokeWidth={2} />
            Take photo
          </Button>
          <Button
            className="w-full"
            variant="secondary"
            disabled={disabled}
            onClick={() => uploadRef.current?.click()}
          >
            <ImagePlus aria-hidden="true" className="h-[17px] w-[17px]" strokeWidth={2} />
            Upload photo
          </Button>
        </div>

        <input
          ref={cameraRef}
          className="sr-only"
          type="file"
          accept={ACCEPTED_TYPES}
          capture="environment"
          aria-label="Take a photo of a Pokémon card"
          onChange={(event) => handleChange(event.target.files?.[0])}
        />
        <input
          ref={uploadRef}
          className="sr-only"
          type="file"
          accept={ACCEPTED_TYPES}
          aria-label="Upload a photo of a Pokémon card"
          onChange={(event) => handleChange(event.target.files?.[0])}
        />
      </div>

      <div className="mt-4 flex items-center justify-center gap-2 text-[12px] text-[#778291]">
        <LockKeyhole aria-hidden="true" className="h-3.5 w-3.5" strokeWidth={1.7} />
        Photos are processed securely and never stored by default
      </div>
    </section>
  );
}
