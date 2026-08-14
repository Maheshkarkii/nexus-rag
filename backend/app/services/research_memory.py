import logging
import time
import uuid

from pydantic import BaseModel, Field

logger = logging.getLogger("ai_research_assistant.research_memory")


# --- Memory Models ---

class ResearchFinding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    user_id: str | None = None
    statement: str
    source_ids: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    status: str = "active"  # active, superseded, disputed, archived
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class ResearchNote(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    user_id: str | None = None
    title: str
    content: str
    source_ids: list[str] = Field(default_factory=list)
    is_ai_generated: bool = False
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class SavedSource(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    user_id: str | None = None
    document_id: str
    filename: str
    page_number: int | None = None
    section_title: str | None = None
    excerpt: str
    created_at: float = Field(default_factory=time.time)


class ResearchSummary(BaseModel):
    project_id: str
    objective: str
    key_findings: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    updated_at: float = Field(default_factory=time.time)


# --- Memory Store Service ---

class ResearchMemoryService:
    """Manages persistent, structured, authorized research context for projects."""

    MAX_MEMORY_ITEMS = 5
    MAX_MEMORY_TOKENS = 1000

    def __init__(self) -> None:
        self._findings: dict[str, list[ResearchFinding]] = {}
        self._notes: dict[str, list[ResearchNote]] = {}
        self._sources: dict[str, list[SavedSource]] = {}
        self._summaries: dict[str, ResearchSummary] = {}

    def save_finding(self, finding: ResearchFinding) -> ResearchFinding:
        p_id = finding.project_id
        if p_id not in self._findings:
            self._findings[p_id] = []
        self._findings[p_id].append(finding)
        return finding

    def get_findings(self, project_id: str) -> list[ResearchFinding]:
        return [f for f in self._findings.get(project_id, []) if f.status == "active"]

    def delete_finding(self, project_id: str, finding_id: str) -> bool:
        if project_id in self._findings:
            initial = len(self._findings[project_id])
            self._findings[project_id] = [f for f in self._findings[project_id] if f.id != finding_id]
            return len(self._findings[project_id]) < initial
        return False

    def save_note(self, note: ResearchNote) -> ResearchNote:
        p_id = note.project_id
        if p_id not in self._notes:
            self._notes[p_id] = []
        self._notes[p_id].append(note)
        return note

    def get_notes(self, project_id: str) -> list[ResearchNote]:
        return self._notes.get(project_id, [])

    def delete_note(self, project_id: str, note_id: str) -> bool:
        if project_id in self._notes:
            initial = len(self._notes[project_id])
            self._notes[project_id] = [n for n in self._notes[project_id] if n.id != note_id]
            return len(self._notes[project_id]) < initial
        return False

    def save_source(self, source: SavedSource) -> SavedSource:
        p_id = source.project_id
        if p_id not in self._sources:
            self._sources[p_id] = []
        self._sources[p_id].append(source)
        return source

    def get_sources(self, project_id: str) -> list[SavedSource]:
        return self._sources.get(project_id, [])

    def build_memory_context(self, project_id: str, query: str) -> str:
        """Build compact, bounded memory context string for research prompt inclusion."""
        findings = self.get_findings(project_id)
        notes = self.get_notes(project_id)

        if not findings and not notes:
            return ""

        q_lower = query.lower()

        # Score & select relevant findings
        selected_findings = []
        for f in findings:
            if any(w in f.statement.lower() for w in q_lower.split()):
                selected_findings.append(f.statement)
            if len(selected_findings) >= self.MAX_MEMORY_ITEMS:
                break

        # Fallback to recent findings if no direct match
        if not selected_findings and findings:
            selected_findings = [f.statement for f in findings[: self.MAX_MEMORY_ITEMS]]

        findings_block = ""
        if selected_findings:
            findings_block = "PRIOR RELEVANT RESEARCH FINDINGS:\n- " + "\n- ".join(selected_findings)

        notes_block = ""
        if notes:
            notes_block = "USER RESEARCH NOTES:\n- " + "\n- ".join([f"{n.title}: {n.content}" for n in notes[:2]])

        context_str = f"--- PERSISTENT WORKSPACE MEMORY ---\n{findings_block}\n{notes_block}\n-----------------------------------\n"
        return context_str


research_memory_service = ResearchMemoryService()
