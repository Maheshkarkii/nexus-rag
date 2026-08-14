"""Text normalization utilities preserving structural research elements like tables and lists."""

import re


def normalize_extracted_text(raw_text: str) -> str:
    """Clean and normalize extracted document text while preserving markdown/table layouts."""
    if not raw_text:
        return ""

    # 1. Normalize line endings (\r\n and \r -> \n)
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Replace null bytes and non-printable control characters except \n and \t
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # 3. Collapse 3+ consecutive newlines into exactly 2 newlines (preserving paragraph boundaries)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 4. Strip excessive trailing whitespace on individual lines
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)

    return text.strip()
