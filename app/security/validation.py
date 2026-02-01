"""
Input Validation and Sanitization

Provides security utilities for validating file paths, filenames,
and other user-provided inputs.
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional, Set

logger = logging.getLogger(__name__)

# File extensions considered safe for certain operations
ALLOWED_EXTENSIONS: Set[str] = {
    # Documents
    ".txt", ".md", ".json", ".yaml", ".yml", ".xml", ".csv", ".toml",
    # Code
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".sql",
    ".java", ".go", ".rs", ".rb", ".php", ".sh", ".bash",
    # Config
    ".env.example", ".gitignore", ".dockerignore",
    # Data
    ".log",
}

# Patterns that indicate path traversal or injection attempts
DANGEROUS_PATTERNS = [
    "..",           # Parent directory traversal
    "~",            # Home directory expansion
    "$",            # Environment variable expansion
    "`",            # Command substitution
    "$(", ")",      # Command substitution
    "\\",           # Backslash (Windows path / escape)
    "\x00",         # Null byte injection
    "%00",          # URL-encoded null byte
    "%2e%2e",       # URL-encoded ..
    "%252e",        # Double-encoded .
    "....//",       # Multiple traversal
    "..../",        # Multiple traversal
]

# Disallowed path prefixes (sensitive directories)
SENSITIVE_PATHS = [
    "/etc",
    "/root",
    "/home",
    "/var/log",
    "/proc",
    "/sys",
    "/dev",
    "~",
    os.path.expanduser("~"),
]


def normalize_path(path: str, base_dir: Optional[str] = None) -> Optional[str]:
    """
    Normalize and resolve a path.

    Args:
        path: The path to normalize
        base_dir: Optional base directory to resolve relative paths against

    Returns:
        Normalized absolute path, or None if path is invalid/dangerous
    """
    if not path:
        return None

    # Check for dangerous patterns first
    path_lower = path.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in path_lower or pattern in path:
            logger.warning(f"Dangerous pattern '{pattern}' found in path: {path}")
            return None

    try:
        # Resolve the path
        if base_dir:
            resolved = Path(base_dir) / path
        else:
            resolved = Path(path)

        # Resolve to absolute path (handles ..)
        resolved = resolved.resolve()

        # Convert to string
        return str(resolved)

    except (ValueError, OSError) as e:
        logger.warning(f"Invalid path '{path}': {e}")
        return None


def is_path_safe(
    path: str,
    allowed_base: Optional[str] = None,
    allow_sensitive: bool = False,
) -> bool:
    """
    Check if a path is safe to access.

    Args:
        path: The path to check
        allowed_base: If provided, path must be under this directory
        allow_sensitive: If False, blocks access to sensitive directories

    Returns:
        True if the path is safe to access
    """
    if not path:
        return False

    # Normalize the path
    normalized = normalize_path(path, allowed_base)
    if normalized is None:
        return False

    # Check if within allowed base directory
    if allowed_base:
        try:
            base_resolved = Path(allowed_base).resolve()
            target_path = Path(normalized).resolve()
            if hasattr(target_path, "is_relative_to"):
                if not target_path.is_relative_to(base_resolved):
                    logger.warning(
                        f"Path traversal attempt: '{path}' escapes base '{allowed_base}'"
                    )
                    return False
            else:
                common = os.path.commonpath([str(base_resolved), str(target_path)])
                if common != str(base_resolved):
                    logger.warning(
                        f"Path traversal attempt: '{path}' escapes base '{allowed_base}'"
                    )
                    return False
        except Exception as e:
            logger.warning(f"Failed to resolve allowed base '{allowed_base}': {e}")
            return False

    # Check for sensitive paths
    if not allow_sensitive:
        for sensitive in SENSITIVE_PATHS:
            try:
                sensitive_resolved = Path(sensitive).expanduser().resolve()
                target_path = Path(normalized).resolve()
                if hasattr(target_path, "is_relative_to"):
                    if target_path.is_relative_to(sensitive_resolved):
                        logger.warning(f"Access to sensitive path blocked: {path}")
                        return False
                else:
                    common = os.path.commonpath([str(sensitive_resolved), str(target_path)])
                    if common == str(sensitive_resolved):
                        logger.warning(f"Access to sensitive path blocked: {path}")
                        return False
            except Exception:
                continue

    return True


def validate_path(
    path: str,
    allowed_base: Optional[str] = None,
    must_exist: bool = False,
    must_be_file: bool = False,
    must_be_directory: bool = False,
) -> Optional[str]:
    """
    Validate and normalize a path for safe access.

    Args:
        path: The path to validate
        allowed_base: If provided, path must be under this directory
        must_exist: If True, path must exist on filesystem
        must_be_file: If True, path must be a file
        must_be_directory: If True, path must be a directory

    Returns:
        Normalized path if valid, None otherwise
    """
    # Check safety first
    if not is_path_safe(path, allowed_base):
        return None

    # Normalize
    normalized = normalize_path(path, allowed_base)
    if normalized is None:
        return None

    # Check existence requirements
    path_obj = Path(normalized)

    if must_exist and not path_obj.exists():
        logger.warning(f"Path does not exist: {path}")
        return None

    if must_be_file and path_obj.exists() and not path_obj.is_file():
        logger.warning(f"Path is not a file: {path}")
        return None

    if must_be_directory and path_obj.exists() and not path_obj.is_dir():
        logger.warning(f"Path is not a directory: {path}")
        return None

    return normalized


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename for safe filesystem use.

    Removes/replaces dangerous characters and patterns.

    Args:
        filename: The filename to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized filename
    """
    if not filename:
        return "unnamed"

    # Remove path separators
    filename = filename.replace("/", "_").replace("\\", "_")

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Remove other dangerous characters
    filename = re.sub(r'[<>:"|?*]', "_", filename)

    # Remove leading/trailing dots and spaces
    filename = filename.strip(". ")

    # Replace multiple underscores
    filename = re.sub(r"_+", "_", filename)

    # Truncate if too long
    if len(filename) > max_length:
        # Preserve extension
        name, ext = os.path.splitext(filename)
        max_name_len = max_length - len(ext)
        filename = name[:max_name_len] + ext

    # Ensure we have a valid filename
    if not filename or filename in (".", ".."):
        return "unnamed"

    return filename


def is_safe_url(url: str) -> bool:
    """
    Check if a URL is safe to access.

    Blocks file://, javascript:, and other dangerous schemes.

    Args:
        url: The URL to check

    Returns:
        True if the URL is safe
    """
    if not url:
        return False

    url_lower = url.lower().strip()

    # Allowed schemes
    allowed_schemes = ("http://", "https://")
    if not any(url_lower.startswith(scheme) for scheme in allowed_schemes):
        logger.warning(f"Blocked URL with unsafe scheme: {url}")
        return False

    # Block internal IPs (SSRF protection)
    internal_patterns = [
        "localhost", "127.0.0.1", "0.0.0.0",
        "169.254.", "10.", "192.168.", "172.16.",
        "172.17.", "172.18.", "172.19.", "172.20.",
        "172.21.", "172.22.", "172.23.", "172.24.",
        "172.25.", "172.26.", "172.27.", "172.28.",
        "172.29.", "172.30.", "172.31.",
        "[::1]", "[::0]",
    ]

    for pattern in internal_patterns:
        if pattern in url_lower:
            logger.warning(f"Blocked internal URL (SSRF protection): {url}")
            return False

    return True
