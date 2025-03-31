import { ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "ghost";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center font-mono font-bold text-base tracking-tight px-2 py-[1px] border-[3px]",
          variant === "default" && "bg-gradient-to-b from-card to-secondary border-border border-r-primary/70 border-b-primary/70 hover:border-input hover:border-r-primary hover:border-b-primary hover:bg-background active:bg-muted active:border-primary active:border-t-border active:border-l-border active:translate-y-[1px]",
          variant === "ghost" && "bg-transparent border-transparent hover:bg-secondary hover:border-border hover:border-r-primary/70 hover:border-b-primary/70 active:bg-muted active:border-primary active:border-t-border active:border-l-border active:translate-y-[1px]",
          className
        )}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";
