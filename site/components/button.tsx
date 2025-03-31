import { ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "ghost" | "small";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center text-base tracking-tight px-3 py-1 border-2 relative font-medium rounded-full",
          variant === "default" &&
            "bg-gradient-to-b from-card to-secondary border-border shadow-[2px_2px_0px_rgba(0,0,0,0.25)] border-r-primary/70 border-b-primary/70 hover:border-input hover:shadow-[3px_3px_0px_rgba(0,0,0,0.2)] hover:border-r-primary hover:border-b-primary active:bg-muted active:shadow-[1px_1px_0px_rgba(0,0,0,0.3)] active:border-primary active:translate-y-[1px] active:translate-x-[1px]",
          variant === "ghost" &&
            "bg-transparent border-transparent hover:bg-secondary hover:border-border hover:shadow-[2px_2px_0px_rgba(0,0,0,0.2)] hover:border-r-primary/70 hover:border-b-primary/70 active:bg-muted active:shadow-[1px_1px_0px_rgba(0,0,0,0.3)] active:border-primary active:translate-y-[1px] active:translate-x-[1px]",
          variant === "small" &&
            "text-sm px-2 py-0.5 bg-gradient-to-b from-card to-secondary border-border shadow-[2px_2px_0px_rgba(0,0,0,0.25)] border-r-primary/70 border-b-primary/70 hover:border-input hover:shadow-[3px_3px_0px_rgba(0,0,0,0.2)] hover:border-r-primary hover:border-b-primary active:bg-muted active:shadow-[1px_1px_0px_rgba(0,0,0,0.3)] active:border-primary active:translate-y-[1px] active:translate-x-[1px]",
          className,
        )}
        {...props}
      />
    );
  },
);

Button.displayName = "Button";
