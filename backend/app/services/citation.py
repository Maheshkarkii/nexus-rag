import logging
import re
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ai_research_assistant.services.citation")


class SourceRegistry:
    """Request-scoped registry mapping stable temporary source IDs to actual retrieved document chunks."""

    def __init__(self) -> None:
        self._registry: Dict[str, Dict[str, Any]] = {}

    def register(self, chunk: Dict[str, Any]) -> str:
        """Register a chunk and return its stable temporary source ID (e.g. S1)."""
        # If already registered (e.g. unique chunks check), return existing key
        chunk_id = chunk.get("chunk_id") or chunk.get("id")
        for sid, registered in self._registry.items():
            reg_id = registered.get("chunk_id") or registered.get("id")
            if reg_id and reg_id == chunk_id:
                return sid

        # Otherwise, assign new source ID
        next_idx = len(self._registry) + 1
        source_id = f"S{next_idx}"
        self._registry[source_id] = chunk
        return source_id

    def resolve(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Resolve a temporary source ID back to the original chunk metadata."""
        return self._registry.get(source_id)

    def get_all_sources(self) -> List[Dict[str, Any]]:
        """Get all registered chunks in this request context."""
        return list(self._registry.values())


class CitationParser:
    """Parser to extract structured source identifiers from LLM generated text."""

    def parse(self, text: str) -> List[str]:
        """Extract citations (e.g. [S1], [S2]) from text, returning unique IDs in first-appearance order."""
        if not text:
            return []

        # Find all occurrences of [S1], [S2], etc.
        matches = re.findall(r"\[S(\d+)\]", text)
        
        seen = set()
        ordered_sources = []
        for match in matches:
            source_id = f"S{match}"
            if source_id not in seen:
                seen.add(source_id)
                ordered_sources.append(source_id)
        
        return ordered_sources


class CitationResolver:
    """Resolver converting text citation keys back to backend metadata structures."""

    def resolve(self, source_ids: List[str], registry: SourceRegistry) -> List[Dict[str, Any]]:
        """Convert a list of citation keys to structured metadata dictionaries, filtering out invalid ones."""
        resolved = []
        for sid in source_ids:
            chunk = registry.resolve(sid)
            if not chunk:
                logger.warning(f"LLM hallucinated citation '{sid}' which does not exist in registry. Skipping.")
                continue

            metadata = chunk.get("metadata", {})
            
            # Map location details
            location = {
                "page_number": metadata.get("page_number"),
                "section_title": metadata.get("section_title"),
                "paragraph_index": metadata.get("paragraph_index"),
                "sheet_name": metadata.get("sheet_name"),
                "row_start": metadata.get("row_start"),
                "row_end": metadata.get("row_end"),
                "column_range": metadata.get("column_range"),
                "json_path": metadata.get("json_path"),
                "line_start": metadata.get("line_start"),
                "line_end": metadata.get("line_end"),
            }

            # Map the response reference structure
            text_preview = chunk.get("text", "")
            preview = text_preview[:200]
            if len(text_preview) > 200:
                preview += "..."

            ref = {
                "source_id": sid,
                "document_id": chunk.get("document_id"),
                "chunk_id": chunk.get("chunk_id") or chunk.get("id") or uuid.uuid4(),
                "filename": metadata.get("source_filename") or "Unknown Document",
                "location": location,
                "relevance_score": float(chunk.get("score", 0.0)),
                "preview": preview,
            }
            resolved.append(ref)

        return resolved
