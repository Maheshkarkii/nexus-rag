import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "outline" | "success" | "warning" | "destructive" | "info";
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variantStyles = {
    default: "border-transparent bg-primary text-primary-foreground",
    secondary: "border-border bg-secondary text-secondary-foreground",
    outline: "border-border text-foreground bg-transparent",
    success: "border-emerald-500/30 bg-emerald-950/60 text-emerald-300",
    warning: "border-amber-500/30 bg-amber-950/60 text-amber-300",
    destructive: "border-red-500/30 bg-red-950/60 text-red-300",
    info: "border-cyan-500/30 bg-cyan-950/60 text-cyan-300",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 select-none",
        variantStyles[variant],
        className
      )}
      {...props}
    />
  );
}

export { Badge };
