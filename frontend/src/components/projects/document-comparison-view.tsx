"use client";

import * as React from "react";
import {
  GitCompare,
  Upload,
  Plus,
  Trash2,
  Sparkles,
  FileText,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Copy,
  Check,
  SplitSquareVertical,
} from "lucide-react";
import { DocumentResponse } from "@/lib/api/types";
import { apiClient } from "@/lib/api";
import { getApiUrl } from "@/lib/config";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface DocumentComparisonViewProps {
  projectId: string;
  documents: DocumentResponse[];
  onRefreshDocuments: () => Promise<void>;
  onProcessDocument: (docId: string) => Promise<void>;
}

interface NumberedSlot {
  slotNumber: number;
  file: File | null;
  uploadedDocId: string | null;
  document: DocumentResponse | null;
  status: "empty" | "selected" | "uploading" | "processing" | "ready" | "failed";
  error?: string;
}

const COMPARISON_PRESETS = [
  {
    title: "Methodology & Architecture",
    description: "Compare models, algorithmic approaches, formulas, and architecture designs.",
    prompt: "Compare and contrast the methodologies and architectures presented in the selected documents. Detail key strengths, algorithmic approaches, and trade-offs of each.",
  },
  {
    title: "Key Findings & Results",
    description: "Compare empirical metrics, accuracy benchmarks, and experimental results.",
    prompt: "Provide a comprehensive side-by-side comparison of the experimental results, evaluation metrics, and key empirical findings across the selected documents.",
  },
  {
    title: "Datasets & Evaluation Setup",
    description: "Compare training data, test splits, preprocessing, and test baselines.",
    prompt: "Compare the datasets, benchmark suites, preprocessing steps, and evaluation setups used across the selected documents. Highlight any differences in data distributions or sizes.",
  },
  {
    title: "Limitations & Future Work",
    description: "Synthesize the trade-offs, constraints, and suggested future research directions.",
    prompt: "Identify and contrast the explicit limitations, potential failure modes, computational costs, and proposed future directions mentioned in the selected documents.",
  },
];

export function DocumentComparisonView({
  projectId,
  documents,
  onRefreshDocuments,
  onProcessDocument,
}: DocumentComparisonViewProps) {
  // Numbered slots state: default 2 slots for comparison (Doc #1, Doc #2), can add up to 6
  const [slots, setSlots] = React.useState<NumberedSlot[]>([
    { slotNumber: 1, file: null, uploadedDocId: null, document: null, status: "empty" },
    { slotNumber: 2, file: null, uploadedDocId: null, document: null, status: "empty" },
  ]);

  // Comparison Query & Streaming Result State
  const [comparisonPrompt, setComparisonPrompt] = React.useState(COMPARISON_PRESETS[0].prompt);
  const [isComparing, setIsComparing] = React.useState(false);
  const [comparisonResult, setComparisonResult] = React.useState<string>("");
  const [statusMessage, setStatusMessage] = React.useState<string | null>(null);
  const [copied, setCopied] = React.useState(false);

  // Sync documents list into slots if uploadedDocId matches
  React.useEffect(() => {
    setSlots((prevSlots) =>
      prevSlots.map((slot) => {
        if (slot.uploadedDocId) {
          const matched = documents.find((d) => d.id === slot.uploadedDocId);
          if (matched) {
            return {
              ...slot,
              document: matched,
              status: matched.status === "ready" ? "ready" : matched.status === "failed" ? "failed" : "processing",
            };
          }
        }
        return slot;
      })
    );
  }, [documents]);

  // Handle adding another slot (Doc #3, Doc #4, ...)
  const handleAddSlot = () => {
    if (slots.length >= 6) return;
    setSlots((prev) => [
      ...prev,
      {
        slotNumber: prev.length + 1,
        file: null,
        uploadedDocId: null,
        document: null,
        status: "empty",
      },
    ]);
  };

  // Handle removing a slot
  const handleRemoveSlot = (slotNumber: number) => {
    if (slots.length <= 2) return; // Keep minimum 2 slots for comparison
    setSlots((prev) =>
      prev
        .filter((s) => s.slotNumber !== slotNumber)
        .map((s, idx) => ({ ...s, slotNumber: idx + 1 }))
    );
  };

  // Select an existing document from workspace for a slot
  const handleSelectExistingDoc = (slotNumber: number, docId: string) => {
    const doc = documents.find((d) => d.id === docId);
    if (!doc) return;
    setSlots((prev) =>
      prev.map((slot) => {
        if (slot.slotNumber === slotNumber) {
          return {
            ...slot,
            file: null,
            uploadedDocId: doc.id,
            document: doc,
            status: doc.status === "ready" ? "ready" : doc.status === "failed" ? "failed" : "processing",
          };
        }
        return slot;
      })
    );
  };

  // Upload file directly into a specific numbered slot
  const handleSlotFileUpload = async (slotNumber: number, file: File) => {
    setSlots((prev) =>
      prev.map((s) => (s.slotNumber === slotNumber ? { ...s, file, status: "uploading" } : s))
    );

    try {
      const uploaded = await apiClient.uploadDocument(projectId, file, { timeoutMs: 120000 });
      setSlots((prev) =>
        prev.map((s) =>
          s.slotNumber === slotNumber
            ? { ...s, uploadedDocId: uploaded.id, document: uploaded, status: "processing" }
            : s
        )
      );

      // Process, chunk and embed
      await onProcessDocument(uploaded.id);
      await onRefreshDocuments();

      setSlots((prev) =>
        prev.map((s) =>
          s.slotNumber === slotNumber
            ? { ...s, status: "ready" }
            : s
        )
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setSlots((prev) =>
        prev.map((s) =>
          s.slotNumber === slotNumber
            ? { ...s, status: "failed", error: msg }
            : s
        )
      );
    }
  };

  // Batch upload all empty/pending slots via drag and drop
  const handleBatchFiles = async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    const currentSlots = [...slots];

    // Ensure we have enough slots for the files
    while (currentSlots.length < fileArray.length && currentSlots.length < 6) {
      currentSlots.push({
        slotNumber: currentSlots.length + 1,
        file: null,
        uploadedDocId: null,
        document: null,
        status: "empty",
      });
    }

    setSlots(currentSlots);

    // Assign and upload each file to its corresponding slot
    for (let i = 0; i < fileArray.length && i < currentSlots.length; i++) {
      const targetSlotNumber = i + 1;
      const targetFile = fileArray[i];
      await handleSlotFileUpload(targetSlotNumber, targetFile);
    }
  };

  // Run AI Comparison across selected/ready numbered documents
  const handleRunComparison = async () => {
    const readyDocIds = slots
      .filter((s) => s.status === "ready" && s.uploadedDocId)
      .map((s) => s.uploadedDocId as string);

    if (readyDocIds.length < 2) {
      alert("Please upload or select at least 2 ready documents to compare.");
      return;
    }

    if (!comparisonPrompt.trim()) {
      alert("Please enter or select a comparison prompt.");
      return;
    }

    setIsComparing(true);
    setComparisonResult("");
    setStatusMessage("Gathering and balancing evidence from numbered documents...");

    try {
      const streamUrl = getApiUrl(`/api/v1/projects/${projectId}/ask/stream`);
      const response = await fetch(
        streamUrl,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: comparisonPrompt,
            document_ids: readyDocIds,
            top_k: 10,
          }),
        }
      );

      if (!response.ok || !response.body) {
        throw new Error(`Comparison API returned HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let partialData = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        partialData += decoder.decode(value, { stream: true });
        const blocks = partialData.split("\n\n");
        partialData = blocks.pop() || "";

        for (const block of blocks) {
          if (!block.trim()) continue;
          const eventMatch = block.match(/^event:\s*(.+)$/m);
          const dataMatch = block.match(/^data:\s*(.+)$/m);

          if (eventMatch && dataMatch) {
            const eventType = eventMatch[1].trim();
            const dataStr = dataMatch[1].trim();
            try {
              const dataObj = JSON.parse(dataStr);
              if (eventType === "token") {
                const textChunk = dataObj.content ?? dataObj.token ?? "";
                setComparisonResult((prev) => prev + textChunk);
                setStatusMessage(null);
              } else if (eventType === "status" || eventType === "research_started" || eventType === "research_step_started") {
                setStatusMessage(dataObj.message || `Analyzing ${dataObj.stage || "documents"}...`);
              } else if (eventType === "error") {
                setComparisonResult((prev) => `${prev}\n\n**Error**: ${dataObj.message || "An error occurred during comparison."}`);
                setStatusMessage(null);
              } else if (eventType === "complete") {
                setStatusMessage(null);
              }
            } catch {
              // ignore malformed SSE block
            }
          }
        }
      }
    } catch (err: unknown) {
      console.error("Comparison error", err);
      const msg = err instanceof Error ? err.message : "Failed to run comparison.";
      setComparisonResult(`**Error**: ${msg}`);
    } finally {
      setIsComparing(false);
      setStatusMessage(null);
    }
  };

  const handleCopyResult = () => {
    if (!comparisonResult) return;
    navigator.clipboard.writeText(comparisonResult);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const readyCount = slots.filter((s) => s.status === "ready").length;

  return (
    <div className="flex-1 min-h-0 flex flex-col gap-4 overflow-y-auto pr-1">
      {/* Top Header Card */}
      <Card className="border-border/80 bg-card/60 backdrop-blur-sm shadow-sm shrink-0">
        <CardHeader className="p-4 pb-3 border-b border-border/60">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 border border-primary/20 text-primary">
                <GitCompare className="h-5 w-5" />
              </div>
              <div>
                <CardTitle className="text-sm font-bold text-foreground flex items-center gap-2">
                  <span>Multi-Document Comparison Studio</span>
                  <Badge variant="secondary" className="text-[10px] font-mono font-normal">
                    {readyCount} / {slots.length} Ready
                  </Badge>
                </CardTitle>
                <p className="text-[11px] text-muted-foreground">
                  Upload numbered files or assign existing documents to compare methodologies, findings, datasets, and architectures.
                </p>
              </div>
            </div>

            {/* Batch Upload / Action Button */}
            <div className="flex items-center gap-2">
              <input
                type="file"
                id="batch-upload-input"
                multiple
                accept=".pdf,.docx,.txt,.csv,.xlsx,.xls,.json"
                className="hidden"
                onChange={(e) => e.target.files && handleBatchFiles(e.target.files)}
              />
              <Button
                size="sm"
                variant="outline"
                className="h-8 px-3 text-xs gap-1.5 bg-primary/10 border-primary/30 text-primary hover:bg-primary/20 cursor-pointer"
                onClick={() => document.getElementById("batch-upload-input")?.click()}
              >
                <Upload className="h-3.5 w-3.5" />
                <span>Batch Upload Files</span>
              </Button>

              {slots.length < 6 && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleAddSlot}
                  className="h-8 px-2.5 text-xs gap-1"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add File Slot
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Numbered File Slots Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 shrink-0">
        {slots.map((slot) => {
          const doc = slot.document;
          return (
            <Card
              key={slot.slotNumber}
              className={`border transition-all duration-200 ${
                slot.status === "ready"
                  ? "border-primary/40 bg-primary/5 shadow-xs"
                  : slot.status === "uploading" || slot.status === "processing"
                  ? "border-amber-500/40 bg-amber-500/5 animate-pulse"
                  : slot.status === "failed"
                  ? "border-destructive/40 bg-destructive/5"
                  : "border-border/60 bg-background/50 border-dashed"
              }`}
            >
              <div className="p-3.5 flex flex-col justify-between h-full space-y-3">
                {/* Slot Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary text-primary-foreground font-mono text-xs font-bold shadow-xs">
                      #{slot.slotNumber}
                    </span>
                    <span className="text-xs font-bold text-foreground">
                      Document #{slot.slotNumber}
                    </span>
                  </div>

                  <div className="flex items-center gap-1">
                    {slot.status === "ready" && (
                      <Badge variant="outline" className="text-[10px] text-emerald-400 border-emerald-500/30 gap-1 bg-emerald-500/10">
                        <CheckCircle2 className="h-3 w-3" /> Ready
                      </Badge>
                    )}
                    {(slot.status === "uploading" || slot.status === "processing") && (
                      <Badge variant="outline" className="text-[10px] text-amber-400 border-amber-500/30 gap-1 bg-amber-500/10">
                        <Loader2 className="h-3 w-3 animate-spin" /> {slot.status}
                      </Badge>
                    )}
                    {slot.status === "failed" && (
                      <Badge variant="destructive" className="text-[10px] gap-1">
                        <AlertCircle className="h-3 w-3" /> Error
                      </Badge>
                    )}
                    {slots.length > 2 && (
                      <button
                        onClick={() => handleRemoveSlot(slot.slotNumber)}
                        className="text-muted-foreground hover:text-destructive p-1 rounded transition-colors"
                        title="Remove this comparison slot"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Slot Body: Assigned Doc vs Upload or Select */}
                {doc ? (
                  <div className="p-2.5 rounded-lg bg-background/80 border border-border/60 space-y-1.5">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-primary shrink-0" />
                      <p className="font-semibold text-xs text-foreground truncate" title={doc.original_filename}>
                        {doc.original_filename}
                      </p>
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-muted-foreground font-mono">
                      <span>{(doc.file_size / 1024).toFixed(1)} KB</span>
                      <span className="uppercase">{doc.file_extension.replace(".", "")}</span>
                      <button
                        onClick={() => {
                          setSlots((prev) =>
                            prev.map((s) =>
                              s.slotNumber === slot.slotNumber
                                ? { ...s, file: null, uploadedDocId: null, document: null, status: "empty" }
                                : s
                            )
                          );
                        }}
                        className="text-xs text-primary hover:underline font-sans cursor-pointer"
                      >
                        Change
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {/* Direct Upload Input for this slot */}
                    <label className="flex flex-col items-center justify-center p-3 rounded-lg border border-dashed border-border/80 hover:border-primary/50 hover:bg-primary/5 transition-colors cursor-pointer text-center">
                      <input
                        type="file"
                        accept=".pdf,.docx,.txt,.csv,.xlsx,.xls,.json"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) handleSlotFileUpload(slot.slotNumber, file);
                        }}
                      />
                      <Upload className="h-4 w-4 text-muted-foreground mb-1" />
                      <span className="text-xs font-medium text-foreground">Upload file for Doc #{slot.slotNumber}</span>
                      <span className="text-[9px] text-muted-foreground">PDF, DOCX, CSV, Excel, TXT</span>
                    </label>

                    {/* Or Select From Existing Workspace Documents */}
                    {documents.length > 0 && (
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] text-muted-foreground shrink-0">or select:</span>
                        <select
                          className="w-full h-7 bg-background border border-border/60 rounded px-1.5 text-[10px] font-medium text-foreground truncate"
                          defaultValue=""
                          onChange={(e) => {
                            if (e.target.value) handleSelectExistingDoc(slot.slotNumber, e.target.value);
                          }}
                        >
                          <option value="" disabled>Choose existing doc...</option>
                          {documents.map((d) => (
                            <option key={d.id} value={d.id}>
                              {d.original_filename} ({d.status})
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      {/* Comparison Prompts & Presets Section */}
      <Card className="border-border/80 bg-card/60 backdrop-blur-sm shadow-sm shrink-0">
        <CardHeader className="p-3 px-4 pb-2 border-b border-border/60">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
              Comparison Presets
            </span>
            <span className="text-[10px] text-muted-foreground">Click a preset to load comparison prompt</span>
          </div>
        </CardHeader>
        <CardContent className="p-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
            {COMPARISON_PRESETS.map((preset, idx) => (
              <button
                key={idx}
                onClick={() => setComparisonPrompt(preset.prompt)}
                className={`text-left p-2.5 rounded-lg border text-xs transition-all cursor-pointer ${
                  comparisonPrompt === preset.prompt
                    ? "border-primary bg-primary/10 text-foreground font-semibold"
                    : "border-border/60 bg-background/50 hover:bg-muted/50 text-muted-foreground hover:text-foreground"
                }`}
              >
                <div className="font-semibold text-foreground flex items-center gap-1">
                  <span>{preset.title}</span>
                </div>
                <p className="text-[10px] text-muted-foreground mt-0.5 line-clamp-2">
                  {preset.description}
                </p>
              </button>
            ))}
          </div>

          {/* Custom Comparison Prompt Input */}
          <div className="mt-3 space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-foreground">
                Comparison Query / Instructions
              </label>
              <span className="text-[10px] text-muted-foreground">
                Comparing across {readyCount} ready documents
              </span>
            </div>
            <div className="flex gap-2">
              <textarea
                value={comparisonPrompt}
                onChange={(e) => setComparisonPrompt(e.target.value)}
                placeholder="E.g., Compare the methodologies, architectures, accuracy numbers, and dataset sizes between Document #1 and Document #2..."
                className="flex-1 h-20 bg-background border border-border/70 rounded-lg p-2.5 text-xs text-foreground resize-none focus:outline-none focus:ring-1 focus:ring-primary leading-relaxed font-sans"
              />
              <Button
                size="sm"
                onClick={handleRunComparison}
                disabled={isComparing || readyCount < 2}
                className="h-20 px-5 gap-2 bg-primary text-primary-foreground font-semibold shrink-0 cursor-pointer shadow-md hover:bg-primary/90"
              >
                {isComparing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <>
                    <GitCompare className="h-4 w-4" />
                    <span>Run Comparison</span>
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Comparison Results Card */}
      {(comparisonResult || isComparing || statusMessage) && (
        <Card className="flex-1 border-border/80 bg-card/60 backdrop-blur-sm shadow-sm flex flex-col min-h-[300px]">
          <CardHeader className="p-3 px-4 border-b border-border/60 flex flex-row items-center justify-between shrink-0 bg-background/40">
            <div className="flex items-center gap-2">
              <SplitSquareVertical className="h-4 w-4 text-primary" />
              <CardTitle className="text-xs font-bold text-foreground">
                Synthesis & Comparative Analysis
              </CardTitle>
            </div>

            <div className="flex items-center gap-2">
              {comparisonResult && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleCopyResult}
                  className="h-7 px-2 text-[10px] gap-1 cursor-pointer"
                >
                  {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                  <span>{copied ? "Copied" : "Copy Analysis"}</span>
                </Button>
              )}
            </div>
          </CardHeader>

          <CardContent className="p-4 flex-1 overflow-y-auto text-xs leading-relaxed">
            {statusMessage && (
              <div className="flex items-center gap-2 text-primary font-medium text-xs mb-3 animate-pulse">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>{statusMessage}</span>
              </div>
            )}

            {comparisonResult ? (
              <div className="prose prose-sm dark:prose-invert max-w-none break-words">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {comparisonResult}
                </ReactMarkdown>
              </div>
            ) : isComparing ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground space-y-2">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
                <p className="text-xs">Balancing context chunks across selected documents...</p>
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
