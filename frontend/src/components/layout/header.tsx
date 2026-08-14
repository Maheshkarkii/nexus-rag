"use client";

import * as React from "react";
import { Search, Menu, Plus, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export interface HeaderProps {
  onToggleMobileSidebar?: () => void;
  onOpenCreateProject?: () => void;
}

export function Header({ onToggleMobileSidebar, onOpenCreateProject }: HeaderProps) {
  return (
    <header className="sticky top-0 z-20 flex h-16 w-full items-center justify-between border-b border-border/80 bg-background/80 px-4 sm:px-6 backdrop-blur-md">
      {/* Left: Mobile Toggle & Page Context */}
      <div className="flex items-center gap-3">
        {onToggleMobileSidebar && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleMobileSidebar}
            aria-label="Toggle mobile menu"
            className="md:hidden h-8 w-8 text-muted-foreground"
          >
            <Menu className="h-4 w-4" />
          </Button>
        )}

        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground hidden sm:inline-block">
            Workspace:
          </span>
          <span className="text-xs font-semibold text-foreground bg-secondary/80 px-2 py-0.5 rounded-md border border-border">
            Global Research
          </span>
          <span className="text-muted-foreground/40 text-xs hidden sm:inline-block">/</span>
          <span className="text-xs font-medium text-foreground hidden sm:inline-block">
            Overview
          </span>
        </div>
      </div>

      {/* Center: Search Action Placeholder */}
      <div className="hidden lg:flex items-center">
        <button
          type="button"
          aria-label="Global search trigger"
          className="flex h-8 w-72 items-center justify-between rounded-lg border border-border bg-card/60 px-3 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <Search className="h-3.5 w-3.5 text-muted-foreground" />
            <span>Search documents, synthesis & notes...</span>
          </div>
          <kbd className="pointer-events-none hidden h-4.5 select-none items-center gap-0.5 rounded border border-border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground sm:flex">
            Ctrl K
          </kbd>
        </button>
      </div>

      {/* Right: Stage Badge & Quick Actions */}
      <div className="flex items-center gap-2.5">
        <Badge variant="success" className="gap-1 text-[10px] hidden sm:inline-flex">
          <Activity className="h-3 w-3 animate-pulse" />
          <span>Stage 4 UI System</span>
        </Badge>

        <Button
          size="sm"
          variant="default"
          onClick={onOpenCreateProject}
          className="h-8 gap-1 text-xs"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>New Project</span>
        </Button>
      </div>
    </header>
  );
}
