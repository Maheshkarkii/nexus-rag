"use client";

import * as React from "react";
import Link from "next/link";
import { FolderKanban, Calendar, Clock, ArrowUpRight, Edit3, Trash2 } from "lucide-react";
import { ProjectResponse } from "@/lib/api/types";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export interface ProjectCardProps {
  project: ProjectResponse;
  onEdit?: (project: ProjectResponse) => void;
  onDelete?: (project: ProjectResponse) => void;
}

export function ProjectCard({ project, onEdit, onDelete }: ProjectCardProps) {
  // Format timestamps nicely
  const createdFormatted = React.useMemo(() => {
    try {
      return new Date(project.created_at).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch {
      return project.created_at;
    }
  }, [project.created_at]);

  const updatedFormatted = React.useMemo(() => {
    try {
      return new Date(project.updated_at).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      });
    } catch {
      return project.updated_at;
    }
  }, [project.updated_at]);

  return (
    <Card className="group relative flex flex-col justify-between overflow-hidden border-border/80 bg-card/60 transition-all duration-200 hover:border-primary/50 hover:bg-card hover:shadow-lg hover:shadow-primary/5">
      <div>
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 border border-primary/25 text-primary transition-colors group-hover:bg-primary/20">
                <FolderKanban className="h-4 w-4" />
              </div>
              <Badge variant="outline" className="text-[10px] font-mono font-normal text-muted-foreground">
                Workspace
              </Badge>
            </div>

            <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100 transition-opacity">
              {onEdit && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  onClick={() => onEdit(project)}
                  title="Edit workspace"
                  aria-label="Edit workspace"
                >
                  <Edit3 className="h-3.5 w-3.5" />
                </Button>
              )}
              {onDelete && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                  onClick={() => onDelete(project)}
                  title="Delete workspace"
                  aria-label="Delete workspace"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          </div>

          <CardTitle className="mt-3 text-base font-semibold tracking-tight text-foreground transition-colors group-hover:text-primary">
            <Link href={`/projects/${project.id}`} className="hover:underline focus:outline-none flex items-center gap-1.5">
              <span className="truncate">{project.name}</span>
              <ArrowUpRight className="h-3.5 w-3.5 shrink-0 opacity-0 transition-all group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </Link>
          </CardTitle>

          <CardDescription className="line-clamp-2 text-xs leading-relaxed text-muted-foreground mt-1">
            {project.description || "No description provided for this research workspace."}
          </CardDescription>
        </CardHeader>

        <CardContent className="pb-3">
          <div className="flex flex-wrap items-center gap-y-1.5 gap-x-4 text-[11px] text-muted-foreground/80 font-mono">
            <div className="flex items-center gap-1.5">
              <Calendar className="h-3 w-3 text-muted-foreground/60" />
              <span>Created {createdFormatted}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Clock className="h-3 w-3 text-muted-foreground/60" />
              <span>Updated {updatedFormatted}</span>
            </div>
          </div>
        </CardContent>
      </div>

      <CardFooter className="pt-2 border-t border-border/40 flex items-center justify-between">
        <span className="text-[10px] font-mono text-muted-foreground/60 truncate max-w-[150px]">
          ID: {project.id.slice(0, 8)}...
        </span>
        <Link href={`/projects/${project.id}`}>
          <Button variant="secondary" size="sm" className="h-7 text-xs font-medium gap-1">
            <span>Open Workspace</span>
            <ArrowUpRight className="h-3 w-3" />
          </Button>
        </Link>
      </CardFooter>
    </Card>
  );
}
