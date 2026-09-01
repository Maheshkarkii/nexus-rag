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
        <section className="relative overflow-hidden rounded-3xl border border-primary/20 bg-gradient-to-b from-primary/10 via-background to-background p-8 sm:p-12 space-y-6 shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <Badge variant="default" className="gap-2 px-3.5 py-1.5 text-xs font-semibold bg-primary text-primary-foreground shadow-md shadow-primary/20">
              <Sparkles className="h-3.5 w-3.5 animate-pulse" />
              <span>Next-Generation Research Intelligence</span>
            </Badge>

            <div className="flex items-center gap-2">
              <Link href="/projects">
                <Button size="sm" variant="default" className="text-xs gap-1.5 shadow-md shadow-primary/20">
                  <FolderKanban className="h-3.5 w-3.5" />
                  <span>Launch Workspace</span>
                </Button>
              </Link>
            </div>
          </div>

          <div className="space-y-3 max-w-3xl">
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight text-foreground leading-[1.15]">
              Autonomous Research & Multi-Document Intelligence
            </h1>
            <p className="text-sm sm:text-base text-muted-foreground leading-relaxed">
              Upload papers, datasets, and reports. Execute grounded Q&amp;A with verifiable citations, compare studies side-by-side, and automate deep multi-step synthesis.
            </p>
          </div>

          {/* Quick Action Badges */}
          <div className="flex flex-wrap items-center gap-2.5 pt-2">
            <Button
              size="sm"
              variant="default"
              onClick={() => setIsCreateModalOpen(true)}
              className="gap-2 h-9 px-4 text-xs font-semibold shadow-lg shadow-primary/25 cursor-pointer"
            >
              <Plus className="h-4 w-4" />
              <span>New Research Project</span>
            </Button>
            <Link href="/projects">
              <Button
                size="sm"
                variant="outline"
                className="gap-2 h-9 px-4 text-xs font-semibold bg-background/80 hover:bg-accent cursor-pointer"
              >
                <GitCompare className="h-4 w-4 text-primary" />
                <span>Multi-Document Comparison Studio</span>
              </Button>
            </Link>
          </div>

          {/* Easy 3-Step Guide */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-4">
            <div className="flex items-start gap-3.5 p-4 rounded-2xl border border-border/80 bg-card/60 backdrop-blur-md transition-all hover:border-primary/40 hover:shadow-md">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground font-black text-xs shadow-sm">
                1
              </div>
              <div className="space-y-1">
                <p className="text-xs font-bold text-foreground">Create Workspace</p>
                <p className="text-[11px] text-muted-foreground leading-relaxed">Isolate research papers, datasets, and knowledge graphs.</p>
              </div>
            </div>

            <div className="flex items-start gap-3.5 p-4 rounded-2xl border border-border/80 bg-card/60 backdrop-blur-md transition-all hover:border-primary/40 hover:shadow-md">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary font-black text-xs border border-primary/30 shadow-sm">
                2
              </div>
              <div className="space-y-1">
                <p className="text-xs font-bold text-foreground">Ingest &amp; Number Files</p>
                <p className="text-[11px] text-muted-foreground leading-relaxed">PDF, Word, Excel, CSV, or text extracted and chunked automatically.</p>
              </div>
            </div>

            <div className="flex items-start gap-3.5 p-4 rounded-2xl border border-border/80 bg-card/60 backdrop-blur-md transition-all hover:border-primary/40 hover:shadow-md">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary font-black text-xs border border-primary/30 shadow-sm">
                3
              </div>
              <div className="space-y-1">
                <p className="text-xs font-bold text-foreground">Compare &amp; Synthesize</p>
                <p className="text-[11px] text-muted-foreground leading-relaxed">Side-by-side matrices, cited chat answers, and automated exports.</p>
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
                <h2 className="text-lg font-bold text-foreground tracking-tight">
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
            <div className="rounded-2xl border border-dashed border-border bg-card/40 p-10 text-center space-y-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary mx-auto border border-primary/20">
                <FolderKanban className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-bold text-foreground">No research projects yet</p>
                <p className="text-xs text-muted-foreground max-w-sm mx-auto leading-relaxed">
                  Create your first workspace to begin organizing documents, datasets, and running comparative synthesis.
                </p>
              </div>
              <Button
                variant="default"
                size="sm"
                onClick={() => setIsCreateModalOpen(true)}
                className="gap-1.5 text-xs font-semibold shadow-md shadow-primary/20"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>Create Project</span>
              </Button>
            </div>
          )}

          {!isLoadingProjects && projects.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.slice(0, 6).map((project) => (
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

        {/* Core Capabilities Section */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-foreground tracking-tight">
                Full-Spectrum Platform Capabilities
              </h2>
              <p className="text-xs text-muted-foreground">
                Integrated modules for multi-document research, comparison, and grounded synthesis
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Card 1 */}
            <Card className="glass-panel-hover group relative overflow-hidden border-border/80 bg-card/60 hover:border-primary/40 transition-all">
              <CardHeader className="p-5 pb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20 mb-3 group-hover:bg-primary/20 transition-colors">
                  <FolderPlus className="h-5 w-5" />
                </div>
                <CardTitle className="text-sm font-bold">Research Workspaces</CardTitle>
                <CardDescription className="text-xs leading-relaxed">
                  Isolate documents, custom chunking parameters, and vector collections with strict project boundaries.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-5 pt-2">
                <Link href="/projects">
                  <Button size="sm" variant="outline" className="w-full text-xs gap-1.5 h-8">
                    <span>Open Workspaces</span>
                    <ArrowRight className="h-3 w-3" />
                  </Button>
                </Link>
              </CardContent>
            </Card>

            {/* Card 2 */}
            <Card className="glass-panel-hover group relative overflow-hidden border-border/80 bg-card/60 hover:border-primary/40 transition-all">
              <CardHeader className="p-5 pb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20 mb-3 group-hover:bg-primary/20 transition-colors">
                  <Upload className="h-5 w-5" />
                </div>
                <CardTitle className="text-sm font-bold">Multi-Format Ingestion</CardTitle>
                <CardDescription className="text-xs leading-relaxed">
                  Support for PDF, Word DOCX, Excel spreadsheets, CSVs, and hierarchical JSON text extraction.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-5 pt-2">
                <Link href="/projects">
                  <Button size="sm" variant="outline" className="w-full text-xs gap-1.5 h-8">
                    <span>Upload &amp; Index</span>
                    <ArrowRight className="h-3 w-3" />
                  </Button>
                </Link>
              </CardContent>
            </Card>

            {/* Card 3 */}
            <Card className="glass-panel-hover group relative overflow-hidden border-border/80 bg-card/60 hover:border-primary/40 transition-all">
              <CardHeader className="p-5 pb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20 mb-3 group-hover:bg-primary/20 transition-colors">
                  <MessageSquareQuote className="h-5 w-5" />
                </div>
                <CardTitle className="text-sm font-bold">Grounded RAG &amp; Citations</CardTitle>
                <CardDescription className="text-xs leading-relaxed">
                  Semantic retrieval with vector indexing (Qdrant), reranking, and interactive clickable citations.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-5 pt-2">
                <Link href="/projects">
                  <Button size="sm" variant="outline" className="w-full text-xs gap-1.5 h-8">
                    <span>Query Assistant</span>
                    <ArrowRight className="h-3 w-3" />
                  </Button>
                </Link>
              </CardContent>
            </Card>

            {/* Card 4 */}
            <Card className="glass-panel-hover group relative overflow-hidden border-border/80 bg-card/60 hover:border-primary/40 transition-all">
              <CardHeader className="p-5 pb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20 mb-3 group-hover:bg-primary/20 transition-colors">
                  <GitCompare className="h-5 w-5" />
                </div>
                <CardTitle className="text-sm font-bold">Document Comparison</CardTitle>
                <CardDescription className="text-xs leading-relaxed">
                  Numbered document slots for side-by-side comparative analysis of methods, results, and findings.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-5 pt-2">
                <Link href="/projects">
                  <Button size="sm" variant="outline" className="w-full text-xs gap-1.5 h-8">
                    <span>Compare Files</span>
                    <ArrowRight className="h-3 w-3" />
                  </Button>
                </Link>
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
