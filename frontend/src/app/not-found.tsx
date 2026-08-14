import * as React from "react";
import Link from "next/link";
import { FileQuestion, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-[70vh] w-full flex-col items-center justify-center p-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-secondary border border-border text-muted-foreground mb-4">
        <FileQuestion className="h-8 w-8" />
      </div>
      <h1 className="text-xl font-bold text-foreground mb-1">
        Page Not Found
      </h1>
      <p className="text-xs text-muted-foreground max-w-sm mb-6 leading-relaxed">
        The requested research workspace or page route does not exist in the application.
      </p>
      <Link href="/">
        <Button variant="default" size="sm" className="gap-2 text-xs">
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Return to Research Home</span>
        </Button>
      </Link>
    </div>
  );
}
