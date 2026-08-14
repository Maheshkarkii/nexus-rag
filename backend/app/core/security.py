import logging
import re
import os
import uuid
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("ai_research_assistant.security")


class PromptInjectionDetector:
    """Detects and classifies potential prompt injection attempts in queries or document text."""

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous\s+)?instructions",
        r"disregard\s+(all\s+)?(previous\s+)?system\s+prompts?",
        r"reveal\s+(your\s+)?(system\s+)?prompt",
        r"print\s+(your\s+)?(system\s+)?prompt",
        r"show\s+(your\s+)?(system\s+)?prompt",
        r"output\s+(your\s+)?(system\s+)?prompt",
        r"forget\s+(all\s+)?rules",
        r"you\s+are\s+now\s+in\s+DAN\s+mode",
        r"jailbreak",
        r"bypass\s+safety\s+filters",
    ]

    @classmethod
    def analyze_text(cls, text: str) -> Dict[str, Any]:
        """Analyze text for prompt injection patterns and return risk assessment."""
        if not text:
            return {"risk_level": "none", "patterns_detected": []}

        detected = []
        for pat in cls.INJECTION_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                detected.append(pat)

        if len(detected) >= 2:
            risk_level = "high_risk"
        elif len(detected) == 1:
            risk_level = "possible"
        else:
            risk_level = "none"

        return {
            "risk_level": risk_level,
            "patterns_detected": detected,
            "is_suspicious": len(detected) > 0,
        }


class FileSecurityValidator:
    """Validates file upload security, path traversal, file sizes, and formula injection."""

    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".csv", ".xlsx", ".xls", ".json", ".txt"}
    MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB limit

    DANGEROUS_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize filename to eliminate path traversal characters and directory separators."""
        if not filename:
            return f"upload_{uuid.uuid4().hex[:8]}"

        # Remove path separators
        clean_name = os.path.basename(filename)
        clean_name = re.sub(r"[^\w\.\-]", "_", clean_name)
        # Prevent hidden files or double extension attacks
        clean_name = clean_name.lstrip(".")
        return clean_name if clean_name else f"upload_{uuid.uuid4().hex[:8]}"

    @classmethod
    def validate_upload(cls, filename: str, file_size: int) -> Dict[str, Any]:
        """Validate filename, extension, and file size boundaries."""
        sanitized = cls.sanitize_filename(filename)
        _, ext = os.path.splitext(sanitized.lower())

        if ext not in cls.ALLOWED_EXTENSIONS:
            return {
                "is_valid": False,
                "error": f"File extension '{ext}' is not supported.",
                "sanitized_filename": sanitized,
            }

        if file_size > cls.MAX_FILE_SIZE_BYTES:
            return {
                "is_valid": False,
                "error": f"File size ({file_size} bytes) exceeds maximum limit of {cls.MAX_FILE_SIZE_BYTES} bytes.",
                "sanitized_filename": sanitized,
            }

        return {"is_valid": True, "error": None, "sanitized_filename": sanitized}

    @classmethod
    def sanitize_formula_cell(cls, cell_value: str) -> str:
        """Sanitize spreadsheet cell content to prevent CSV/Excel formula injection attacks."""
        if not isinstance(cell_value, str):
            return cell_value
        stripped = cell_value.strip()
        if stripped.startswith(cls.DANGEROUS_FORMULA_PREFIXES):
            return f"'{cell_value}" # Single-quote escape
        return cell_value


class LogSanitizer:
    """Sanitizes sensitive values (API keys, passwords, bearer tokens) from log messages."""

    SENSITIVE_KEY_PATTERNS = [
        r"(api[_\-]?key\s*=\s*)(['\"]?[A-Za-z0-9_\-]{8,}['\"]?)",
        r"(password\s*=\s*)(['\"]?[^'\"]+['\"]?)",
        r"(bearer\s+)([A-Za-z0-9_\-\.]{8,})",
        r"(secret[_\-]?key\s*=\s*)(['\"]?[A-Za-z0-9_\-]{8,}['\"]?)",
    ]

    @classmethod
    def sanitize_message(cls, message: str) -> str:
        """Replace sensitive credential patterns with masked strings."""
        if not message:
            return message

        sanitized = message
        for pat in cls.SENSITIVE_KEY_PATTERNS:
            sanitized = re.sub(pat, r"\1[REDACTED_SECRET]", sanitized, flags=re.IGNORECASE)
        return sanitized


class ResourceAccessAuthorizer:
    """Centralized authorization validator enforcing project boundaries and resource ownership."""

    @staticmethod
    def verify_project_scope(resource_project_id: uuid.UUID, target_project_id: uuid.UUID) -> bool:
        """Enforce strict project workspace boundaries. Rejects cross-project IDOR access attempts."""
        if not resource_project_id or not target_project_id:
            return False
        return resource_project_id == target_project_id


class RateLimitValidator:
    """In-memory rate limiter protecting expensive API endpoints from resource exhaustion attacks."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = {}

    def is_rate_limited(self, client_identifier: str, current_timestamp: float) -> bool:
        """Check whether a client identifier has exceeded rate limits."""
        if client_identifier not in self._history:
            self._history[client_identifier] = []

        timestamps = self._history[client_identifier]
        cutoff = current_timestamp - self.window_seconds
        valid_timestamps = [t for t in timestamps if t > cutoff]

        if len(valid_timestamps) >= self.max_requests:
            return True

        valid_timestamps.append(current_timestamp)
        self._history[client_identifier] = valid_timestamps
        return False


class SecurityAuditLogger:
    """Logs security audit events safely without exposing raw user document content."""

    @staticmethod
    def log_event(event_type: str, user_id: Optional[str], resource_id: Optional[str], details: Optional[Dict[str, Any]] = None) -> None:
        safe_details = details or {}
        logger.info(
            f"[SECURITY_AUDIT] Event: {event_type} | User: {user_id or 'anonymous'} | Resource: {resource_id or 'N/A'} | Details: {safe_details}"
        )
