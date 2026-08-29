"use client";

import * as React from "react";
import { Sparkles, Check, RotateCcw, FileCode, BookOpen, Zap } from "lucide-react";


import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export interface RagConfig {
  topK: number;
  chunkSize: number;
  chunkOverlap: number;
}

export const DEFAULT_RAG_CONFIG: RagConfig = {
  topK: 8,
  chunkSize: 500,
  chunkOverlap: 100,
};

interface Preset {
  id: string;
  name: string;
  description: string;
  icon: React.ElementType;
  config: RagConfig;
  badge: string;
}

const PRESETS: Preset[] = [
  {
    id: "balanced",
    name: "Balanced Research",
    description: "Optimal balance of precision and context for multi-topic documents.",
    icon: Sparkles,
    badge: "Recommended",
    config: { topK: 8, chunkSize: 500, chunkOverlap: 100 },
  },
  {
    id: "academic",
    name: "Deep Academic Synthesis",
    description: "Larger context blocks and broad evidence for literature reviews and research papers.",
    icon: BookOpen,
    badge: "Papers & Journals",
    config: { topK: 12, chunkSize: 1000, chunkOverlap: 200 },
  },
  {
    id: "precise",
    name: "Fast Fact-Checking",
    description: "Tight, focused chunk sizes for pinpoint exact quotes and definitions.",
    icon: Zap,
    badge: "Low Latency",
    config: { topK: 4, chunkSize: 300, chunkOverlap: 50 },
  },
  {
    id: "tabular",
    name: "Structured & Tabular Data",
    description: "Compact chunks optimized for spreadsheet rows, CSV lines, and JSON structures.",
    icon: FileCode,
    badge: "CSV / Excel / JSON",
    config: { topK: 10, chunkSize: 250, chunkOverlap: 30 },
  },
];

export interface RagConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: RagConfig;
  onSave: (config: RagConfig) => void;
}

export function RagConfigModal({ isOpen, onClose, config: initialConfig, onSave }: RagConfigModalProps) {
  const [localConfig, setLocalConfig] = React.useState<RagConfig>(initialConfig);
  const [activePreset, setActivePreset] = React.useState<string | null>(null);

  // Sync initial config when modal opens
  React.useEffect(() => {
    setLocalConfig(initialConfig);
    const matched = PRESETS.find(
      (p) =>
        p.config.topK === initialConfig.topK &&
        p.config.chunkSize === initialConfig.chunkSize &&
        p.config.chunkOverlap === initialConfig.chunkOverlap
    );
    setActivePreset(matched ? matched.id : null);
  }, [initialConfig, isOpen]);

  const handlePresetSelect = (preset: Preset) => {
    setLocalConfig(preset.config);
    setActivePreset(preset.id);
  };

  const handleFieldChange = <K extends keyof RagConfig>(key: K, value: number) => {
    setActivePreset(null);
    setLocalConfig((prev) => {
      const next = { ...prev, [key]: value };
      // Ensure overlap doesn't exceed chunk size
      if (key === "chunkSize" && next.chunkOverlap >= value) {
        next.chunkOverlap = Math.max(0, Math.floor(value * 0.2));
      }
      if (key === "chunkOverlap" && value >= next.chunkSize) {
        next.chunkOverlap = Math.max(0, next.chunkSize - 50);
      }
      return next;
    });
  };

  const handleReset = () => {
    setLocalConfig(DEFAULT_RAG_CONFIG);
    setActivePreset("balanced");
  };

  const handleSave = () => {
    onSave(localConfig);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="RAG & Ingestion Hyperparameters"
      description="Configure evidence retrieval depth (Top K) and document chunking granularity."
      maxWidth="lg"
    >
      <div className="space-y-6">
        {/* Recommended Presets */}
        <div>
          <div className="flex items-center justify-between mb-2.5">
            <span className="text-xs font-semibold text-foreground uppercase tracking-wider">
              Smart Preset Profiles
            </span>
            <span className="text-[11px] text-muted-foreground">Click to apply instant tuning</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {PRESETS.map((preset) => {
              const Icon = preset.icon;
              const isSelected = activePreset === preset.id;
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => handlePresetSelect(preset)}
                  className={`flex flex-col text-left p-3 rounded-xl border transition-all cursor-pointer relative ${
                    isSelected
                      ? "border-primary bg-primary/10 shadow-sm shadow-primary/10"
                      : "border-border/80 bg-card/60 hover:border-primary/40 hover:bg-accent/40"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-2">
                      <div
                        className={`flex h-6 w-6 items-center justify-center rounded-lg ${
                          isSelected ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                        }`}
                      >
                        <Icon className="h-3.5 w-3.5" />
                      </div>
                      <span className="text-xs font-semibold text-foreground">{preset.name}</span>
                    </div>
                    <Badge variant={isSelected ? "default" : "outline"} className="text-[9px] px-1.5 py-0">
                      {preset.badge}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
                    {preset.description}
                  </p>
                  <div className="mt-2 pt-2 border-t border-border/40 flex items-center gap-3 text-[10px] font-mono text-muted-foreground">
                    <span>Top K: <strong className="text-foreground">{preset.config.topK}</strong></span>
                    <span>Chunk: <strong className="text-foreground">{preset.config.chunkSize}</strong></span>
                    <span>Overlap: <strong className="text-foreground">{preset.config.chunkOverlap}</strong></span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Sliders & Parameter Customization */}
        <div className="space-y-4 rounded-xl border border-border/80 bg-background/50 p-4">
          <div className="flex items-center justify-between border-b border-border/40 pb-2">
            <span className="text-xs font-semibold text-foreground uppercase tracking-wider">
              Fine-Tuning Controls
            </span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleReset}
              className="h-6 px-2 text-[11px] text-muted-foreground hover:text-foreground gap-1"
            >
              <RotateCcw className="h-3 w-3" />
              Reset Defaults
            </Button>
          </div>

          {/* Top K (Top Results) */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <label htmlFor="top-k-input" className="text-xs font-medium text-foreground">
                  Top Results (top_k)
                </label>
                <span className="text-[10px] text-muted-foreground font-normal">
                  — Number of evidence chunks evaluated by LLM
                </span>
              </div>
              <div className="flex items-center gap-2">
                <input
                  id="top-k-input"
                  type="number"
                  min={1}
                  max={50}
                  value={localConfig.topK}
                  onChange={(e) => handleFieldChange("topK", Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
                  className="w-14 rounded-md border border-border bg-card px-2 py-0.5 text-right font-mono text-xs text-foreground focus:border-primary focus:outline-none"
                />
                <span className="text-[11px] font-mono text-muted-foreground">chunks</span>
              </div>
            </div>
            <input
              type="range"
              min={1}
              max={25}
              step={1}
              value={localConfig.topK}
              onChange={(e) => handleFieldChange("topK", Number(e.target.value))}
              className="w-full accent-primary cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
              <span>1 (Focused)</span>
              <span>8 (Standard)</span>
              <span>15 (Broad)</span>
              <span>25 (Deep)</span>
            </div>
          </div>

          {/* Chunk Size */}
          <div className="space-y-2 pt-2 border-t border-border/40">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <label htmlFor="chunk-size-input" className="text-xs font-medium text-foreground">
                  Chunk Size (chunk_size)
                </label>
                <span className="text-[10px] text-muted-foreground font-normal">
                  — Maximum character length per partitioned fragment
                </span>
              </div>
              <div className="flex items-center gap-2">
                <input
                  id="chunk-size-input"
                  type="number"
                  min={100}
                  max={3000}
                  step={50}
                  value={localConfig.chunkSize}
                  onChange={(e) =>
                    handleFieldChange("chunkSize", Math.max(100, Math.min(3000, Number(e.target.value) || 100)))
                  }
                  className="w-16 rounded-md border border-border bg-card px-2 py-0.5 text-right font-mono text-xs text-foreground focus:border-primary focus:outline-none"
                />
                <span className="text-[11px] font-mono text-muted-foreground">chars</span>
              </div>
            </div>
            <input
              type="range"
              min={100}
              max={2000}
              step={50}
              value={localConfig.chunkSize}
              onChange={(e) => handleFieldChange("chunkSize", Number(e.target.value))}
              className="w-full accent-primary cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
              <span>100 chars</span>
              <span>500 (Default)</span>
              <span>1000 (Papers)</span>
              <span>2000 chars</span>
            </div>
          </div>

          {/* Chunk Overlap */}
          <div className="space-y-2 pt-2 border-t border-border/40">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <label htmlFor="chunk-overlap-input" className="text-xs font-medium text-foreground">
                  Chunk Overlap (chunk_overlap)
                </label>
                <span className="text-[10px] text-muted-foreground font-normal">
                  — Shared boundary characters to preserve context continuity
                </span>
              </div>
              <div className="flex items-center gap-2">
                <input
                  id="chunk-overlap-input"
                  type="number"
                  min={0}
                  max={Math.max(0, localConfig.chunkSize - 50)}
                  step={10}
                  value={localConfig.chunkOverlap}
                  onChange={(e) =>
                    handleFieldChange(
                      "chunkOverlap",
                      Math.max(0, Math.min(localConfig.chunkSize - 50, Number(e.target.value) || 0))
                    )
                  }
                  className="w-16 rounded-md border border-border bg-card px-2 py-0.5 text-right font-mono text-xs text-foreground focus:border-primary focus:outline-none"
                />
                <span className="text-[11px] font-mono text-muted-foreground">chars</span>
              </div>
            </div>
            <input
              type="range"
              min={0}
              max={Math.min(500, Math.floor(localConfig.chunkSize * 0.5))}
              step={10}
              value={localConfig.chunkOverlap}
              onChange={(e) => handleFieldChange("chunkOverlap", Number(e.target.value))}
              className="w-full accent-primary cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
              <span>0 (None)</span>
              <span>100 (Balanced)</span>
              <span>{Math.min(500, Math.floor(localConfig.chunkSize * 0.5))} chars</span>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between pt-2">
          <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
            <span>Applied:</span>
            <Badge variant="secondary" className="text-[10px]">
              top_k={localConfig.topK}, size={localConfig.chunkSize}, overlap={localConfig.chunkOverlap}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <Button type="button" variant="outline" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="button" size="sm" onClick={handleSave} className="gap-1.5 shadow-sm shadow-primary/20">
              <Check className="h-3.5 w-3.5" />
              Save Configuration
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
