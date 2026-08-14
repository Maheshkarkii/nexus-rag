"use client";

import * as React from "react";
import { Sparkles, AlertCircle } from "lucide-react";
import { apiClient } from "@/lib/api";
import { ProjectResponse } from "@/lib/api/types";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface CreateProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (newProject: ProjectResponse) => void;
}

export function CreateProjectModal({ isOpen, onClose, onSuccess }: CreateProjectModalProps) {
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [validationError, setValidationError] = React.useState<string | null>(null);
  const [apiError, setApiError] = React.useState<string | null>(null);

  // Reset form state on open/close
  React.useEffect(() => {
    if (isOpen) {
      setName("");
      setDescription("");
      setValidationError(null);
      setApiError(null);
      setIsSubmitting(false);
    }
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    setApiError(null);

    const trimmedName = name.trim();
    if (!trimmedName) {
      setValidationError("Project title is required and cannot be blank.");
      return;
    }
    if (trimmedName.length > 255) {
      setValidationError("Project title cannot exceed 255 characters.");
      return;
    }

    setIsSubmitting(true);
    try {
      const created = await apiClient.createProject({
        name: trimmedName,
        description: description.trim() || undefined,
      });
      onSuccess(created);
      onClose();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to create project. Please try again.";
      setApiError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Create Research Project"
      description="Initialize a dedicated workspace to organize papers, datasets, RAG queries, and findings."
      maxWidth="md"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Error Alert Banner */}
        {(validationError || apiError) && (
          <div className="flex items-start gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <p className="leading-relaxed">{validationError || apiError}</p>
          </div>
        )}

        {/* Project Name Field */}
        <div className="space-y-1.5">
          <label htmlFor="project-name" className="block text-xs font-semibold text-foreground">
            Project Name <span className="text-destructive">*</span>
          </label>
          <Input
            id="project-name"
            type="text"
            placeholder="e.g. Attention & Transformer Architecture Synthesis"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              if (validationError) setValidationError(null);
            }}
            disabled={isSubmitting}
            autoFocus
            maxLength={255}
            required
            className="text-xs"
          />
          <p className="text-[10px] text-muted-foreground">
            A descriptive title for your research goals and document corpus.
          </p>
        </div>

        {/* Project Description Field */}
        <div className="space-y-1.5">
          <label htmlFor="project-description" className="block text-xs font-semibold text-foreground">
            Description <span className="text-muted-foreground text-[10px] font-normal">(Optional)</span>
          </label>
          <textarea
            id="project-description"
            rows={3}
            placeholder="e.g. Comprehensive review of long-context mechanisms and KV-cache optimizations across modern LLMs."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={isSubmitting}
            maxLength={5000}
            className="flex w-full rounded-lg border border-border bg-input/50 px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 resize-none transition-colors"
          />
          <p className="text-[10px] text-muted-foreground">
            Optional scope, methodology notes, or hypothesis details.
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 pt-2 border-t border-border/50">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="default"
            size="sm"
            isLoading={isSubmitting}
            className="gap-1.5"
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>Create Workspace</span>
          </Button>
        </div>
      </form>
    </Modal>
  );
}
