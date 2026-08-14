"use client";

import * as React from "react";
import { FolderKanban, Plus, Search, RefreshCw, AlertCircle } from "lucide-react";
import { apiClient } from "@/lib/api";
import { ProjectResponse } from "@/lib/api/types";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { ProjectCard } from "@/components/projects/project-card";
import { CreateProjectModal } from "@/components/projects/create-project-modal";
import { EditProjectModal } from "@/components/projects/edit-project-modal";
import { DeleteProjectModal } from "@/components/projects/delete-project-modal";

export default function ProjectsPage() {
  const [projects, setProjects] = React.useState<ProjectResponse[]>([]);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  // Modals state
  const [isCreateOpen, setIsCreateOpen] = React.useState(false);
  const [editingProject, setEditingProject] = React.useState<ProjectResponse | null>(null);
  const [deletingProject, setDeletingProject] = React.useState<ProjectResponse | null>(null);

  const fetchProjects = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.listProjects();
      setProjects(data);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Unable to load research projects. Please verify the backend is running.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  // Filter projects by search query
  const filteredProjects = React.useMemo(() => {
    if (!searchQuery.trim()) return projects;
    const q = searchQuery.toLowerCase().trim();
    return projects.filter(
      (p) => p.name.toLowerCase().includes(q) || (p.description && p.description.toLowerCase().includes(q))
    );
  }, [projects, searchQuery]);

  // Handlers for modal completions
  const handleCreated = (newProject: ProjectResponse) => {
    setProjects((prev) => [newProject, ...prev]);
  };

  const handleUpdated = (updated: ProjectResponse) => {
    setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
  };

  const handleDeleted = (deletedId: string) => {
    setProjects((prev) => prev.filter((p) => p.id !== deletedId));
  };

  return (
    <Container className="py-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border/60">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-xl font-bold tracking-tight text-foreground">Research Projects</h1>
            <Badge variant="secondary" className="text-[10px] font-mono">
              {projects.length} {projects.length === 1 ? "Workspace" : "Workspaces"}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Organize documents, datasets, grounded RAG queries, and autonomous research workflows.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchProjects}
            disabled={isLoading}
            title="Refresh projects"
            className="gap-1.5"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">Refresh</span>
          </Button>

          <Button
            variant="default"
            size="sm"
            onClick={() => setIsCreateOpen(true)}
            className="gap-1.5"
          >
            <Plus className="h-4 w-4" />
            <span>Create Project</span>
          </Button>
        </div>
      </div>

      {/* Search & Filter Bar */}
      {projects.length > 0 && (
        <div className="flex items-center justify-between gap-4">
          <div className="relative w-full max-w-sm">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search workspaces by title or description..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 text-xs h-9"
            />
          </div>
        </div>
      )}

      {/* Error State */}
      {error && !isLoading && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-5 text-destructive flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold">Unable to load research projects</p>
              <p className="text-xs text-destructive/80 leading-relaxed mt-0.5">{error}</p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={fetchProjects} className="shrink-0">
            Try Again
          </Button>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-44 rounded-xl border border-border/60 bg-card/40 p-5 animate-pulse flex flex-col justify-between"
            >
              <div className="space-y-2.5">
                <div className="h-4 w-1/3 bg-muted rounded" />
                <div className="h-4 w-2/3 bg-muted/60 rounded" />
                <div className="h-3 w-full bg-muted/40 rounded mt-2" />
              </div>
              <div className="h-3 w-1/2 bg-muted/30 rounded" />
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && projects.length === 0 && (
        <EmptyState
          icon={<FolderKanban className="h-6 w-6 text-primary" />}
          title="No research projects yet"
          description="Create your first research project to begin organizing documents, datasets, and research workflows."
          action={
            <Button
              variant="default"
              size="sm"
              onClick={() => setIsCreateOpen(true)}
              className="gap-1.5"
            >
              <Plus className="h-4 w-4" />
              <span>Create Project</span>
            </Button>
          }
        />
      )}

      {/* Search No Results */}
      {!isLoading && !error && projects.length > 0 && filteredProjects.length === 0 && (
        <div className="rounded-xl border border-dashed border-border bg-card/30 p-8 text-center space-y-2">
          <p className="text-xs font-semibold text-foreground">No matching workspaces found</p>
          <p className="text-xs text-muted-foreground">
            No projects matched &ldquo;{searchQuery}&rdquo;. Try a different search term.
          </p>
          <Button variant="ghost" size="sm" onClick={() => setSearchQuery("")} className="text-xs mt-2">
            Clear Search
          </Button>
        </div>
      )}

      {/* Projects Grid */}
      {!isLoading && !error && filteredProjects.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredProjects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onEdit={(p) => setEditingProject(p)}
              onDelete={(p) => setDeletingProject(p)}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      <CreateProjectModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSuccess={handleCreated}
      />

      <EditProjectModal
        project={editingProject}
        isOpen={Boolean(editingProject)}
        onClose={() => setEditingProject(null)}
        onSuccess={handleUpdated}
      />

      <DeleteProjectModal
        project={deletingProject}
        isOpen={Boolean(deletingProject)}
        onClose={() => setDeletingProject(null)}
        onSuccess={handleDeleted}
      />
    </Container>
  );
}
