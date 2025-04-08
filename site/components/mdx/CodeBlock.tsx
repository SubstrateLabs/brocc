"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/ui/tooltip";
import { CopyIcon } from "lucide-react";

interface InlineCodeProps {
  code: string;
  className?: string;
}

export const InlineCode: React.FC<InlineCodeProps> = ({ code, className }) => {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <TooltipProvider>
      <Tooltip open={copied}>
        <TooltipTrigger asChild>
          <button
            onClick={copyToClipboard}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border border-green-500 bg-muted/30 px-2 py-0.5 font-mono text-sm transition-colors hover:bg-muted hover:border-input group",
              className,
            )}
            aria-label="Copy code to clipboard"
          >
            <span>{code}</span>
            <CopyIcon className="h-3.5 w-3.5 text-muted-foreground transition-colors group-hover:text-foreground" />
          </button>
        </TooltipTrigger>
        <TooltipContent>Copied to clipboard</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};
