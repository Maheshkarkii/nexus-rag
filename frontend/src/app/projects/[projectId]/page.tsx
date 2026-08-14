"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  FolderKanban,
  ArrowLeft,
  Edit3,
  Trash2,
  FileText,
  GitCompare,
  Bot,
  AlertCircle,
  Plus,
  Upload,
  RefreshCw,
  Send,
  Loader2,
  CheckSquare,
  Square,
  CheckCircle2,
  Info,
  FileDown,
  FileCode,
  FileCheck,
  Sparkles,
  X
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { ProjectResponse, DocumentResponse } from "@/lib/api/types";
import { Container } from "@/components/ui/container";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { EditProjectModal } from "@/components/projects/edit-project-modal";
import { DeleteProjectModal } from "@/components/projects/delete-project-modal";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface CitationSource {
  source_id: string;
  filename: string;
  preview: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: CitationSource[];
  sources?: unknown[];
  statusMessage?: string;
  latencyMs?: number;
}

interface ConversationItem {
  id: string;
  title: string;
}

interface ReportItem {
  id: string;
  title: string;
  report_type: string;
  status: string;
  version: number;
  content_json?: {
    sections?: Array<{ title: string; content: string }>;
    sources?: Array<{ source_id: string; filename: string; location_info: string }>;
  };
  created_at: string;
}

export default function ProjectWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.projectId as string;

  // Project workspace states
  const [project, setProject] = React.useState<ProjectResponse | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  // Documents states
  const [documents, setDocuments] = React.useState<DocumentResponse[]>([]);
  const [isUploading, setIsUploading] = React.useState(false);
  const [uploadStatus, setUploadStatus] = React.useState<string | null>(null);
  const [processingDocs, setProcessingDocs] = React.useState<Record<string, string>>({});

  // Document Selection Scope
  const [selectedDocIds, setSelectedDocIds] = React.useState<string[]>([]);
  const [searchEntireProject, setSearchEntireProject] = React.useState(true);

  // Conversation/Chat states
  const [conversations, setConversations] = React.useState<ConversationItem[]>([]);
  const [activeConvId, setActiveConvId] = React.useState<string | null>(null);
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [queryInput, setQueryInput] = React.useState("");
  const [isGenerating, setIsGenerating] = React.useState(false);

  // Stage 21 Reports states
  const [reports, setReports] = React.useState<ReportItem[]>([]);
  const [selectedReport, setSelectedReport] = React.useState<ReportItem | null>(null);
  const [isReportModalOpen, setIsReportModalOpen] = React.useState(false);
  const [isGeneratingReport, setIsGeneratingReport] = React.useState(false);
  const [reportTypeSelect, setReportTypeSelect] = React.useState("research_summary");
  const [reportProgressMsg, setReportProgressMsg] = React.useState<string | null>(null);

  // Modals
  const [isEditOpen, setIsEditOpen] = React.useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = React.useState(false);

  // Load project details
  const fetchProject = React.useCallback(async () => {
    if (!projectId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.getProject(projectId);
      setProject(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unable to retrieve research workspace.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  // Load documents
  const fetchDocuments = React.useCallback(async () => {
    if (!projectId) return;
    try {
      const docs = await apiClient.listDocuments(projectId);
      setDocuments(docs);
    } catch (err) {
      console.error("Failed to load documents", err);
    }
  }, [projectId]);

  // Load conversations
  const fetchConversations = React.useCallback(async () => {
    if (!projectId) return;
    try {
      const convs = await apiClient.listConversations(projectId);
      const mapped = convs.map((c) => {
        const item = c as Record<string, unknown>;
        return { id: String(item.id), title: String(item.title) };
      });
      setConversations(mapped);
      if (mapped.length > 0 && !activeConvId) {
        setActiveConvId(mapped[0].id);
      }
    } catch (err) {
      console.error("Failed to load conversations", err);
    }
  }, [projectId, activeConvId]);

  // Load reports
  const fetchReports = React.useCallback(async () => {
    if (!projectId) return;
    try {
      const rpts = await apiClient.listReports(projectId);
      setReports(rpts as ReportItem[]);
    } catch (err) {
      console.error("Failed to load reports", err);
    }
  }, [projectId]);

  // Load messages for active conversation
  const fetchMessages = React.useCallback(async () => {
    if (!activeConvId) {
      setMessages([]);
      return;
    }
    try {
      const dbMsgs = await apiClient.getConversationMessages(activeConvId);
      const mapped: Message[] = dbMsgs.map((m) => {
        const item = m as Record<string, unknown>;
        const metadata = (item.metadata_json || {}) as Record<string, unknown>;
        return {
          role: item.role as "user" | "assistant",
          content: String(item.content),
          citations: (metadata.citations || []) as CitationSource[],
        };
      });
      setMessages(mapped);
    } catch (err) {
      console.error("Failed to load messages", err);
    }
  }, [activeConvId]);

  React.useEffect(() => {
    fetchProject();
    fetchDocuments();
    fetchConversations();
    fetchReports();
  }, [fetchProject, fetchDocuments, fetchConversations, fetchReports]);

  React.useEffect(() => {
    fetchMessages();
  }, [activeConvId, fetchMessages]);

  const handleUpdated = (updated: ProjectResponse) => {
    setProject(updated);
  };

  const handleDeleted = () => {
    router.push("/projects");
  };

  // Upload file handler
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !projectId) return;

    setIsUploading(true);
    setUploadStatus("Uploading file...");
    try {
      const uploadedDoc = await apiClient.uploadDocument(projectId, file);
      setUploadStatus("File uploaded. Starting processing...");
      await handleProcessDoc(uploadedDoc.id);
      await fetchDocuments();
    } catch (err: unknown) {
      setUploadStatus(null);
      const msg = err instanceof Error ? err.message : "Failed to upload file.";
      alert(msg);
    } finally {
      setIsUploading(false);
    }
  };

  // Process, chunk, embed, index sequential execution pipeline
  const handleProcessDoc = async (docId: string) => {
    if (!projectId) return;
    setProcessingDocs((prev) => ({ ...prev, [docId]: "Extracting text..." }));
    try {
      await apiClient.processDocument(projectId, docId);
      setProcessingDocs((prev) => ({ ...prev, [docId]: "Partitioning chunks..." }));
      await apiClient.chunkDocument(projectId, docId);
      setProcessingDocs((prev) => ({ ...prev, [docId]: "Generating vectors..." }));
      await apiClient.embedDocument(projectId, docId);
      setProcessingDocs((prev) => ({ ...prev, [docId]: "Indexing to Qdrant..." }));
      await apiClient.indexDocument(projectId, docId);
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
      alert(msg);
      await fetchDocuments();
    }
  };

  // Delete document
  const handleDeleteDoc = async (docId: string) => {
    if (!projectId || !confirm("Are you sure you want to delete this document?")) return;
    try {
      await apiClient.deleteDocument(projectId, docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      setSelectedDocIds((prev) => prev.filter((id) => id !== docId));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete document.";
      alert(msg);
    }
  };

  // Toggle document selection
  const handleToggleDoc = (docId: string) => {
    setSearchEntireProject(false);
    setSelectedDocIds((prev) => {
      if (prev.includes(docId)) {
        const next = prev.filter((id) => id !== docId);
        if (next.length === 0) setSearchEntireProject(true);
        return next;
      } else {
        return [...prev, docId];
      }
    });
  };

  // Select all / Search entire project toggle
  const handleToggleSearchAll = () => {
    if (searchEntireProject) {
      setSearchEntireProject(false);
      const readyIds = documents.filter((d) => d.status === "ready").map((d) => d.id);
      setSelectedDocIds(readyIds);
    } else {
      setSearchEntireProject(true);
      setSelectedDocIds([]);
    }
  };

  // Create new chat session
  const handleCreateSession = async () => {
    if (!projectId) return;
    try {
      const title = `Session ${conversations.length + 1}`;
      const newSessionObj = await apiClient.createConversation(projectId, title) as { id: string; title: string };
      const newSession: ConversationItem = { id: String(newSessionObj.id), title: String(newSessionObj.title) };
      setConversations((prev) => [newSession, ...prev]);
      setActiveConvId(newSession.id);
    } catch {
      alert("Failed to create session.");
    }
  };

  // Submit Query to ask RAG using SSE streaming (Stage 17 + 20)
  const handleSubmitQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryInput.trim() || !projectId || isGenerating) return;

    let convId = activeConvId;
    if (!convId) {
      try {
        const title = `Session ${conversations.length + 1}`;
        const newSessionObj = await apiClient.createConversation(projectId, title) as { id: string; title: string };
        const newSession: ConversationItem = { id: String(newSessionObj.id), title: String(newSessionObj.title) };
        setConversations([newSession]);
        setActiveConvId(newSession.id);
        convId = newSession.id;
      } catch {
        alert("Failed to initialize conversation session.");
        return;
      }
    }

    const userMsg: Message = { role: "user", content: queryInput };
    setMessages((prev) => [...prev, userMsg]);
    setQueryInput("");
    setIsGenerating(true);

    const assistantPlaceholderIdx = messages.length + 1;
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", sources: [], citations: [], statusMessage: "Initializing..." }
    ]);

    const apiBaseUrl = apiClient["baseUrl"];
    const askStreamUrl = `${apiBaseUrl}/api/v1/projects/${projectId}/ask/stream`;

    try {
      const response = await fetch(askStreamUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: userMsg.content,
          top_k: 8,
          document_ids: searchEntireProject ? null : selectedDocIds,
          conversation_id: convId,
        }),
      });

      if (!response.ok) throw new Error("Ask query stream request failed.");

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("Body reader missing.");

      let partialData = "";
      let answerText = "";
      let activeSources: unknown[] = [];
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
              if (eventType === "status" || eventType === "research_started" || eventType === "research_step_started") {
                const msgText = dataObj.message || `Executing ${dataObj.question || "research step"}...`;
                setMessages((prev) => {
                  const copy = [...prev];
                  if (copy[assistantPlaceholderIdx]) {
                    copy[assistantPlaceholderIdx].statusMessage = msgText;
                  }
                  return copy;
                });
              } else if (eventType === "sources") {
                activeSources = (dataObj.sources || []) as unknown[];
                setMessages((prev) => {
                  const copy = [...prev];
                  if (copy[assistantPlaceholderIdx]) {
                    copy[assistantPlaceholderIdx].sources = activeSources;
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
              console.error("Failed to parse event packet", err);
            }
          }
        }
      }
    } catch (err: unknown) {
      console.error(err);
      setMessages((prev) => {
        const copy = [...prev];
        if (copy[assistantPlaceholderIdx]) {
          copy[assistantPlaceholderIdx].content = "Failed to retrieve grounded answer.";
          copy[assistantPlaceholderIdx].statusMessage = undefined;
        }
        return copy;
      });
    } finally {
      setIsGenerating(false);
    }
  };

  // Generate Report Handler (Stage 21)
  const handleGenerateReport = async () => {
    if (!projectId || isGeneratingReport) return;
    setIsGeneratingReport(true);
    setReportProgressMsg("Gathering research evidence...");

    try {
      const createdReport = await apiClient.generateReport(projectId, {
        report_type: reportTypeSelect,
        conversation_id: activeConvId,
        document_ids: searchEntireProject ? null : selectedDocIds,
      }) as ReportItem;
      await fetchReports();
      setSelectedReport(createdReport);
      setReportProgressMsg(null);
    } catch (err: unknown) {
      console.error(err);
      alert("Failed to generate report.");
      setReportProgressMsg(null);
    } finally {
      setIsGeneratingReport(false);
    }
  };

  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  if (isLoading) {
    return (
      <Container className="py-6 space-y-6">
        <div className="h-6 w-36 bg-muted/60 rounded animate-pulse" />
        <div className="h-28 rounded-xl border border-border/60 bg-card/40 p-6 animate-pulse" />
      </Container>
    );
  }

  if (error || !project) {
    return (
      <Container className="py-12 max-w-lg mx-auto text-center space-y-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-destructive/10 text-destructive mx-auto border border-destructive/20">
          <AlertCircle className="h-6 w-6" />
        </div>
        <h2 className="text-lg font-bold text-foreground">Project Not Found</h2>
        <div className="flex items-center justify-center gap-3 pt-2">
          <Link href="/projects">
            <Button variant="outline" size="sm" className="gap-1.5">
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Back to Projects</span>
            </Button>
          </Link>
        </div>
      </Container>
    );
  }

  return (
    <Container size="xl" className="py-4 space-y-4 max-w-[1600px] h-[calc(100vh-2rem)] flex flex-col">
      {/* Top Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <Link href="/projects">
            <Button variant="outline" size="icon" className="h-8 w-8">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
              <FolderKanban className="h-4.5 w-4.5 text-primary" />
              <span>{project.name}</span>
            </h1>
            <p className="text-[11px] text-muted-foreground truncate max-w-sm sm:max-w-md">
              {project.description || "Active research workspace."}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsReportModalOpen(true)}
            className="gap-1.5 h-8 text-xs bg-primary/10 border-primary/30 text-primary hover:bg-primary/20"
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>Reports & Exports ({reports.length})</span>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsEditOpen(true)}
            className="gap-1.5 h-8 text-xs"
          >
            <Edit3 className="h-3.5 w-3.5" />
            <span>Edit</span>
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setIsDeleteOpen(true)}
            className="gap-1.5 h-8 text-xs"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span>Delete</span>
          </Button>
        </div>
      </div>

      {/* Main Split Layout */}
      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-12 gap-4">
        
        {/* Left Side: Document Manager & Sessions (4 columns) */}
        <div className="lg:col-span-4 flex flex-col gap-4 min-h-0">
          
          {/* Document Management Card */}
          <Card className="flex-1 flex flex-col min-h-0 border-border/80 bg-card/60 backdrop-blur-sm shadow-sm">
            <CardHeader className="p-4 pb-2 border-b border-border/60 shrink-0">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                  <FileText className="h-4 w-4 text-primary" />
                  <span>Project Knowledge Base</span>
                </CardTitle>
                <div className="relative">
                  <input
                    type="file"
                    ref={fileInputRef}
                    className="hidden"
                    onChange={handleFileUpload}
                    accept=".pdf,.docx,.txt,.csv,.xlsx,.xls,.json"
                    disabled={isUploading}
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 px-2.5 text-[10px] gap-1 cursor-pointer"
                    disabled={isUploading}
                    onClick={handleUploadClick}
                  >
                    {isUploading ? (
                      <Loader2 className="h-3 w-3 animate-spin text-primary" />
                    ) : (
                      <Upload className="h-3 w-3" />
                    )}
                    Upload
                  </Button>
                </div>
              </div>
              {uploadStatus && (
                <p className="text-[10px] text-primary font-mono mt-1 animate-pulse">
                  {uploadStatus}
                </p>
              )}
            </CardHeader>

            <CardContent className="p-3 overflow-y-auto flex-1 space-y-2">
              {documents.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground space-y-2">
                  <Upload className="h-8 w-8 mx-auto text-muted-foreground/45" />
                  <p className="text-xs">No documents uploaded yet.</p>
                  <p className="text-[10px]">Supports PDF, DOCX, CSV, Excel, and JSON</p>
                </div>
              ) : (
                documents.map((doc) => {
                  const isProcessing = !!processingDocs[doc.id];
                  const procState = processingDocs[doc.id];
                  
                  return (
                    <div
                      key={doc.id}
                      className={`flex items-start justify-between p-2.5 rounded-lg border text-xs transition-colors hover:bg-muted/40 ${
                        selectedDocIds.includes(doc.id)
                          ? "border-primary/40 bg-primary/5"
                          : "border-border/60 bg-background/50"
                      }`}
                    >
                      <div className="flex items-start gap-2.5 min-w-0 flex-1">
                        <button
                          onClick={() => doc.status === "ready" && handleToggleDoc(doc.id)}
                          disabled={doc.status !== "ready"}
                          className="mt-0.5 shrink-0"
                        >
                          {doc.status !== "ready" ? (
                            <Square className="h-4 w-4 text-muted-foreground/40 cursor-not-allowed" />
                          ) : selectedDocIds.includes(doc.id) ? (
                            <CheckSquare className="h-4 w-4 text-primary" />
                          ) : (
                            <Square className="h-4 w-4 text-muted-foreground" />
                          )}
                        </button>
                        
                        <div className="min-w-0 flex-1">
                          <p className="font-semibold text-foreground truncate" title={doc.original_filename}>
                            {doc.original_filename}
                          </p>
                          <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground font-mono mt-0.5">
                            <span>{(doc.file_size / 1024).toFixed(1)} KB</span>
                            <span>•</span>
                            <span className="uppercase">{doc.file_extension.replace(".", "")}</span>
                            <span>•</span>
                            {isProcessing ? (
                              <span className="text-primary font-bold animate-pulse">{procState}</span>
                            ) : doc.status === "ready" ? (
                              <span className="text-emerald-400 font-bold flex items-center gap-0.5">
                                <CheckCircle2 className="h-3 w-3" /> Ready
                              </span>
                            ) : doc.status === "failed" ? (
                              <span className="text-destructive font-bold">Failed</span>
                            ) : (
                              <span className="text-amber-400 font-bold">Raw Metadata</span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-1 shrink-0 ml-2">
                        {doc.status !== "ready" && !isProcessing && (
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-7 w-7 text-primary hover:bg-primary/10"
                            onClick={() => handleProcessDoc(doc.id)}
                            title="Run pipeline (Process -> Chunk -> Embed -> Index)"
                          >
                            <RefreshCw className="h-3.5 w-3.5" />
                          </Button>
                        )}
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 text-destructive hover:bg-destructive/10"
                          onClick={() => handleDeleteDoc(doc.id)}
                          title="Remove document"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>

          {/* Research Scope & Sessions Card */}
          <Card className="h-44 flex flex-col min-h-0 border-border/80 bg-card/60 backdrop-blur-sm shadow-sm shrink-0">
            <CardHeader className="p-4 pb-2 border-b border-border/60 shrink-0">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Research Scope
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-[10px] gap-1 px-2"
                  onClick={handleToggleSearchAll}
                >
                  {searchEntireProject ? "Restrict Retrieval" : "Search All Files"}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-3 text-xs space-y-2 flex-1 overflow-y-auto">
              <div className="p-2 bg-background/50 rounded-lg border border-border/50 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Info className="h-3.5 w-3.5 text-primary" />
                  <span className="font-medium text-[11px]">
                    {searchEntireProject
                      ? "Project-wide research active"
                      : `${selectedDocIds.length} document(s) targeted`}
                  </span>
                </div>
                <Badge variant={searchEntireProject ? "default" : "secondary"} className="text-[9px]">
                  {searchEntireProject ? "All Sources" : "Filtered"}
                </Badge>
              </div>

              {/* Session controller */}
              <div className="flex items-center gap-2 pt-1.5">
                <div className="flex-1">
                  <select
                    className="w-full h-8 bg-background border border-border/60 rounded-md px-2 text-xs font-mono"
                    value={activeConvId || ""}
                    onChange={(e) => setActiveConvId(e.target.value || null)}
                  >
                    <option value="" disabled>Select Research Session</option>
                    {conversations.map((c) => (
                      <option key={c.id} value={c.id}>{c.title}</option>
                    ))}
                  </select>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleCreateSession}
                  className="h-8 gap-1 text-xs shrink-0"
                >
                  <Plus className="h-3.5 w-3.5" />
                  New
                </Button>
              </div>
            </CardContent>
          </Card>

        </div>

        {/* Right Side: Chat & Comparison Board (8 columns) */}
        <div className="lg:col-span-8 flex flex-col min-h-0">
          <Card className="flex-1 flex flex-col min-h-0 border-border/80 bg-card/60 backdrop-blur-sm shadow-sm relative">
            {/* Header displaying targeted scope */}
            <div className="p-4 border-b border-border/60 shrink-0 bg-background/40 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bot className="h-5 w-5 text-primary" />
                <div>
                  <h2 className="text-xs font-bold text-foreground">Grounded Research Assistant</h2>
                  <p className="text-[10px] text-muted-foreground">
                    Ask questions, decompose complex tasks, and generate grounded research reports.
                  </p>
                </div>
              </div>
              <Badge variant="outline" className="text-[10px] font-mono gap-1">
                <GitCompare className="h-3 w-3" />
                <span>Stage 20 Planning & Stage 21 Reports</span>
              </Badge>
            </div>

            {/* Chat Messages Log */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center space-y-4 max-w-md mx-auto py-12">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 border border-primary/25 text-primary">
                    <Bot className="h-6 w-6" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="text-sm font-semibold text-foreground">Query Workspace Context</h3>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Select document sources on the left side, then ask complex research questions like:
                    </p>
                  </div>
                  <div className="grid grid-cols-1 gap-2 w-full pt-2">
                    {[
                      "Compare the methodologies used in the papers, identify their datasets, and summarize key results",
                      "What datasets did the papers use, what models did they evaluate, and how do their reported accuracies compare?",
                      "Analyze dataset row counts and schema columns across uploaded files",
                    ].map((sample) => (
                      <button
                        key={sample}
                        onClick={() => setQueryInput(sample)}
                        className="text-left text-xs p-2.5 rounded-lg border border-border/50 bg-background/50 hover:bg-muted/50 hover:border-border transition-colors font-medium text-foreground"
                      >
                        {sample}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex gap-3 max-w-4xl ${
                      msg.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
                    }`}
                  >
                    <div
                      className={`flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-lg border text-xs font-bold ${
                        msg.role === "user"
                          ? "bg-primary text-primary-foreground border-primary/20"
                          : "bg-muted text-muted-foreground border-border"
                      }`}
                    >
                      {msg.role === "user" ? "U" : "AI"}
                    </div>

                    <div className="space-y-1.5 min-w-0">
                      <div
                        className={`rounded-xl p-3 px-4 text-xs leading-relaxed shadow-sm border ${
                          msg.role === "user"
                            ? "bg-primary/10 border-primary/20 text-foreground"
                            : "bg-background/90 border-border/80 text-foreground"
                        }`}
                      >
                        {msg.role === "assistant" && msg.statusMessage && (
                          <div className="flex items-center gap-2 mb-2 text-primary font-medium text-[11px]">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            <span>{msg.statusMessage}</span>
                          </div>
                        )}
                        
                        <div className="prose prose-sm dark:prose-invert max-w-none break-words">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.content}
                          </ReactMarkdown>
                        </div>
                      </div>

                      {/* Display Citations tags and Latency */}
                      {msg.role === "assistant" && (
                        <div className="flex flex-wrap items-center gap-2 px-1 text-[10px] text-muted-foreground font-mono">
                          {msg.latencyMs && <span>Latency: {msg.latencyMs}ms</span>}
                          {msg.citations && msg.citations.length > 0 && (
                            <div className="flex flex-wrap gap-1.5 items-center">
                              <span>• Sources:</span>
                              {msg.citations.map((c) => (
                                <span
                                  key={c.source_id}
                                  className="px-1.5 py-0.5 rounded bg-muted border border-border text-[9px] font-bold text-foreground cursor-help"
                                  title={`${c.filename} - ${c.preview}`}
                                >
                                  {c.source_id}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Input Form area */}
            <form onSubmit={handleSubmitQuery} className="p-4 border-t border-border/60 shrink-0 bg-background/40">
              <div className="relative flex items-center">
                <input
                  type="text"
                  placeholder={
                    isGenerating
                      ? "Waiting for completion..."
                      : searchEntireProject
                      ? "Search across all files..."
                      : `Compare selected ${selectedDocIds.length} files...`
                  }
                  className="w-full bg-background border border-border/80 rounded-xl pl-4 pr-12 py-3 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary disabled:opacity-60"
                  value={queryInput}
                  onChange={(e) => setQueryInput(e.target.value)}
                  disabled={isGenerating}
                />
                <Button
                  type="submit"
                  size="icon"
                  className="absolute right-2 h-8 w-8 rounded-lg bg-primary hover:bg-primary/95 text-primary-foreground"
                  disabled={isGenerating || !queryInput.trim()}
                >
                  {isGenerating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </form>
          </Card>
        </div>

      </div>

      {/* Reports & Exports Modal Drawer (Stage 21) */}
      {isReportModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-card border border-border/80 rounded-xl shadow-2xl max-w-4xl w-full h-[85vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="p-4 border-b border-border flex items-center justify-between bg-muted/30 shrink-0">
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                <h2 className="text-sm font-bold text-foreground">Research Reports & Export Center</h2>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => setIsReportModalOpen(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Modal Split Content */}
            <div className="flex-1 min-h-0 grid grid-cols-12 overflow-hidden">
              {/* Left Column: Report Generation & History (4 cols) */}
              <div className="col-span-4 border-r border-border p-4 flex flex-col gap-4 overflow-y-auto bg-background/50">
                <div className="space-y-3 p-3 bg-card rounded-lg border border-border/80">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Plus className="h-3.5 w-3.5 text-primary" />
                    <span>Generate New Report</span>
                  </h3>
                  
                  <div className="space-y-1">
                    <label className="text-[10px] text-muted-foreground font-semibold">Report Structure Type</label>
                    <select
                      className="w-full h-8 bg-background border border-border/80 rounded px-2 text-xs font-mono"
                      value={reportTypeSelect}
                      onChange={(e) => setReportTypeSelect(e.target.value)}
                      disabled={isGeneratingReport}
                    >
                      <option value="research_summary">Research Summary</option>
                      <option value="comparative_report">Comparative Analysis</option>
                      <option value="literature_review">Literature Review</option>
                      <option value="document_analysis">Document Analysis</option>
                      <option value="data_analysis_summary">Data Analysis Summary</option>
                    </select>
                  </div>

                  <Button
                    onClick={handleGenerateReport}
                    disabled={isGeneratingReport}
                    className="w-full h-8 text-xs gap-1.5"
                  >
                    {isGeneratingReport ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Generating...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-3.5 w-3.5" />
                        <span>Generate Report</span>
                      </>
                    )}
                  </Button>

                  {reportProgressMsg && (
                    <p className="text-[10px] text-primary font-mono text-center animate-pulse">
                      {reportProgressMsg}
                    </p>
                  )}
                </div>

                {/* Report History */}
                <div className="space-y-2 flex-1">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    Generated Reports History ({reports.length})
                  </h3>

                  {reports.length === 0 ? (
                    <div className="text-center py-6 text-muted-foreground text-xs">
                      No reports generated yet.
                    </div>
                  ) : (
                    reports.map((r) => (
                      <div
                        key={r.id}
                        onClick={() => setSelectedReport(r)}
                        className={`p-3 rounded-lg border text-xs cursor-pointer transition-colors ${
                          selectedReport?.id === r.id
                            ? "border-primary bg-primary/10"
                            : "border-border/60 hover:bg-muted/40"
                        }`}
                      >
                        <p className="font-bold text-foreground truncate">{r.title}</p>
                        <div className="flex items-center justify-between text-[10px] text-muted-foreground font-mono mt-1">
                          <span className="capitalize">{r.report_type.replace("_", " ")}</span>
                          <Badge variant="outline" className="text-[9px]">v{r.version}</Badge>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Right Column: Report Preview & Export Buttons (8 cols) */}
              <div className="col-span-8 p-4 flex flex-col h-full min-h-0 bg-background">
                {selectedReport && selectedReport.content_json ? (
                  <div className="flex flex-col h-full min-h-0 space-y-3">
                    {/* Top Action Bar */}
                    <div className="flex items-center justify-between border-b border-border pb-3 shrink-0">
                      <div>
                        <h3 className="text-sm font-bold text-foreground">{selectedReport.title}</h3>
                        <p className="text-[11px] text-muted-foreground font-mono">
                          Version {selectedReport.version} • Created: {new Date(selectedReport.created_at).toLocaleDateString()}
                        </p>
                      </div>

                      {/* Export buttons */}
                      <div className="flex items-center gap-2">
                        <a
                          href={apiClient.getExportUrl(projectId, selectedReport.id, "markdown")}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <Button variant="outline" size="sm" className="h-7 text-[10px] gap-1">
                            <FileCode className="h-3 w-3" />
                            Markdown
                          </Button>
                        </a>
                        <a
                          href={apiClient.getExportUrl(projectId, selectedReport.id, "pdf")}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <Button variant="outline" size="sm" className="h-7 text-[10px] gap-1">
                            <FileDown className="h-3 w-3 text-red-400" />
                            PDF
                          </Button>
                        </a>
                        <a
                          href={apiClient.getExportUrl(projectId, selectedReport.id, "docx")}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <Button variant="outline" size="sm" className="h-7 text-[10px] gap-1">
                            <FileCheck className="h-3 w-3 text-blue-400" />
                            Word (DOCX)
                          </Button>
                        </a>
                      </div>
                    </div>

                    {/* Report Structured Section Preview */}
                    <div className="flex-1 overflow-y-auto pr-2 space-y-4 text-xs leading-relaxed">
                      {selectedReport.content_json.sections?.map((sec, idx) => (
                        <div key={idx} className="space-y-1.5 p-3 rounded-lg border border-border/50 bg-card/40">
                          <h4 className="font-bold text-sm text-foreground">{sec.title}</h4>
                          <div className="prose prose-sm dark:prose-invert max-w-none text-muted-foreground">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {sec.content}
                            </ReactMarkdown>
                          </div>
                        </div>
                      ))}

                      {selectedReport.content_json.sources && selectedReport.content_json.sources.length > 0 && (
                        <div className="p-3 rounded-lg border border-border/50 bg-muted/20 space-y-2">
                          <h4 className="font-bold text-xs uppercase tracking-wider text-foreground">Sources & Traceability</h4>
                          <ul className="space-y-1 text-[11px] font-mono">
                            {selectedReport.content_json.sources.map((src, idx) => (
                              <li key={idx} className="flex items-center gap-2">
                                <Badge variant="outline" className="text-[9px] font-bold">{src.source_id}</Badge>
                                <span className="text-foreground font-semibold">{src.filename}</span>
                                <span className="text-muted-foreground">({src.location_info})</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground space-y-2">
                    <FileText className="h-10 w-10 text-muted-foreground/40" />
                    <p className="text-xs">Select a report on the left to preview or export.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Workspace CRUD Modals */}
      <EditProjectModal
        project={project}
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
        onSuccess={handleUpdated}
      />

      <DeleteProjectModal
        project={project}
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
        onSuccess={handleDeleted}
      />
    </Container>
  );
}
