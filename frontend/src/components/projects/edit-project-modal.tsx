"use client";

import * as React from "react";
import { Edit3, AlertCircle } from "lucide-react";
import { apiClient } from "@/lib/api";
import { ProjectResponse } from "@/lib/api/types";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface EditProjectModalProps {
  project: ProjectResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updated: ProjectResponse) => void;
}

export function EditProjectModal({ project, isOpen, onClose, onSuccess }: EditProjectModalProps) {
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [validationError, setValidationError] = React.useState<string | null>(null);
  const [apiError, setApiError] = React.useState<string | null>(null);

  // Synchronize initial project state
  React.useEffect(() => {
    if (project && isOpen) {
      setName(project.name);
      setDescription(project.description || "");
      setValidationError(null);
      setApiError(null);
      setIsSubmitting(false);
    }
  }, [project, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!project) return;

    setValidationError(null);
    setApiError(null);

    const trimmedName = name.trim();
    if (!trimmedName) {
      setValidationError("Project title cannot be blank.");
      return;
    }
    if (trimmedName.length > 255) {
      setValidationError("Project title cannot exceed 255 characters.");
      return;
    }

    setIsSubmitting(true);
    try {
      const updated = await apiClient.updateProject(project.id, {
        name: trimmedName,
        description: description.trim() ? description.trim() : null,
      });
      onSuccess(updated);
      onClose();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to update project. Please try again.";
      setApiError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Edit Research Workspace"
      description="Modify workspace title or refine research objectives."
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
          <label htmlFor="edit-project-name" className="block text-xs font-semibold text-foreground">
            Project Name <span className="text-destructive">*</span>
          </label>
          <Input
            id="edit-project-name"
            type="text"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              if (validationError) setValidationError(null);
            }}
            disabled={isSubmitting}
            maxLength={255}
            required
            className="text-xs"
          />
        </div>

        {/* Project Description Field */}
        <div className="space-y-1.5">
          <label htmlFor="edit-project-description" className="block text-xs font-semibold text-foreground">
            Description <span className="text-muted-foreground text-[10px] font-normal">(Optional)</span>
          </label>
          <textarea
            id="edit-project-description"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={isSubmitting}
            maxLength={5000}
            className="flex w-full rounded-lg border border-border bg-input/50 px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 resize-none transition-colors"
          />
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
            <Edit3 className="h-3.5 w-3.5" />
            <span>Save Changes</span>
          </Button>
        </div>
      </form>
    </Modal>
  );
}
