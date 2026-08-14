"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  FolderKanban,
  FileText,
  Search,
  GitCompare,
  Settings,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  Database,
  Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

export interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  isStagePlaceholder?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Home", href: "/", icon: Layers },
  { label: "Research Projects", href: "/projects", icon: FolderKanban, badge: "Workspaces" },
  { label: "Documents", href: "/documents", icon: FileText, isStagePlaceholder: true },
  { label: "Research Queries", href: "/queries", icon: Search, isStagePlaceholder: true },
  { label: "Comparisons", href: "/comparisons", icon: GitCompare, isStagePlaceholder: true },
  { label: "Settings", href: "/settings", icon: Settings },
];

export interface SidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  className?: string;
}

export function Sidebar({ isCollapsed, onToggleCollapse, className }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-border bg-card/60 backdrop-blur-md transition-all duration-300 select-none h-screen sticky top-0 z-30",
        isCollapsed ? "w-16" : "w-64",
        className
      )}
    >
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-between px-4 border-b border-border/80">
        <Link href="/" className="flex items-center gap-3 overflow-hidden group">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 border border-primary/30 text-primary transition-colors group-hover:bg-primary/20">
            <Sparkles className="h-4 w-4 text-primary animate-pulse-slow" />
          </div>
          {!isCollapsed && (
            <div className="flex flex-col overflow-hidden text-left">
              <span className="text-sm font-bold tracking-tight text-foreground truncate">
                AI Research
              </span>
              <span className="text-[10px] font-mono text-muted-foreground truncate">
                Assistant Platform
              </span>
            </div>
          )}
        </Link>

        <button
          onClick={onToggleCollapse}
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="hidden md:flex h-7 w-7 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
        >
          {isCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
        </button>
      </div>

      {/* Navigation Group */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        <div className="px-2 pb-2">
          {!isCollapsed ? (
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/80">
              Navigation
            </span>
          ) : (
            <div className="h-4 border-b border-border/50 mx-auto w-4" />
          )}
        </div>

        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          const Icon = item.icon;

          return (
            <Link
              key={item.label}
              href={item.href}
              title={isCollapsed ? item.label : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-xs font-medium transition-all group",
                isActive
                  ? "bg-primary text-primary-foreground shadow-sm shadow-primary/20 font-semibold"
                  : "text-muted-foreground hover:bg-accent/80 hover:text-foreground"
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0 transition-transform group-hover:scale-105",
                  isActive ? "text-primary-foreground" : "text-muted-foreground group-hover:text-foreground"
                )}
              />
              {!isCollapsed && (
                <div className="flex flex-1 items-center justify-between overflow-hidden">
                  <span className="truncate">{item.label}</span>
                  {item.badge && (
                    <Badge variant={isActive ? "secondary" : "outline"} className="text-[9px] px-1.5 py-0">
                      {item.badge}
                    </Badge>
                  )}
                </div>
              )}
            </Link>
          );
        })}
      </div>

      {/* Bottom Workspace Status Info */}
      <div className="p-3 border-t border-border/80">
        {!isCollapsed ? (
          <div className="rounded-lg border border-border/60 bg-muted/40 p-2.5 flex items-center gap-2.5">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-accent text-primary">
              <Database className="h-3.5 w-3.5" />
            </div>
            <div className="flex-1 overflow-hidden">
              <p className="text-[11px] font-semibold text-foreground truncate">PostgreSQL 16</p>
              <p className="text-[10px] font-mono text-muted-foreground truncate">Stage 7 Active</p>
            </div>
          </div>
        ) : (
          <div className="flex justify-center" title="PostgreSQL 16 (Stage 7)">
            <div className="h-2 w-2 rounded-full bg-emerald-400" />
          </div>
        )}
      </div>
    </aside>
  );
}
