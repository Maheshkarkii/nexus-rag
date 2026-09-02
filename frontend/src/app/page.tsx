"use client";

import * as React from "react";
import {
  Upload,
  Bot,
  GitCompare,
  SlidersHorizontal,
  Sparkles,
  RotateCcw,
  FileText,
  CheckCircle2,
  Trash2,
  Send,
  Loader2,
  CheckSquare,
  Square,
  Plus,
  RefreshCw,
  BookOpen,
  Zap,
  FileCode,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { ProjectResponse, DocumentResponse } from "@/lib/api/types";
import { AppShell } from "@/components/layout/app-shell";
import { Container } from "@/components/ui/container";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DocumentComparisonView } from "@/components/projects/document-comparison-view";
import { RagConfig, DEFAULT_RAG_CONFIG } from "@/components/projects/rag-config-modal";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface CitationSource {
  source_id: string;
  document_id?: string;
  chunk_id?: string;
  filename: string;
  location?: {
    page_number?: number | null;
    section_title?: string | null;
    paragraph_index?: number | null;
    sheet_name?: string | null;
  };
  relevance_score?: number;
  preview: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: CitationSource[];
  statusMessage?: string;
  latencyMs?: number;
}

const PRESETS = [
  {
    id: "balanced",
    name: "Balanced",
    icon: Sparkles,
    badge: "Recommended",
    config: { topK: 8, chunkSize: 500, chunkOverlap: 100 },
  },
  {
    id: "academic",
    name: "Academic Papers",
    icon: BookOpen,
    badge: "Large Chunks",
    config: { topK: 12, chunkSize: 1000, chunkOverlap: 200 },
  },
  {
    id: "precise",
    name: "Fast Fact-Checking",
    icon: Zap,
    badge: "Pinpoint",
    config: { topK: 4, chunkSize: 300, chunkOverlap: 50 },
  },
  {
    id: "tabular",
    name: "CSV / Excel / JSON",
    icon: FileCode,
    badge: "Tabular",
    config: { topK: 10, chunkSize: 250, chunkOverlap: 30 },
  },
];

export default function HomePage() {
  // Main Tab: "rag" for Regular RAG & "compare" for Document Comparison
  const [activeSection, setActiveSection] = React.useState<"rag" | "compare">("rag");

  // Project state (auto-provisioned direct workspace)
  const [activeProject, setActiveProject] = React.useState<ProjectResponse | null>(null);
  const [isLoadingProject, setIsLoadingProject] = React.useState<boolean>(true);

  // Document states
  const [documents, setDocuments] = React.useState<DocumentResponse[]>([]);
  const [isUploading, setIsUploading] = React.useState<boolean>(false);
  const [uploadStatus, setUploadStatus] = React.useState<string | null>(null);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [processingDocs, setProcessingDocs] = React.useState<Record<string, string>>({});
  const [selectedDocIds, setSelectedDocIds] = React.useState<string[]>([]);
  const [searchEntireProject, setSearchEntireProject] = React.useState<boolean>(true);

  // Hyperparameters
  const [ragConfig, setRagConfig] = React.useState<RagConfig>(DEFAULT_RAG_CONFIG);
  const [activePreset, setActivePreset] = React.useState<string | null>("balanced");
  const [showTuning, setShowTuning] = React.useState<boolean>(false);

  // Chat / Q&A States
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [queryInput, setQueryInput] = React.useState("");
  const [isGenerating, setIsGenerating] = React.useState(false);
  const [activeConvId, setActiveConvId] = React.useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = React.useState<CitationSource | null>(null);

  const messagesEndRef = React.useRef<HTMLDivElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // Auto-scroll chat
  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isGenerating]);

  // Initialize workspace automatically
  const initProject = React.useCallback(async () => {
    setIsLoadingProject(true);
    try {
      const list = await apiClient.listProjects();
      if (list && list.length > 0) {
        const def = list.find((p) => p.name === "Default Research Workspace") || list[0];
        setActiveProject(def);
      } else {
        const created = await apiClient.createProject({
          name: "Default Research Workspace",
          description: "Default workspace for document ingestion, Q&A and comparisons.",
        });
        setActiveProject(created);
      }
    } catch (err) {
      console.error("Failed to initialize project:", err);
    } finally {
      setIsLoadingProject(false);
    }
  }, []);

  React.useEffect(() => {
    initProject();
  }, [initProject]);

  // Load documents
  const fetchDocuments = React.useCallback(async () => {
    if (!activeProject) return;
    try {
      const docs = await apiClient.listDocuments(activeProject.id);
      setDocuments(docs);
    } catch (err) {
      console.error("Failed to fetch documents:", err);
    }
  }, [activeProject]);

  React.useEffect(() => {
    if (activeProject) {
      fetchDocuments();
    }
  }, [activeProject, fetchDocuments]);

  // File Upload
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !activeProject) return;

    setErrorMessage(null);
    setIsUploading(true);
    setUploadStatus(`Uploading & processing "${file.name}"...`);

    try {
      const uploadedDoc = await apiClient.uploadDocument(activeProject.id, file, { timeoutMs: 120000 });
      setUploadStatus("Extracting text and indexing vectors with current settings...");
      await handleProcessDoc(uploadedDoc.id);
      await fetchDocuments();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to upload file.";
      setErrorMessage(msg);
    } finally {
      setIsUploading(false);
      setUploadStatus(null);
      if (event.target) {
        event.target.value = "";
      }
    }
  };

  // Run full ingestion pipeline
  const handleProcessDoc = async (docId: string, customConfig?: RagConfig) => {
    if (!activeProject) return;
    setProcessingDocs((prev) => ({ ...prev, [docId]: "Processing pipeline..." }));
    const cfg = customConfig || ragConfig;
    try {
      await apiClient.runDocumentPipeline(
        activeProject.id,
        docId,
        {
          chunkSize: cfg.chunkSize,
          chunkOverlap: cfg.chunkOverlap,
        },
        { timeoutMs: 180000 }
      );
      setProcessingDocs((prev) => {
        const copy = { ...prev };
        delete copy[docId];
        return copy;
      });
      await fetchDocuments();
    } catch (err: unknown) {
      console.error(err);
      setProcessingDocs((prev) => ({ ...prev, [docId]: "Failed" }));
      const msg = err instanceof Error ? err.message : "Pipeline processing failed.";
      setErrorMessage(msg);
      await fetchDocuments();
    }
  };

  // Delete document
  const handleDeleteDoc = async (docId: string) => {
    if (!activeProject || !confirm("Are you sure you want to delete this document?")) return;
    try {
      await apiClient.deleteDocument(activeProject.id, docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      setSelectedDocIds((prev) => prev.filter((id) => id !== docId));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete document.";
      setErrorMessage(msg);
    }
  };

  // Hyperparameter changes
  const handlePresetSelect = (preset: (typeof PRESETS)[0]) => {
    setRagConfig(preset.config);
    setActivePreset(preset.id);
  };

  const handleHyperparamChange = <K extends keyof RagConfig>(key: K, value: number) => {
    setActivePreset(null);
    setRagConfig((prev) => {
      const next = { ...prev, [key]: value };
      if (key === "chunkSize" && next.chunkOverlap >= value) {
        next.chunkOverlap = Math.max(0, Math.floor(value * 0.2));
      }
      if (key === "chunkOverlap" && value >= next.chunkSize) {
        next.chunkOverlap = Math.max(0, next.chunkSize - 50);
      }
      return next;
    });
  };

  // Submit Q&A Query
  const handleSubmitQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryInput.trim() || !activeProject || isGenerating) return;

    let convId = activeConvId;
    if (!convId) {
      try {
        const newSessionObj = (await apiClient.createConversation(
          activeProject.id,
          "Research Query Session"
        )) as { id: string };
        setActiveConvId(newSessionObj.id);
        convId = newSessionObj.id;
      } catch {
        // Continue even if session create fails
      }
    }

    const userMsg: Message = { role: "user", content: queryInput };
    setMessages((prev) => [...prev, userMsg]);
    setQueryInput("");
    setIsGenerating(true);

    const assistantPlaceholderIdx = messages.length + 1;
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", citations: [], statusMessage: "Searching knowledge base..." },
    ]);

    const apiBaseUrl = apiClient.baseUrl;
    const askStreamUrl = `${apiBaseUrl}/api/v1/projects/${activeProject.id}/ask/stream`;

    try {
      const response = await fetch(askStreamUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: userMsg.content,
          top_k: ragConfig.topK,
          document_ids: searchEntireProject ? null : selectedDocIds,
          conversation_id: convId,
        }),
      });

      if (!response.ok) {
        throw new Error(`Query failed with status ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("Stream reader not available.");

      let partialData = "";
      let answerText = "";
      let activeCitations: CitationSource[] = [];

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        partialData += decoder.decode(value, { stream: true });
        const lines = partialData.split("\n\n");
        partialData = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          const eventMatch = line.match(/^event:\s*(.+)$/m);
          const dataMatch = line.match(/^data:\s*(.+)$/m);

          if (eventMatch && dataMatch) {
            const eventType = eventMatch[1].trim();
            const dataStr = dataMatch[1].trim();

            try {
              const dataObj = JSON.parse(dataStr);
              if (eventType === "status" || eventType === "research_started") {
                const msgText = dataObj.message || "Searching context...";
                setMessages((prev) => {
                  const copy = [...prev];
                  if (copy[assistantPlaceholderIdx]) {
                    copy[assistantPlaceholderIdx].statusMessage = msgText;
                  }
                  return copy;
                });
              } else if (eventType === "token") {
                answerText += dataObj.content;
                setMessages((prev) => {
                  const copy = [...prev];
                  if (copy[assistantPlaceholderIdx]) {
                    copy[assistantPlaceholderIdx].content = answerText;
                  }
                  return copy;
                });
              } else if (eventType === "citations") {
                activeCitations = (dataObj.citations || []) as CitationSource[];
                setMessages((prev) => {
                  const copy = [...prev];
                  if (copy[assistantPlaceholderIdx]) {
                    copy[assistantPlaceholderIdx].citations = activeCitations;
                  }
                  return copy;
                });
              } else if (eventType === "complete") {
                setMessages((prev) => {
                  const copy = [...prev];
                  if (copy[assistantPlaceholderIdx]) {
                    copy[assistantPlaceholderIdx].latencyMs = dataObj.metadata?.latency_ms;
                    copy[assistantPlaceholderIdx].statusMessage = undefined;
                  }
                  return copy;
                });
              }
            } catch (err) {
              console.error("Stream parse error:", err);
            }
          }
        }
      }
    } catch (err: unknown) {
      console.error(err);
      setMessages((prev) => {
        const copy = [...prev];
        if (copy[assistantPlaceholderIdx]) {
          copy[assistantPlaceholderIdx].content = "Failed to retrieve grounded response. Please verify documents are ready.";
          copy[assistantPlaceholderIdx].statusMessage = undefined;
        }
        return copy;
      });
    } finally {
      setIsGenerating(false);
    }
  };

  const readyDocuments = documents.filter((d) => d.status === "ready");

  return (
    <AppShell>
      <Container size="xl" className="space-y-6 py-2 max-w-[1500px]">
        {/* Simple 2-Section Navigation Switcher */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl border border-border/80 bg-card/80 backdrop-blur-md shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20">
              <Sparkles className="h-5 w-5 animate-pulse" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-foreground">AI Research Platform</h1>
              <p className="text-xs text-muted-foreground">Select a section below to get started</p>
            </div>
          </div>

          <div className="flex items-center p-1 bg-muted/60 border border-border rounded-xl">
            {/* Section 1 Switcher */}
            <button
              onClick={() => setActiveSection("rag")}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeSection === "rag"
                  ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Bot className="h-4 w-4" />
              <span>1. Regular RAG &amp; Q&amp;A</span>
            </button>

            {/* Section 2 Switcher */}
            <button
              onClick={() => setActiveSection("compare")}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeSection === "compare"
                  ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <GitCompare className="h-4 w-4" />
              <span>2. Document Comparison</span>
            </button>
          </div>
        </div>

        {/* Global Error Banner */}
        {errorMessage && (
          <div className="flex items-center justify-between gap-2 text-xs font-medium text-destructive bg-destructive/10 border border-destructive/30 rounded-xl p-3.5 shadow-sm">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-destructive animate-ping shrink-0" />
              <span>{errorMessage}</span>
            </div>
            <button
              onClick={() => setErrorMessage(null)}
              className="text-muted-foreground hover:text-foreground text-xs px-2 py-0.5 rounded cursor-pointer"
            >
              ✕
            </button>
          </div>
        )}

        {/* SECTION 1: REGULAR RAG */}
        {activeSection === "rag" && (
          <div className="space-y-5">
            {/* Upload & Hyperparameter Action Header */}
            <Card className="border-border/80 bg-card/60 backdrop-blur-sm shadow-sm">
              <CardContent className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-foreground">Regular RAG Studio</span>
                    <Badge variant="secondary" className="text-[10px] font-mono">
                      {readyDocuments.length} Ready Files
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Directly upload documents, tune retrieval parameters, and ask questions with exact citations.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2.5">
                  <input
                    type="file"
                    ref={fileInputRef}
                    className="hidden"
                    onChange={handleFileUpload}
                    accept=".pdf,.docx,.txt,.csv,.xlsx,.xls,.json"
                    disabled={isUploading || !activeProject}
                  />

                  {/* Direct Upload Button */}
                  <Button
                    size="md"
                    variant="default"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploading || !activeProject}
                    className="gap-2 h-9 px-4 text-xs font-semibold cursor-pointer shadow-sm"
                  >
                    {isUploading ? (
                      <Loader2 className="h-4 w-4 animate-spin text-primary-foreground" />
                    ) : (
                      <Upload className="h-4 w-4" />
                    )}
                    <span>{isUploading ? "Uploading..." : "Upload Document"}</span>
                  </Button>

                  {/* Hyperparameter Tuning Toggle */}
                  <Button
                    size="md"
                    variant="outline"
                    onClick={() => setShowTuning((prev) => !prev)}
                    className={`gap-1.5 h-9 px-3.5 text-xs font-medium border-border/80 cursor-pointer ${
                      showTuning ? "bg-accent text-primary font-semibold" : "bg-card text-muted-foreground"
                    }`}
                  >
                    <SlidersHorizontal className="h-3.5 w-3.5" />
                    <span>Hyperparameter Tuning</span>
                    <Badge variant="secondary" className="text-[9px] px-1 py-0 font-mono text-primary bg-primary/10">
                      Top K: {ragConfig.topK}
                    </Badge>
                  </Button>

                  <Button
                    size="md"
                    variant="ghost"
                    onClick={fetchDocuments}
                    className="h-9 px-2 text-xs text-muted-foreground"
                    title="Refresh document list"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardContent>

              {uploadStatus && (
                <div className="px-5 pb-4">
                  <div className="flex items-center gap-2 text-xs font-medium text-primary bg-primary/10 border border-primary/20 rounded-lg p-2.5 animate-pulse">
                    <Loader2 className="h-4 w-4 animate-spin shrink-0" />
                    <span>{uploadStatus}</span>
                  </div>
                </div>
              )}
            </Card>

            {/* Hyperparameter Tuning Controls */}
            {showTuning && (
              <Card className="border-primary/30 bg-card/90 shadow-md">
                <CardHeader className="p-4 pb-2 border-b border-border/50 flex flex-row items-center justify-between">
                  <CardTitle className="text-xs font-bold uppercase tracking-wider text-primary flex items-center gap-2">
                    <SlidersHorizontal className="h-4 w-4" />
                    <span>RAG Hyperparameters</span>
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setRagConfig(DEFAULT_RAG_CONFIG);
                      setActivePreset("balanced");
                    }}
                    className="h-6 px-2 text-[10px] text-muted-foreground hover:text-foreground gap-1"
                  >
                    <RotateCcw className="h-3 w-3" />
                    Reset
                  </Button>
                </CardHeader>
                <CardContent className="p-4 space-y-4">
                  {/* Preset Pills */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {PRESETS.map((p) => {
                      const Icon = p.icon;
                      const isSel = activePreset === p.id;
                      return (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => handlePresetSelect(p)}
                          className={`p-2.5 rounded-lg border text-left transition-all cursor-pointer ${
                            isSel
                              ? "border-primary bg-primary/15 font-semibold text-foreground"
                              : "border-border/60 bg-background/50 text-muted-foreground hover:border-primary/40"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-foreground flex items-center gap-1.5">
                              <Icon className="h-3.5 w-3.5 text-primary" />
                              {p.name}
                            </span>
                            <Badge variant={isSel ? "default" : "outline"} className="text-[8px] px-1 py-0">
                              {p.badge}
                            </Badge>
                          </div>
                          <span className="text-[10px] font-mono text-muted-foreground">
                            k={p.config.topK}, size={p.config.chunkSize}
                          </span>
                        </button>
                      );
                    })}
                  </div>

                  {/* Sliders */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
                    <div className="space-y-1 p-2.5 rounded-lg border border-border/60 bg-background/40">
                      <div className="flex justify-between text-xs font-medium">
                        <span>Top K (Evidence Chunks)</span>
                        <span className="font-mono text-primary font-bold">{ragConfig.topK}</span>
                      </div>
                      <input
                        type="range"
                        min={1}
                        max={25}
                        value={ragConfig.topK}
                        onChange={(e) => handleHyperparamChange("topK", Number(e.target.value))}
                        className="w-full accent-primary cursor-pointer"
                      />
                    </div>

                    <div className="space-y-1 p-2.5 rounded-lg border border-border/60 bg-background/40">
                      <div className="flex justify-between text-xs font-medium">
                        <span>Chunk Size</span>
                        <span className="font-mono text-primary font-bold">{ragConfig.chunkSize} chars</span>
                      </div>
                      <input
                        type="range"
                        min={100}
                        max={2000}
                        step={50}
                        value={ragConfig.chunkSize}
                        onChange={(e) => handleHyperparamChange("chunkSize", Number(e.target.value))}
                        className="w-full accent-primary cursor-pointer"
                      />
                    </div>

                    <div className="space-y-1 p-2.5 rounded-lg border border-border/60 bg-background/40">
                      <div className="flex justify-between text-xs font-medium">
                        <span>Chunk Overlap</span>
                        <span className="font-mono text-primary font-bold">{ragConfig.chunkOverlap} chars</span>
                      </div>
                      <input
                        type="range"
                        min={0}
                        max={Math.min(500, Math.floor(ragConfig.chunkSize * 0.5))}
                        step={10}
                        value={ragConfig.chunkOverlap}
                        onChange={(e) => handleHyperparamChange("chunkOverlap", Number(e.target.value))}
                        className="w-full accent-primary cursor-pointer"
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Split Layout: Files List (Left) + Interactive Q&A (Right) */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              {/* Left Column: Uploaded Documents */}
              <div className="lg:col-span-4">
                <Card className="border-border/80 bg-card/60 backdrop-blur-sm shadow-sm flex flex-col h-[600px]">
                  <CardHeader className="p-3 px-4 border-b border-border/60 shrink-0">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5 text-primary" />
                        <span>Uploaded Documents ({documents.length})</span>
                      </CardTitle>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={isUploading}
                        className="h-6 px-2 text-[10px] gap-1 cursor-pointer"
                      >
                        <Plus className="h-3 w-3" />
                        Add
                      </Button>
                    </div>
                  </CardHeader>

                  <CardContent className="p-3 flex-1 overflow-y-auto space-y-2">
                    {documents.length > 0 && (
                      <div className="p-2 rounded-lg bg-background/50 border border-border/50 flex items-center justify-between text-xs">
                        <button
                          onClick={() => {
                            if (searchEntireProject) {
                              setSearchEntireProject(false);
                              setSelectedDocIds(readyDocuments.map((d) => d.id));
                            } else {
                              setSearchEntireProject(true);
                              setSelectedDocIds([]);
                            }
                          }}
                          className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground font-medium cursor-pointer"
                        >
                          {searchEntireProject ? (
                            <CheckSquare className="h-3.5 w-3.5 text-primary" />
                          ) : (
                            <Square className="h-3.5 w-3.5" />
                          )}
                          <span>Search all documents</span>
                        </button>
                        <Badge variant="outline" className="text-[10px] font-mono">
                          {searchEntireProject ? documents.length : selectedDocIds.length} active
                        </Badge>
                      </div>
                    )}

                    {documents.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center p-6 text-center space-y-2.5">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20">
                          <Upload className="h-5 w-5" />
                        </div>
                        <p className="text-xs font-semibold text-foreground">No documents uploaded</p>
                        <p className="text-[11px] text-muted-foreground max-w-xs">
                          Upload PDFs, DOCX, CSV, Excel, or JSON files to start querying.
                        </p>
                        <Button
                          size="sm"
                          variant="default"
                          onClick={() => fileInputRef.current?.click()}
                          className="gap-1 text-xs"
                        >
                          <Upload className="h-3 w-3" />
                          Upload File
                        </Button>
                      </div>
                    ) : (
                      documents.map((doc) => {
                        const isSelected = selectedDocIds.includes(doc.id);
                        const isReady = doc.status === "ready";
                        const isProcessing = doc.status === "processing" || processingDocs[doc.id];
                        const isFailed = doc.status === "failed";

                        return (
                          <div
                            key={doc.id}
                            className={`p-2.5 rounded-xl border text-xs space-y-1.5 ${
                              isSelected && !searchEntireProject
                                ? "border-primary/60 bg-primary/10"
                                : "border-border/60 bg-background/60"
                            }`}
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex items-start gap-2 overflow-hidden">
                                {!searchEntireProject && (
                                  <button
                                    onClick={() => {
                                      setSearchEntireProject(false);
                                      setSelectedDocIds((prev) =>
                                        prev.includes(doc.id)
                                          ? prev.filter((id) => id !== doc.id)
                                          : [...prev, doc.id]
                                      );
                                    }}
                                    className="mt-0.5 text-muted-foreground hover:text-foreground cursor-pointer shrink-0"
                                  >
                                    {isSelected ? (
                                      <CheckSquare className="h-3.5 w-3.5 text-primary" />
                                    ) : (
                                      <Square className="h-3.5 w-3.5" />
                                    )}
                                  </button>
                                )}
                                <div className="overflow-hidden">
                                  <p className="font-semibold text-foreground truncate" title={doc.original_filename}>
                                    {doc.original_filename}
                                  </p>
                                  <span className="text-[10px] text-muted-foreground font-mono">
                                    {(doc.file_size / 1024).toFixed(1)} KB • {doc.file_extension.replace(".", "").toUpperCase()}
                                  </span>
                                </div>
                              </div>

                              <button
                                onClick={() => handleDeleteDoc(doc.id)}
                                className="text-muted-foreground hover:text-destructive p-1 rounded cursor-pointer"
                                title="Delete file"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>

                            <div className="flex items-center justify-between text-[10px] pt-1 border-t border-border/40">
                              {isReady && (
                                <Badge variant="outline" className="text-emerald-400 border-emerald-500/30 gap-1 bg-emerald-500/10">
                                  <CheckCircle2 className="h-3 w-3" /> Ready
                                </Badge>
                              )}
                              {isProcessing && (
                                <Badge variant="outline" className="text-amber-400 border-amber-500/30 gap-1 bg-amber-500/10">
                                  <Loader2 className="h-3 w-3 animate-spin" /> Ingesting...
                                </Badge>
                              )}
                              {isFailed && <Badge variant="destructive">Failed</Badge>}

                              {!isReady && !isProcessing && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => handleProcessDoc(doc.id)}
                                  className="h-5 px-1.5 text-[10px] text-primary hover:underline cursor-pointer"
                                >
                                  Re-Index
                                </Button>
                              )}
                            </div>
                          </div>
                        );
                      })
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Right Column: Q&A Chat */}
              <div className="lg:col-span-8 flex flex-col h-[600px]">
                <Card className="border-border/80 bg-card/60 backdrop-blur-sm shadow-sm flex flex-col h-full">
                  <CardHeader className="p-3 px-4 border-b border-border/60 shrink-0">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Bot className="h-4 w-4 text-primary" />
                        <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                          Grounded Research Q&amp;A
                        </CardTitle>
                      </div>
                      <Badge variant="secondary" className="text-[10px] font-mono text-primary bg-primary/10">
                        Top K = {ragConfig.topK}
                      </Badge>
                    </div>
                  </CardHeader>

                  <CardContent className="p-4 flex-1 overflow-y-auto space-y-4 text-xs">
                    {messages.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center space-y-2 p-6 text-muted-foreground">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20">
                          <Bot className="h-5 w-5" />
                        </div>
                        <p className="text-sm font-bold text-foreground">Ask anything from your documents</p>
                        <p className="text-xs text-muted-foreground max-w-sm">
                          Responses are grounded in retrieved evidence with clickable source citations.
                        </p>
                      </div>
                    ) : (
                      messages.map((msg, idx) => (
                        <div
                          key={idx}
                          className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                        >
                          {msg.role === "assistant" && (
                            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 border border-primary/20 text-primary">
                              <Bot className="h-4 w-4" />
                            </div>
                          )}

                          <div
                            className={`max-w-[85%] rounded-2xl p-3.5 space-y-2 ${
                              msg.role === "user"
                                ? "bg-primary text-primary-foreground font-medium shadow-sm"
                                : "bg-background/80 border border-border/70 text-foreground shadow-sm"
                            }`}
                          >
                            {msg.statusMessage && (
                              <div className="flex items-center gap-1.5 text-primary text-xs animate-pulse">
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                <span>{msg.statusMessage}</span>
                              </div>
                            )}

                            {msg.content && (
                              <div className="prose prose-sm dark:prose-invert max-w-none text-xs leading-relaxed break-words">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                              </div>
                            )}

                            {msg.citations && msg.citations.length > 0 && (
                              <div className="pt-2 border-t border-border/40 space-y-1">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                                  Citations:
                                </span>
                                <div className="flex flex-wrap gap-1">
                                  {msg.citations.map((cite, cIdx) => (
                                    <button
                                      key={cIdx}
                                      onClick={() => setSelectedCitation(cite)}
                                      className="px-2 py-0.5 rounded text-[10px] font-mono bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 cursor-pointer"
                                    >
                                      [{cIdx + 1}] {cite.filename}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                    <div ref={messagesEndRef} />
                  </CardContent>

                  {/* Input Form */}
                  <div className="p-3 border-t border-border/60 bg-background/50">
                    <form onSubmit={handleSubmitQuery} className="flex gap-2">
                      <input
                        type="text"
                        value={queryInput}
                        onChange={(e) => setQueryInput(e.target.value)}
                        placeholder={
                          documents.length === 0
                            ? "Upload a document on the left to start asking questions..."
                            : "Ask a question about your documents..."
                        }
                        disabled={isGenerating || documents.length === 0}
                        className="flex-1 bg-background border border-border rounded-xl px-3.5 py-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60"
                      />
                      <Button
                        type="submit"
                        disabled={isGenerating || !queryInput.trim() || documents.length === 0}
                        className="h-10 px-4 gap-1 text-xs font-semibold cursor-pointer"
                      >
                        {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                        <span>Ask</span>
                      </Button>
                    </form>
                  </div>
                </Card>
              </div>
            </div>
          </div>
        )}

        {/* SECTION 2: DOCUMENT COMPARISON */}
        {activeSection === "compare" && (
          <div className="space-y-4">
            {isLoadingProject ? (
              <div className="h-64 rounded-2xl border border-border/60 bg-card/40 flex items-center justify-center animate-pulse">
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
              </div>
            ) : activeProject ? (
              <DocumentComparisonView
                projectId={activeProject.id}
                documents={documents}
                onRefreshDocuments={fetchDocuments}
                onProcessDocument={handleProcessDoc}
              />
            ) : null}
          </div>
        )}

        {/* Citation Inspection Modal */}
        {selectedCitation && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
            <div className="relative w-full max-w-lg rounded-2xl border border-border bg-card p-5 shadow-2xl space-y-3">
              <div className="flex items-center justify-between border-b border-border/50 pb-2">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-primary" />
                  <span className="text-xs font-bold text-foreground truncate">{selectedCitation.filename}</span>
                </div>
                <Button size="sm" variant="ghost" onClick={() => setSelectedCitation(null)} className="h-6 w-6 p-0">
                  ✕
                </Button>
              </div>
              <div className="text-xs text-muted-foreground bg-background/80 p-3 rounded-xl border border-border/60 font-mono max-h-60 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                {selectedCitation.preview}
              </div>
              <div className="flex justify-end pt-1">
                <Button size="sm" variant="outline" onClick={() => setSelectedCitation(null)} className="text-xs h-7">
                  Close
                </Button>
              </div>
            </div>
          </div>
        )}
      </Container>
    </AppShell>
  );
}
