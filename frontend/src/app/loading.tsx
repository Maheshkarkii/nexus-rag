import * as React from "react";
import { Sparkles } from "lucide-react";

export default function Loading() {
  return (
    <div className="flex min-h-[60vh] w-full flex-col items-center justify-center gap-4 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20 text-primary">
        <Sparkles className="h-6 w-6 animate-pulse" />
      </div>
      <div className="space-y-1.5">
        <h3 className="text-sm font-semibold text-foreground tracking-tight">
          Preparing Research Workspace...
        </h3>
        <p className="text-xs text-muted-foreground font-mono">
          Loading layout and design tokens
        </p>
      </div>
    </div>
  );
}
