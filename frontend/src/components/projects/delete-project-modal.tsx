"use client";

import * as React from "react";
import { AlertTriangle, AlertCircle, Trash2 } from "lucide-react";
import { apiClient } from "@/lib/api";
import { ProjectResponse } from "@/lib/api/types";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";

export interface DeleteProjectModalProps {
  project: ProjectResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (deletedId: string) => void;
}

export function DeleteProjectModal({ project, isOpen, onClose, onSuccess }: DeleteProjectModalProps) {
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [apiError, setApiError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (isOpen) {
      setApiError(null);
      setIsDeleting(false);
    }
  }, [isOpen]);

  const handleDelete = async () => {
    if (!project) return;

    setIsDeleting(true);
    setApiError(null);
    try {
      await apiClient.deleteProject(project.id);
      onSuccess(project.id);
      onClose();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to delete research project. Please try again.";
      setApiError(message);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Delete Research Project?"
      description="This action will permanently delete the project workspace and cannot be undone."
      maxWidth="sm"
    >
      <div className="space-y-4">
        {/* Error Alert Banner */}
        {apiError && (
          <div className="flex items-start gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <p className="leading-relaxed">{apiError}</p>
          </div>
        )}

        {/* Warning Details */}
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3.5 flex items-start gap-3">
          <AlertTriangle className="h-4 w-4 shrink-0 text-destructive mt-0.5" />
          <div className="text-xs text-foreground space-y-1">
            <p className="font-semibold text-destructive">Destructive Operation</p>
            <p className="text-muted-foreground leading-relaxed">
              Are you sure you want to remove{" "}
              <strong className="text-foreground font-semibold">
                &ldquo;{project?.name}&rdquo;
              </strong>
              ?
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 pt-2 border-t border-border/50">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onClose}
            disabled={isDeleting}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            isLoading={isDeleting}
            onClick={handleDelete}
            className="gap-1.5"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span>Delete Project</span>
          </Button>
        </div>
      </div>
    </Modal>
  );
}
