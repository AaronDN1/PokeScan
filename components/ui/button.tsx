import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type ButtonVariant = "primary" | "secondary" | "ghost";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-[#f2f6fc] text-[#0a0e14] border-transparent hover:bg-white disabled:bg-[#75808e]",
  secondary:
    "bg-white/[0.035] text-[#eef3fa] border-white/[0.11] hover:bg-white/[0.075] hover:border-white/[0.18]",
  ghost:
    "bg-transparent text-[#aab4c2] border-transparent hover:bg-white/[0.05] hover:text-white",
};

export function Button({ className, variant = "primary", type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex min-h-12 items-center justify-center gap-2 rounded-[12px] border px-5 text-[14px] font-semibold tracking-[-0.01em] transition-[background-color,border-color,color,transform] duration-200 active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
