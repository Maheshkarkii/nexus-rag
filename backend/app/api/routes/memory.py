from fastapi import APIRouter, HTTPException, status
from typing import List

from app.services.research_memory import (
    ResearchFinding,
    ResearchNote,
    SavedSource,
    research_memory_service,
)

router = APIRouter(prefix="/projects/{project_id}", tags=["Research Workspace Memory"])


@router.post("/findings", response_model=ResearchFinding, summary="Save Research Finding")
async def save_finding(project_id: str, finding: ResearchFinding):
    """Save a verified research finding to persistent workspace memory."""
    finding.project_id = project_id
    return research_memory_service.save_finding(finding)


@router.get("/findings", response_model=List[ResearchFinding], summary="Get Project Findings")
async def get_findings(project_id: str):
    """Retrieve active research findings for project workspace."""
    return research_memory_service.get_findings(project_id)


@router.delete("/findings/{finding_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Finding")
async def delete_finding(project_id: str, finding_id: str):
    """Delete a research finding from project workspace memory."""
    deleted = research_memory_service.delete_finding(project_id, finding_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Finding not found")


@router.post("/notes", response_model=ResearchNote, summary="Save User Note")
async def save_note(project_id: str, note: ResearchNote):
    """Save a research note to project workspace."""
    note.project_id = project_id
    return research_memory_service.save_note(note)


@router.get("/notes", response_model=List[ResearchNote], summary="Get Project Notes")
async def get_notes(project_id: str):
    """Retrieve user research notes for project workspace."""
    return research_memory_service.get_notes(project_id)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Note")
async def delete_note(project_id: str, note_id: str):
    """Delete a research note from project workspace."""
    deleted = research_memory_service.delete_note(project_id, note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")


@router.post("/sources", response_model=SavedSource, summary="Save Bookmarked Source")
async def save_source(project_id: str, source: SavedSource):
    """Bookmark an important source reference for persistent research reuse."""
    source.project_id = project_id
    return research_memory_service.save_source(source)


@router.get("/sources", response_model=List[SavedSource], summary="Get Saved Sources")
async def get_sources(project_id: str):
    """Retrieve bookmarked sources for project workspace."""
    return research_memory_service.get_sources(project_id)
