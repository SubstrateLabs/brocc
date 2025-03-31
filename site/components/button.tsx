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
          "inline-flex items-center justify-center font-mono font-bold text-lg tracking-tight px-2 py-[1px] border-[3px]",
          variant === "default" && "bg-[#f0f0f0] border-[#cacaca] border-r-[#404040] border-b-[#404040] hover:border-[#b0b0b0] hover:border-r-[#202020] hover:border-b-[#202020] hover:bg-white active:bg-[#e8e8e8] active:border-[#404040] active:border-t-[#cacaca] active:border-l-[#cacaca] active:translate-y-[1px]",
          variant === "ghost" && "bg-transparent border-transparent hover:bg-[#f0f0f0] hover:border-[#cacaca] hover:border-r-[#404040] hover:border-b-[#404040] active:bg-[#e8e8e8] active:border-[#404040] active:border-t-[#cacaca] active:border-l-[#cacaca] active:translate-y-[1px]",
          className
        )}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";
