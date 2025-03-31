"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";
import { CopyIcon, CheckIcon } from "lucide-react";

interface CodeBlockProps {
  code: string;
  language?: string;
  className?: string;
}

interface InlineCodeProps {
  code: string;
  className?: string;
}

export const CodeBlock: React.FC<CodeBlockProps> = ({ 
  code, 
  language, 
  className 
}) => {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={cn(
      "relative my-4 rounded-md border border-border bg-muted/50 p-4 font-mono text-sm",
      className
    )}>
      <TooltipProvider>
        <Tooltip open={copied}>
          <TooltipTrigger asChild>
            <button
              onClick={copyToClipboard}
              className="absolute right-3 top-3 rounded-md border border-border bg-background p-1.5 hover:bg-muted hover:border-input transition-colors focus:outline-none focus:ring-2 focus:ring-ring group"
              aria-label="Copy code to clipboard"
            >
              {copied ? (
                <CheckIcon className="h-4 w-4 text-green-500" />
              ) : (
                <CopyIcon className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors" />
              )}
            </button>
          </TooltipTrigger>
          <TooltipContent>
            Copied to clipboard
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
      
      {language && (
        <div className="mb-2 text-xs text-muted-foreground">
          {language}
        </div>
      )}
      
      <pre className="overflow-x-auto">{code}</pre>
    </div>
  );
};

export const InlineCode: React.FC<InlineCodeProps> = ({ 
  code, 
  className 
}) => {
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
              "inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/30 px-2 py-0.5 font-mono text-sm transition-colors hover:bg-muted hover:border-input group",
              className
            )}
            aria-label="Copy code to clipboard"
          >
            <span>{code}</span>
            <CopyIcon className="h-3.5 w-3.5 text-muted-foreground transition-colors group-hover:text-foreground" />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          Copied to clipboard
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}; 