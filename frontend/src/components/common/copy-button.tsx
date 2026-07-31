"use client";

import { Check, Copy } from "lucide-react";

import { Button, type ButtonProps } from "@/components/ui/button";
import { useCopyToClipboard } from "@/hooks/use-copy-to-clipboard";
import { cn } from "@/lib/utils";

interface CopyButtonProps extends Omit<ButtonProps, "onClick" | "children"> {
  value: string;
  label?: string;
}

export function CopyButton({
  value,
  label,
  className,
  variant = "outline",
  size = "sm",
  ...props
}: CopyButtonProps) {
  const { copied, copy } = useCopyToClipboard();

  return (
    <Button
      variant={variant}
      size={size}
      className={cn(className)}
      onClick={() => void copy(value)}
      aria-label={copied ? "Copied" : "Copy to clipboard"}
      {...props}
    >
      {copied ? (
        <Check className="text-success" />
      ) : (
        <Copy />
      )}
      {label ? <span>{copied ? "Copied" : label}</span> : null}
    </Button>
  );
}
