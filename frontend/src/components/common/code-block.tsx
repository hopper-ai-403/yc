import { cn } from "@/lib/utils";

import { CopyButton } from "./copy-button";

export function CodeBlock({
  code,
  language,
  showCopy = true,
  className,
}: {
  code: string;
  language?: string;
  showCopy?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("group relative", className)}>
      <pre className="scrollbar-thin overflow-auto rounded-md border border-border bg-muted/30 p-3 font-mono text-xs leading-5 text-foreground">
        <code data-language={language}>{code}</code>
      </pre>
      {showCopy ? (
        <CopyButton
          value={code}
          size="icon"
          variant="ghost"
          className="absolute right-2 top-2 opacity-0 transition-opacity group-hover:opacity-100"
        />
      ) : null}
    </div>
  );
}
