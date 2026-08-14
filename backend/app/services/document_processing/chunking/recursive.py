from typing import List, Dict, Any
from app.db.models.document import Document
from app.services.document_processing.chunking.strategy import ChunkingStrategy

def count_tokens(text: str) -> int:
    """
    Estimate token count for a text block.
    Stage 10 specifies model-independent, deterministic token estimation.
    We use standard English token heuristic (approx. 4 characters per token).
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


class RecursiveChunkingStrategy(ChunkingStrategy):
    """
    Recursively splits text using a list of separators in order of priority:
    paragraphs (\\n\\n), lines (\\n), sentences (. , ? , ! ), words ( ), and characters.
    """

    def __init__(self, separators: List[str] = None):
        self.separators = separators or ["\n\n", "\n", ". ", "? ", "! ", " ", ""]

    def _split_text(self, text: str, separators: List[str], max_size: int) -> List[str]:
        if not text:
            return []

        if len(text) <= max_size:
            return [text]

        # Find first separator that exists in the text
        separator = None
        remaining_separators = []
        for idx, sep in enumerate(separators):
            if sep in text:
                separator = sep
                remaining_separators = separators[idx + 1 :]
                break

        # Fallback if no separators match
        if separator is None:
            return [text[i : i + max_size] for i in range(0, len(text), max_size)]

        # Split text by the separator
        parts = text.split(separator)
        splits = []

        for i, part in enumerate(parts):
            # Keep separator at the end of the split if it's punctuation, or reconstruct it
            # Except for the last part if it didn't originally end with the separator
            if separator and i < len(parts) - 1:
                part_with_sep = part + separator
            else:
                part_with_sep = part

            if not part_with_sep:
                continue

            if len(part_with_sep) <= max_size:
                splits.append(part_with_sep)
            else:
                # Recursively split the part that is too large
                sub_splits = self._split_text(part_with_sep, remaining_separators, max_size)
                splits.extend(sub_splits)

        return splits

    def chunk(self, text: str, document: Document, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
        if not text or not text.strip():
            return []

        # Step 1: Split into primitive fragments based on target chunk_size
        splits = self._split_text(text, self.separators, chunk_size)

        # Step 2: Combine splits into chunks up to chunk_size, keeping track of overlap
        chunks = []
        current_chunk_parts = []
        current_chunk_len = 0

        for split in splits:
            split_len = len(split)
            if not split.strip():
                continue

            # If adding this split exceeds chunk_size, finalize current chunk
            if current_chunk_parts and current_chunk_len + split_len > chunk_size:
                chunk_text = "".join(current_chunk_parts).strip()
                if chunk_text:
                    chunks.append(chunk_text)

                # Track overlap: keep parts from the end of the current chunk up to chunk_overlap characters
                overlap_parts = []
                overlap_len = 0
                for part in reversed(current_chunk_parts):
                    if overlap_len + len(part) <= chunk_overlap:
                        overlap_parts.insert(0, part)
                        overlap_len += len(part)
                    else:
                        break
                current_chunk_parts = overlap_parts
                current_chunk_len = overlap_len

            current_chunk_parts.append(split)
            current_chunk_len += split_len

        # Append final chunk
        if current_chunk_parts:
            chunk_text = "".join(current_chunk_parts).strip()
            if chunk_text:
                chunks.append(chunk_text)

        return [{"text": c, "metadata": {}} for c in chunks]
