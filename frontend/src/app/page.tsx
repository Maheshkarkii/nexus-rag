"use client";

import * as React from "react";
import Link from "next/link";
import {
  FolderPlus,
  Upload,
  MessageSquareQuote,
  GitCompare,
  Sparkles,
  ArrowRight,
  Layers,
  Plus,
  FolderKanban,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { ProjectResponse } from "@/lib/api/types";
import { AppShell } from "@/components/layout/app-shell";
import { Container } from "@/components/ui/container";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ApiStatusCard } from "@/components/ui/api-status-card";
import { CreateProjectModal } from "@/components/projects/create-project-modal";
import { ProjectCard } from "@/components/projects/project-card";
import { EditProjectModal } from "@/components/projects/edit-project-modal";
import { DeleteProjectModal } from "@/components/projects/delete-project-modal";

export default function HomePage() {
  const [isCreateModalOpen, setIsCreateModalOpen] = React.useState<boolean>(false);
  const [editingProject, setEditingProject] = React.useState<ProjectResponse | null>(null);
  const [deletingProject, setDeletingProject] = React.useState<ProjectResponse | null>(null);

  const [projects, setProjects] = React.useState<ProjectResponse[]>([]);
  const [isLoadingProjects, setIsLoadingProjects] = React.useState<boolean>(true);

  const loadProjects = React.useCallback(async () => {
    setIsLoadingProjects(true);
    try {
      const data = await apiClient.listProjects();
      setProjects(data);
    } catch {
      // Silently fail on home page; projects page handles dedicated error states
      setProjects([]);
    } finally {
      setIsLoadingProjects(false);
    }
  }, []);

  React.useEffect(() => {
    loadProjects();
  }, [loadProjects]);

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
    <AppShell onOpenCreateProject={() => setIsCreateModalOpen(true)}>
      <Container size="lg" className="space-y-8 py-2">
        {/* Hero Section */}
        <section className="space-y-4 pt-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="default" className="gap-1.5 px-3 py-1 text-xs bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20">
              <Sparkles className="h-3.5 w-3.5" />
              <span>AI Research & Document Intelligence</span>
            </Badge>
          </div>

          <div className="space-y-2 max-w-3xl">
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight text-foreground">
              Instant Answers from Your Research Documents
            </h1>
            <p className="text-sm sm:text-base text-muted-foreground leading-relaxed">
              Upload research papers, PDFs, notes, or spreadsheets. Ask questions in natural language and receive grounded answers with exact source citations.
            </p>
          </div>

          {/* Easy 3-Step Guide for Basic Users */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
            <div className="flex items-start gap-3 p-3.5 rounded-xl border border-border/70 bg-card/40 backdrop-blur-sm">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold text-xs">
                1
              </div>
              <div className="space-y-0.5">
                <p className="text-xs font-semibold text-foreground">Create Workspace</p>
                <p className="text-[11px] text-muted-foreground leading-tight">Create a project workspace for your topic or assignment.</p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3.5 rounded-xl border border-border/70 bg-card/40 backdrop-blur-sm">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary font-bold text-xs border border-primary/20">
                2
              </div>
              <div className="space-y-0.5">
                <p className="text-xs font-semibold text-foreground">Upload Documents</p>
                <p className="text-[11px] text-muted-foreground leading-tight">Add PDF, Word, Excel, CSV, or text files easily.</p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3.5 rounded-xl border border-border/70 bg-card/40 backdrop-blur-sm">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary font-bold text-xs border border-primary/20">
                3
              </div>
              <div className="space-y-0.5">
                <p className="text-xs font-semibold text-foreground">Ask & Synthesize</p>
                <p className="text-[11px] text-muted-foreground leading-tight">Get instant cited summaries and detailed research answers.</p>
              </div>
            </div>
          </div>
        </section>

        {/* Live Backend Connection Card */}
        <section>
          <ApiStatusCard />
        </section>

        <Separator />

        {/* Active Research Projects Section */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-foreground tracking-tight">
                  Research Projects
                </h2>
                <Badge variant="secondary" className="text-[10px] font-mono">
                  {projects.length} {projects.length === 1 ? "Workspace" : "Workspaces"}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                Workspaces for organizing papers, datasets, and synthesis workflows
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Link href="/projects">
                <Button variant="ghost" size="sm" className="text-xs gap-1">
                  <span>View All</span>
                  <ArrowRight className="h-3 w-3" />
                </Button>
              </Link>
              <Button
                size="sm"
                variant="default"
                onClick={() => setIsCreateModalOpen(true)}
                className="text-xs gap-1.5"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>Create Workspace</span>
              </Button>
            </div>
          </div>

          {isLoadingProjects && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-36 rounded-xl border border-border/60 bg-card/40 p-5 animate-pulse"
                />
              ))}
            </div>
          )}

          {!isLoadingProjects && projects.length === 0 && (
            <div className="rounded-xl border border-dashed border-border bg-card/30 p-8 text-center space-y-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary mx-auto border border-primary/20">
                <FolderKanban className="h-5 w-5" />
              </div>
              <div className="space-y-1">
                <p className="text-xs font-semibold text-foreground">No research projects yet</p>
                <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                  Create your first workspace to begin organizing documents, datasets, and research.
                </p>
              </div>
              <Button
                variant="default"
                size="sm"
                onClick={() => setIsCreateModalOpen(true)}
                className="gap-1.5 text-xs"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>Create Project</span>
              </Button>
            </div>
          )}

          {!isLoadingProjects && projects.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.slice(0, 3).map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onEdit={(p) => setEditingProject(p)}
                  onDelete={(p) => setDeletingProject(p)}
                />
              ))}
            </div>
          )}
        </section>

        <Separator />

        {/* Core Capabilities & Visual Placeholders for Future Stages */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-foreground tracking-tight">
                Core Research Capabilities
              </h2>
              <p className="text-xs text-muted-foreground">
                Upcoming modules for document ingestion, grounded RAG, and multi-document comparison
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Card 1: Start a Research Project */}
            <Card className="glass-panel-hover group relative overflow-hidden border-border/80 bg-card/60">
              <CardHeader className="p-5 pb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20 mb-3 group-hover:bg-primary/20 transition-colors">
                  <FolderPlus className="h-5 w-5" />
                </div>
                <CardTitle className="text-sm font-semibold">Research Workspaces</CardTitle>
                <CardDescription className="text-xs line-clamp-2">
                  Organize literature reviews, datasets, and analytical notes with full CRUD support.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-5 pt-2">
                <Link href="/projects">
                  <Button size="sm" variant="outline" className="w-full text-xs gap-1.5 h-8">
                    <span>Manage Projects</span>
                    <ArrowRight className="h-3 w-3" />
                  </Button>
                </Link>
              </CardContent>
            </Card>

            {/* Card 2: Upload Documents */}
            <Card className="glass-panel-hover group relative overflow-hidden border-border/80 bg-card/60">
              <CardHeader className="p-5 pb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-info/10 text-info border border-info/20 mb-3 group-hover:bg-info/20 transition-colors">
                  <Upload className="h-5 w-5" />
                </div>
                <CardTitle className="text-sm font-semibold">Upload Documents</CardTitle>
                <CardDescription className="text-xs line-clamp-2">
                  Ingest PDF, DOCX, TXT, Markdown, CSV, XLSX, and JSON files for semantic chunking.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-5 pt-2">
                <Button size="sm" variant="outline" disabled className="w-full text-xs gap-1.5 h-8 opacity-75">
                  <span>Ingestion (Stage 8)</span>
                </Button>
              </CardContent>
            </Card>

            {/* Card 3: Ask Questions */}
            <Card className="glass-panel-hover group relative overflow-hidden border-border/80 bg-card/60">
              <CardHeader className="p-5 pb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-success/10 text-success border border-success/20 mb-3 group-hover:bg-success/20 transition-colors">
                  <MessageSquareQuote className="h-5 w-5" />
                </div>
                <CardTitle className="text-sm font-semibold">Grounded RAG</CardTitle>
                <CardDescription className="text-xs line-clamp-2">
                  Perform grounded RAG synthesis with evidence citations and verifiable source links.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-5 pt-2">
                <Button size="sm" variant="outline" disabled className="w-full text-xs gap-1.5 h-8 opacity-75">
                  <span>RAG Query (Stage 10)</span>
                </Button>
              </CardContent>
            </Card>

            {/* Card 4: Compare Sources */}
            <Card className="glass-panel-hover group relative overflow-hidden border-border/80 bg-card/60">
              <CardHeader className="p-5 pb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-warning/10 text-warning border border-warning/20 mb-3 group-hover:bg-warning/20 transition-colors">
                  <GitCompare className="h-5 w-5" />
                </div>
                <CardTitle className="text-sm font-semibold">Compare Sources</CardTitle>
                <CardDescription className="text-xs line-clamp-2">
                  Contrast methodologies, uncover research gaps, and generate cross-study matrices.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-5 pt-2">
                <Button size="sm" variant="outline" disabled className="w-full text-xs gap-1.5 h-8 opacity-75">
                  <span>Compare (Stage 11)</span>
                </Button>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* Foundation Architecture Summary */}
        <section className="rounded-xl border border-border/80 bg-card/40 p-5 sm:p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary border border-border text-foreground">
                <Layers className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-foreground">
                  Architecture & Foundation Roadmap
                </h3>
                <p className="text-xs text-muted-foreground">
                  Monorepo infrastructure, relational database, and frontend project management
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="success" className="text-[11px]">
                Stage 1–7 Active
              </Badge>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="rounded-lg border border-border/50 bg-background/50 p-3 space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Stage 1</span>
              <p className="font-semibold text-foreground">Docker Monorepo</p>
              <p className="text-[11px] text-emerald-400 font-medium">✓ Ready</p>
            </div>
            <div className="rounded-lg border border-border/50 bg-background/50 p-3 space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Stage 2</span>
              <p className="font-semibold text-foreground">FastAPI Backend</p>
              <p className="text-[11px] text-emerald-400 font-medium">✓ 34 Tests Passing</p>
            </div>
            <div className="rounded-lg border border-border/50 bg-background/50 p-3 space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Stage 3 & 6</span>
              <p className="font-semibold text-foreground">PostgreSQL Workspaces</p>
              <p className="text-[11px] text-emerald-400 font-medium">✓ Full CRUD</p>
            </div>
            <div className="rounded-lg border border-border/50 bg-background/50 p-3 space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Stage 5 & 7</span>
              <p className="font-semibold text-foreground">API Client & UI</p>
              <p className="text-[11px] text-indigo-400 font-medium">✓ Live UI Connected</p>
            </div>
          </div>
        </section>
      </Container>

      {/* Modals */}
      <CreateProjectModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
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
    </AppShell>
  );
}
