"use client";

import * as React from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  React.useEffect(() => {
    // Log safe error trace to browser console for frontend debugging
    console.error("Route error boundary triggered:", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] w-full flex-col items-center justify-center p-6 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-destructive/10 border border-destructive/20 text-destructive mb-4">
        <AlertCircle className="h-7 w-7" />
      </div>
      <h2 className="text-base font-semibold text-foreground mb-1">
        Workspace Rendering Error
      </h2>
      <p className="text-xs text-muted-foreground max-w-md mb-6 leading-relaxed">
        An unexpected error occurred while rendering this interface. The frontend design system boundary has caught this issue.
      </p>
      <Button variant="secondary" onClick={() => reset()} className="gap-2 text-xs">
        <RefreshCw className="h-3.5 w-3.5" />
        <span>Try Again</span>
      </Button>
    </div>
  );
}
