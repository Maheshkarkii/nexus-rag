import re
from typing import List, Dict, Any
from app.db.models.document import Document
from app.services.document_processing.chunking.strategy import ChunkingStrategy
from app.services.document_processing.chunking.recursive import RecursiveChunkingStrategy


class PDFChunkingStrategy(RecursiveChunkingStrategy):
    """
    Chunks PDF text page-by-page, preserving page numbers in metadata for citations.
    """

    def chunk(self, text: str, document: Document, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
        # PDFProcessor formats page markers as "--- Page {idx} ---"
        pattern = r"--- Page (\d+) ---\n"
        matches = list(re.finditer(pattern, text))

        if not matches:
            # Fallback to standard recursive chunking if no page markers exist
            return super().chunk(text, document, chunk_size, chunk_overlap)

        chunks = []
        for i in range(len(matches)):
            start_pos = matches[i].end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            page_num = int(matches[i].group(1))
            page_text = text[start_pos:end_pos].strip()

            if not page_text:
                continue

            page_chunks = super().chunk(page_text, document, chunk_size, chunk_overlap)
            for pc in page_chunks:
                pc["metadata"] = {
                    "page_number": page_num,
                    "page_start": page_num,
                    "page_end": page_num,
                }
                chunks.append(pc)

        return chunks


class DocxChunkingStrategy(RecursiveChunkingStrategy):
    """
    Chunks Word document text by section headings, preserving hierarchy paths.
    """

    def chunk(self, text: str, document: Document, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
        # DocxProcessor prefixes headings with "## "
        lines = text.split("\n")
        chunks = []
        
        sections = []
        current_section_title = None
        current_section_path = []
        current_section_text = []

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            if line_stripped.startswith("## "):
                # Finalize the current section before starting a new one
                if current_section_text or current_section_title:
                    sections.append({
                        "title": current_section_title,
                        "path": " > ".join(current_section_path) if current_section_path else None,
                        "text": "\n\n".join(current_section_text),
                    })

                heading_text = line_stripped[3:].strip()
                current_section_title = heading_text
                current_section_path = [heading_text]
                current_section_text = []
            else:
                current_section_text.append(line_stripped)

        # Append the last section
        if current_section_text or current_section_title:
            sections.append({
                "title": current_section_title,
                "path": " > ".join(current_section_path) if current_section_path else None,
                "text": "\n\n".join(current_section_text),
            })

        for sec in sections:
            if not sec["text"].strip():
                continue
            sec_chunks = super().chunk(sec["text"], document, chunk_size, chunk_overlap)
            for sc in sec_chunks:
                metadata = {}
                if sec["title"]:
                    metadata["section_title"] = sec["title"]
                if sec["path"]:
                    metadata["section_path"] = sec["path"]
                sc["metadata"] = metadata
                chunks.append(sc)

        return chunks


class CSVChunkingStrategy(ChunkingStrategy):
    """
    Chunks CSV datasets row-by-row, keeping column headers on each chunk and tracking row ranges.
    """

    def chunk(self, text: str, document: Document, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
        lines = text.split("\n")
        if not lines:
            return []

        # Parse column headers
        columns_line = lines[0]
        columns = []
        if columns_line.startswith("Columns: "):
            columns = [col.strip() for col in columns_line[9:].split("|")]

        row_lines = []
        for line in lines[1:]:
            if line.strip().startswith("Row "):
                row_lines.append(line.strip())

        if not row_lines:
            # Fallback to simple split if rows are not parsed
            return [{"text": text, "metadata": {"column_names": columns}}]

        chunks = []
        current_chunk_rows = []
        # Header + double newline
        current_chunk_char_count = len(columns_line) + 2
        row_start = 1

        for idx, row_line in enumerate(row_lines, start=1):
            row_len = len(row_line) + 1 # + newline
            if current_chunk_rows and current_chunk_char_count + row_len > chunk_size:
                chunk_text = columns_line + "\n\n" + "\n".join(current_chunk_rows)
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "column_names": columns,
                        "row_start": row_start,
                        "row_end": idx - 1,
                    },
                })

                # Respect overlap by keeping trailing rows within the overlap window
                overlap_rows = []
                overlap_chars = len(columns_line) + 2
                for r in reversed(current_chunk_rows):
                    if overlap_chars + len(r) + 1 <= chunk_overlap:
                        overlap_rows.insert(0, r)
                        overlap_chars += len(r) + 1
                    else:
                        break

                current_chunk_rows = overlap_rows
                current_chunk_char_count = overlap_chars
                row_start = idx - len(overlap_rows)

            current_chunk_rows.append(row_line)
            current_chunk_char_count += row_len

        if current_chunk_rows:
            chunk_text = columns_line + "\n\n" + "\n".join(current_chunk_rows)
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    "column_names": columns,
                    "row_start": row_start,
                    "row_end": len(row_lines),
                },
            })

        return chunks


class ExcelChunkingStrategy(ChunkingStrategy):
    """
    Chunks multi-sheet Excel files sheet-by-sheet to avoid cross-sheet pollution.
    """

    def chunk(self, text: str, document: Document, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
        sheet_blocks = text.split("\n\n---\n\n")
        chunks = []

        for block in sheet_blocks:
            lines = block.strip().split("\n")
            if not lines:
                continue

            sheet_name = "Unknown"
            columns_line = ""
            columns = []
            row_lines = []

            if lines[0].startswith("Sheet: "):
                sheet_name = lines[0][7:].strip()

            if len(lines) > 1 and lines[1].startswith("Columns: "):
                columns_line = lines[1]
                columns = [col.strip() for col in columns_line[9:].split("|")]

            for line in lines[2:]:
                if line.strip().startswith("Row "):
                    row_lines.append(line.strip())

            if not row_lines:
                # If no rows found, chunk sheet block recursively
                rec = RecursiveChunkingStrategy()
                block_chunks = rec.chunk(block, document, chunk_size, chunk_overlap)
                for bc in block_chunks:
                    bc["metadata"] = {"sheet_name": sheet_name}
                    chunks.append(bc)
                continue

            # Process sheet rows
            current_chunk_rows = []
            header_prefix = f"Sheet: {sheet_name}\n{columns_line}"
            current_chunk_char_count = len(header_prefix) + 2
            row_start = 1

            for idx, row_line in enumerate(row_lines, start=1):
                row_len = len(row_line) + 1
                if current_chunk_rows and current_chunk_char_count + row_len > chunk_size:
                    chunk_text = header_prefix + "\n\n" + "\n".join(current_chunk_rows)
                    chunks.append({
                        "text": chunk_text,
                        "metadata": {
                            "sheet_name": sheet_name,
                            "column_names": columns,
                            "row_start": row_start,
                            "row_end": idx - 1,
                        },
                    })

                    # Respect overlap
                    overlap_rows = []
                    overlap_chars = len(header_prefix) + 2
                    for r in reversed(current_chunk_rows):
                        if overlap_chars + len(r) + 1 <= chunk_overlap:
                            overlap_rows.insert(0, r)
                            overlap_chars += len(r) + 1
                        else:
                            break

                    current_chunk_rows = overlap_rows
                    current_chunk_char_count = overlap_chars
                    row_start = idx - len(overlap_rows)

                current_chunk_rows.append(row_line)
                current_chunk_char_count += row_len

            if current_chunk_rows:
                chunk_text = header_prefix + "\n\n" + "\n".join(current_chunk_rows)
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "sheet_name": sheet_name,
                        "column_names": columns,
                        "row_start": row_start,
                        "row_end": len(row_lines),
                    },
                })

        return chunks


class JSONChunkingStrategy(RecursiveChunkingStrategy):
    """
    Chunks hierarchical JSON representations, maintaining path scopes (e.g. root.users[0].profile).
    """

    def chunk(self, text: str, document: Document, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
        if len(text) <= chunk_size:
            return [{"text": text, "metadata": {"json_path": "root"}}]

        lines = text.split("\n")
        chunks = []
        
        current_chunk_lines = []
        current_chunk_len = 0
        path_stack = []
        chunk_start_path = "root"

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Indentation tracks nesting hierarchy
            leading_spaces = len(line) - len(line.lstrip(" "))
            indent_level = leading_spaces // 2

            while len(path_stack) > indent_level:
                path_stack.pop()

            current_path_segment = None
            if ":" in line_stripped:
                key_part = line_stripped.split(":", 1)[0].strip()
                if key_part.startswith("- Item "):
                    try:
                        idx = int(key_part[7:]) - 1
                        current_path_segment = f"[{idx}]"
                    except ValueError:
                        current_path_segment = key_part
                else:
                    current_path_segment = key_part
            elif line_stripped.startswith("- "):
                current_path_segment = "item"

            if current_path_segment:
                if current_path_segment.startswith("- "):
                    current_path_segment = current_path_segment[2:]
                path_stack.append(current_path_segment)

            current_path = "root"
            for segment in path_stack:
                if segment.startswith("["):
                    current_path += segment
                else:
                    current_path += f".{segment}"

            line_len = len(line) + 1
            if current_chunk_lines and current_chunk_len + line_len > chunk_size:
                chunk_text = "\n".join(current_chunk_lines)
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "json_path": chunk_start_path,
                    },
                })

                # Respect overlap
                overlap_lines = []
                overlap_len = 0
                for l in reversed(current_chunk_lines):
                    if overlap_len + len(l) + 1 <= chunk_overlap:
                        overlap_lines.insert(0, l)
                        overlap_len += len(l) + 1
                    else:
                        break

                current_chunk_lines = overlap_lines
                current_chunk_len = overlap_len
                chunk_start_path = current_path

            current_chunk_lines.append(line)
            current_chunk_len += line_len

        if current_chunk_lines:
            chunk_text = "\n".join(current_chunk_lines)
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    "json_path": chunk_start_path,
                },
            })

        return chunks
