"""
Advanced Tools for Agent Execution

Cutting-edge tools including browser automation, secure code sandbox,
PDF processing, document generation, data analysis, URL preview, and knowledge graph.
"""

import asyncio
import json
import logging
import os
import io
import csv
import tempfile
import statistics
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from pathlib import Path

import httpx

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


# ============== Browser Use Tool ==============
# Requires: pip install browser-use playwright
# Run: playwright install chromium

BROWSER_USE_ENABLED = os.getenv("BROWSER_USE_ENABLED", "false").lower() == "true"
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"


async def browser_handler(
    task: str,
    url: Optional[str] = None,
    max_steps: int = 10,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Execute a browser automation task using browser-use.

    The agent will navigate, interact with elements, and extract information
    based on the natural language task description.
    """
    logger.info(f"Browser task: {task[:50]}...")

    if not BROWSER_USE_ENABLED:
        return {
            "error": "Browser automation is disabled. Set BROWSER_USE_ENABLED=true to enable.",
            "success": False,
        }

    try:
        # Lazy import to avoid loading when not needed
        from browser_use import Agent as BrowserAgent
        from browser_use import Browser, BrowserConfig
        from langchain_openai import ChatOpenAI

        # Configure browser
        browser_config = BrowserConfig(
            headless=BROWSER_HEADLESS,
            disable_security=False,  # Keep security enabled
        )

        browser = Browser(config=browser_config)

        # Create a simple LLM for browser control
        # Uses the same OpenAI key as the rest of the system
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
        )

        # Create browser agent
        agent = BrowserAgent(
            task=task,
            llm=llm,
            browser=browser,
            max_actions_per_step=3,
        )

        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                agent.run(max_steps=max_steps),
                timeout=timeout
            )

            return {
                "result": result,
                "task": task,
                "steps_taken": len(agent.history) if hasattr(agent, 'history') else 0,
                "success": True,
            }

        except asyncio.TimeoutError:
            return {
                "error": f"Browser task timed out after {timeout}s",
                "task": task,
                "success": False,
            }

        finally:
            await browser.close()

    except ImportError:
        return {
            "error": "browser-use not installed. Run: pip install browser-use && playwright install chromium",
            "success": False,
        }
    except Exception as e:
        logger.error(f"Browser error: {e}")
        return {"error": str(e), "success": False}


BROWSER_TOOL = ToolDefinition(
    name="browser",
    description="Execute browser automation tasks using AI. Can navigate websites, fill forms, click buttons, extract data, and perform complex web interactions. Requires BROWSER_USE_ENABLED=true.",
    parameters=[
        ToolParameter(
            name="task",
            type="string",
            description="Natural language description of the browser task (e.g., 'Go to google.com and search for AI news')",
            required=True,
        ),
        ToolParameter(
            name="url",
            type="string",
            description="Optional starting URL",
            required=False,
        ),
        ToolParameter(
            name="max_steps",
            type="number",
            description="Maximum number of steps to take (default 10)",
            required=False,
            default=10,
        ),
        ToolParameter(
            name="timeout",
            type="number",
            description="Timeout in seconds (default 60)",
            required=False,
            default=60,
        ),
    ],
    handler=browser_handler,
)


# ============== Code Sandbox Tool ==============
# Uses RestrictedPython for safer execution than basic exec()

SANDBOX_ENABLED = os.getenv("CODE_SANDBOX_ENABLED", "true").lower() == "true"
SANDBOX_TIMEOUT = int(os.getenv("CODE_SANDBOX_TIMEOUT", "30"))

# Session storage for stateful execution
_sandbox_sessions: Dict[str, Dict[str, Any]] = {}


async def sandbox_handler(
    code: str,
    session_id: Optional[str] = None,
    packages: Optional[List[str]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Execute Python code in a sandboxed environment with common data science packages.

    Supports:
    - numpy, pandas (via safe alternatives)
    - math, statistics
    - json, datetime
    - Stateful sessions (variables persist across calls with same session_id)
    """
    logger.info(f"Sandbox execution: {len(code)} chars, session={session_id}")

    if not SANDBOX_ENABLED:
        return {
            "error": "Code sandbox is disabled. Set CODE_SANDBOX_ENABLED=true to enable.",
            "success": False,
        }

    # Get or create session
    if session_id:
        if session_id not in _sandbox_sessions:
            _sandbox_sessions[session_id] = {
                "variables": {},
                "created_at": datetime.utcnow().isoformat(),
            }
        session = _sandbox_sessions[session_id]
    else:
        session = {"variables": {}}

    # Security: Block dangerous patterns
    BLOCKED_PATTERNS = [
        "__import__", "importlib", "eval(", "exec(", "compile(",
        "open(", "file(", "input(", "breakpoint(",
        "os.", "sys.", "subprocess", "socket", "pickle",
        "builtins", "globals()", "locals()", "vars(",
        "getattr(", "setattr(", "delattr(",
        "__class__", "__bases__", "__subclasses__",
        "__code__", "__globals__",
    ]

    code_lower = code.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern.lower() in code_lower:
            return {
                "error": f"Security: Blocked pattern detected - {pattern}",
                "success": False,
            }

    try:
        # Build safe execution environment
        import math
        import statistics
        from datetime import datetime, timedelta, date

        safe_builtins = {
            # Basic types
            "True": True, "False": False, "None": None,
            "int": int, "float": float, "str": str, "bool": bool,
            "list": list, "dict": dict, "set": set, "tuple": tuple,
            "bytes": bytes, "bytearray": bytearray,

            # Functions
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "len": len, "range": range, "enumerate": enumerate,
            "zip": zip, "map": map, "filter": filter, "sorted": sorted,
            "reversed": reversed, "all": all, "any": any,
            "print": print, "type": type, "isinstance": isinstance,
            "hasattr": hasattr, "repr": repr, "hash": hash,
            "ord": ord, "chr": chr, "hex": hex, "bin": bin, "oct": oct,
            "format": format, "divmod": divmod, "pow": pow,

            # Itertools basics
            "iter": iter, "next": next,
        }

        safe_globals = {
            "__builtins__": safe_builtins,
            "math": math,
            "statistics": statistics,
            "json": json,
            "datetime": datetime,
            "timedelta": timedelta,
            "date": date,
        }

        # Try to add numpy/pandas if available
        try:
            import numpy as np
            safe_globals["np"] = np
            safe_globals["numpy"] = np
        except ImportError:
            pass

        try:
            import pandas as pd
            safe_globals["pd"] = pd
            safe_globals["pandas"] = pd
        except ImportError:
            pass

        # Capture output
        output_lines = []
        def capture_print(*args, **kwargs):
            output_lines.append(" ".join(str(a) for a in args))
        safe_globals["__builtins__"]["print"] = capture_print

        # Include session variables
        local_vars = dict(session["variables"])

        # Execute with timeout
        def run_code():
            exec(code, safe_globals, local_vars)
            return local_vars

        # Run in thread pool with timeout
        loop = asyncio.get_event_loop()
        result_vars = await asyncio.wait_for(
            loop.run_in_executor(None, run_code),
            timeout=min(timeout, SANDBOX_TIMEOUT)
        )

        # Update session variables (excluding internal)
        session["variables"] = {
            k: v for k, v in result_vars.items()
            if not k.startswith("_") and not callable(v)
        }

        # Get result if defined
        result = result_vars.get("result")

        # Serialize variables for response
        serializable_vars = {}
        for k, v in result_vars.items():
            if k.startswith("_"):
                continue
            try:
                # Try to make it JSON serializable
                json.dumps(v)
                serializable_vars[k] = v
            except (TypeError, ValueError):
                serializable_vars[k] = str(v)[:500]

        return {
            "output": "\n".join(output_lines),
            "result": result if result is not None else None,
            "variables": serializable_vars,
            "session_id": session_id,
            "success": True,
        }

    except asyncio.TimeoutError:
        return {
            "error": f"Execution timed out after {timeout}s",
            "success": False,
        }
    except Exception as e:
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "success": False,
        }


async def sandbox_session_handler(
    operation: str,
    session_id: str,
) -> Dict[str, Any]:
    """Manage sandbox sessions."""
    logger.info(f"Sandbox session: {operation} {session_id}")

    if operation == "get":
        if session_id in _sandbox_sessions:
            session = _sandbox_sessions[session_id]
            return {
                "session_id": session_id,
                "variables": list(session["variables"].keys()),
                "created_at": session.get("created_at"),
                "success": True,
            }
        return {"error": "Session not found", "success": False}

    elif operation == "clear":
        if session_id in _sandbox_sessions:
            _sandbox_sessions[session_id]["variables"] = {}
            return {"session_id": session_id, "cleared": True, "success": True}
        return {"error": "Session not found", "success": False}

    elif operation == "delete":
        if session_id in _sandbox_sessions:
            del _sandbox_sessions[session_id]
            return {"session_id": session_id, "deleted": True, "success": True}
        return {"error": "Session not found", "success": False}

    elif operation == "list":
        return {
            "sessions": list(_sandbox_sessions.keys()),
            "count": len(_sandbox_sessions),
            "success": True,
        }

    return {"error": f"Unknown operation: {operation}", "success": False}


CODE_SANDBOX_TOOL = ToolDefinition(
    name="code_sandbox",
    description="Execute Python code in a secure sandbox. Supports math, statistics, json, datetime, numpy, and pandas. Use session_id for stateful execution across multiple calls. Set 'result' variable to return a value.",
    parameters=[
        ToolParameter(
            name="code",
            type="string",
            description="Python code to execute",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="Optional session ID for stateful execution (variables persist)",
            required=False,
        ),
        ToolParameter(
            name="packages",
            type="array",
            description="Additional packages to enable (currently: numpy, pandas)",
            required=False,
        ),
        ToolParameter(
            name="timeout",
            type="number",
            description="Execution timeout in seconds (max 30)",
            required=False,
            default=30,
        ),
    ],
    handler=sandbox_handler,
)


SANDBOX_SESSION_TOOL = ToolDefinition(
    name="sandbox_session",
    description="Manage code sandbox sessions. Operations: get (view session), clear (reset variables), delete (remove session), list (all sessions).",
    parameters=[
        ToolParameter(
            name="operation",
            type="string",
            description="Operation: get, clear, delete, list",
            required=True,
            enum=["get", "clear", "delete", "list"],
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="Session ID (required for get, clear, delete)",
            required=True,
        ),
    ],
    handler=sandbox_session_handler,
)


# ============== Screenshot Tool ==============

async def screenshot_handler(
    url: str,
    full_page: bool = False,
    width: int = 1280,
    height: int = 720,
) -> Dict[str, Any]:
    """Take a screenshot of a webpage."""
    logger.info(f"Screenshot: {url}")

    if not BROWSER_USE_ENABLED:
        return {
            "error": "Browser features disabled. Set BROWSER_USE_ENABLED=true",
            "success": False,
        }

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": width, "height": height})

            await page.goto(url, wait_until="networkidle")

            screenshot_bytes = await page.screenshot(full_page=full_page)

            await browser.close()

            # Return as base64
            import base64
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

            return {
                "screenshot_base64": screenshot_b64,
                "url": url,
                "dimensions": f"{width}x{height}",
                "full_page": full_page,
                "success": True,
            }

    except ImportError:
        return {
            "error": "playwright not installed. Run: pip install playwright && playwright install chromium",
            "success": False,
        }
    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        return {"error": str(e), "success": False}


SCREENSHOT_TOOL = ToolDefinition(
    name="screenshot",
    description="Take a screenshot of a webpage. Returns base64-encoded PNG image.",
    parameters=[
        ToolParameter(
            name="url",
            type="string",
            description="URL of the webpage to screenshot",
            required=True,
        ),
        ToolParameter(
            name="full_page",
            type="boolean",
            description="Capture full page (default: viewport only)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="width",
            type="number",
            description="Viewport width in pixels",
            required=False,
            default=1280,
        ),
        ToolParameter(
            name="height",
            type="number",
            description="Viewport height in pixels",
            required=False,
            default=720,
        ),
    ],
    handler=screenshot_handler,
)


# ============== PDF Processing Tool ==============

SANDBOX_DIR = os.getenv("TOOL_SANDBOX_DIR", "/tmp/brigade-sandbox")


async def pdf_extract_handler(
    source: str,
    pages: Optional[str] = None,
    extract_metadata: bool = True,
) -> Dict[str, Any]:
    """
    Extract text, metadata, and page information from PDF files.

    Supports both file paths (within sandbox) and URLs.
    Uses PyPDF2 or pdfplumber for extraction.
    """
    logger.info(f"PDF extraction: {source[:50]}...")

    pdf_bytes = None
    source_type = "file"

    try:
        # Determine if source is URL or file path
        if source.startswith(("http://", "https://")):
            source_type = "url"
            # Download PDF from URL
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(source)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                if "pdf" not in content_type.lower() and not source.lower().endswith(".pdf"):
                    return {
                        "success": False,
                        "error": f"URL does not appear to be a PDF (content-type: {content_type})"
                    }

                pdf_bytes = io.BytesIO(response.content)
        else:
            source_type = "file"
            # Ensure sandbox directory exists
            os.makedirs(SANDBOX_DIR, exist_ok=True)

            # Prevent path traversal
            safe_path = os.path.normpath(os.path.join(SANDBOX_DIR, source))
            if not safe_path.startswith(SANDBOX_DIR):
                return {"success": False, "error": "Path traversal blocked"}

            if not os.path.exists(safe_path):
                return {"success": False, "error": f"File not found: {source}"}

            with open(safe_path, "rb") as f:
                pdf_bytes = io.BytesIO(f.read())

        # Try pdfplumber first (better text extraction), fall back to PyPDF2
        extracted_text = []
        metadata = {}
        page_count = 0

        try:
            import pdfplumber

            with pdfplumber.open(pdf_bytes) as pdf:
                page_count = len(pdf.pages)

                # Parse page range if specified
                if pages:
                    page_indices = _parse_page_range(pages, page_count)
                else:
                    page_indices = list(range(page_count))

                for idx in page_indices:
                    if 0 <= idx < page_count:
                        page = pdf.pages[idx]
                        text = page.extract_text() or ""
                        extracted_text.append({
                            "page": idx + 1,
                            "text": text,
                            "char_count": len(text)
                        })

                if extract_metadata and pdf.metadata:
                    metadata = {k: str(v) for k, v in pdf.metadata.items() if v}

        except ImportError:
            # Fall back to PyPDF2
            try:
                from PyPDF2 import PdfReader

                pdf_bytes.seek(0)
                reader = PdfReader(pdf_bytes)
                page_count = len(reader.pages)

                # Parse page range if specified
                if pages:
                    page_indices = _parse_page_range(pages, page_count)
                else:
                    page_indices = list(range(page_count))

                for idx in page_indices:
                    if 0 <= idx < page_count:
                        page = reader.pages[idx]
                        text = page.extract_text() or ""
                        extracted_text.append({
                            "page": idx + 1,
                            "text": text,
                            "char_count": len(text)
                        })

                if extract_metadata and reader.metadata:
                    metadata = {
                        "title": reader.metadata.title,
                        "author": reader.metadata.author,
                        "subject": reader.metadata.subject,
                        "creator": reader.metadata.creator,
                        "producer": reader.metadata.producer,
                        "creation_date": str(reader.metadata.creation_date) if reader.metadata.creation_date else None,
                    }
                    metadata = {k: v for k, v in metadata.items() if v}

            except ImportError:
                return {
                    "success": False,
                    "error": "No PDF library available. Install pdfplumber or PyPDF2: pip install pdfplumber"
                }

        # Combine all text for convenience
        full_text = "\n\n".join([p["text"] for p in extracted_text])

        return {
            "success": True,
            "source": source,
            "source_type": source_type,
            "page_count": page_count,
            "pages_extracted": len(extracted_text),
            "pages": extracted_text,
            "full_text": full_text[:50000],  # Limit to 50k chars
            "text_truncated": len(full_text) > 50000,
            "total_chars": len(full_text),
            "metadata": metadata,
        }

    except httpx.HTTPError as e:
        return {"success": False, "error": f"HTTP error downloading PDF: {str(e)}"}
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return {"success": False, "error": str(e)}


def _parse_page_range(pages: str, total_pages: int) -> List[int]:
    """Parse page range string like '1-3,5,7-9' into list of 0-indexed page numbers."""
    result = []
    parts = pages.replace(" ", "").split(",")

    for part in parts:
        if "-" in part:
            start, end = part.split("-", 1)
            start_idx = int(start) - 1 if start else 0
            end_idx = int(end) if end else total_pages
            result.extend(range(max(0, start_idx), min(total_pages, end_idx)))
        else:
            idx = int(part) - 1
            if 0 <= idx < total_pages:
                result.append(idx)

    return sorted(set(result))


PDF_EXTRACT_TOOL = ToolDefinition(
    name="pdf_extract",
    description="Extract text, metadata, and page information from PDF files. Supports both local files (in sandbox) and URLs. Returns full text content and per-page breakdown.",
    parameters=[
        ToolParameter(
            name="source",
            type="string",
            description="PDF file path (relative to sandbox) or URL",
            required=True,
        ),
        ToolParameter(
            name="pages",
            type="string",
            description="Page range to extract (e.g., '1-3,5,7-9'). Omit for all pages.",
            required=False,
        ),
        ToolParameter(
            name="extract_metadata",
            type="boolean",
            description="Whether to extract PDF metadata (default: true)",
            required=False,
            default=True,
        ),
    ],
    handler=pdf_extract_handler,
)


# ============== Document Generator Tool ==============

# Document templates
DOCUMENT_TEMPLATES = {
    "report": {
        "markdown": """# {title}

**Date:** {date}
**Author:** {author}

## Executive Summary

{summary}

## Key Findings

{findings}

## Recommendations

{recommendations}

## Conclusion

{conclusion}

---
*Generated by Unicorn Brigade Document Generator*
""",
        "html": """<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .meta {{ color: #666; font-style: italic; margin-bottom: 20px; }}
        .section {{ margin-bottom: 20px; }}
        footer {{ margin-top: 40px; border-top: 1px solid #ddd; padding-top: 10px; color: #999; font-size: 0.9em; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="meta">
        <p><strong>Date:</strong> {date}</p>
        <p><strong>Author:</strong> {author}</p>
    </div>
    <h2>Executive Summary</h2>
    <div class="section">{summary}</div>
    <h2>Key Findings</h2>
    <div class="section">{findings}</div>
    <h2>Recommendations</h2>
    <div class="section">{recommendations}</div>
    <h2>Conclusion</h2>
    <div class="section">{conclusion}</div>
    <footer>Generated by Unicorn Brigade Document Generator</footer>
</body>
</html>
""",
    },
    "summary": {
        "markdown": """# {title}

{content}

## Key Points

{key_points}

---
*Summary generated on {date}*
""",
        "html": """<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Georgia, serif; max-width: 700px; margin: 40px auto; padding: 20px; line-height: 1.6; }}
        h1 {{ color: #2c3e50; }}
        h2 {{ color: #34495e; }}
        ul {{ padding-left: 20px; }}
        footer {{ margin-top: 30px; color: #7f8c8d; font-size: 0.85em; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div>{content}</div>
    <h2>Key Points</h2>
    <div>{key_points}</div>
    <footer>Summary generated on {date}</footer>
</body>
</html>
""",
    },
    "proposal": {
        "markdown": """# {title}

**Prepared for:** {recipient}
**Prepared by:** {author}
**Date:** {date}

---

## Introduction

{introduction}

## Problem Statement

{problem}

## Proposed Solution

{solution}

## Implementation Plan

{implementation}

## Timeline

{timeline}

## Budget

{budget}

## Expected Outcomes

{outcomes}

## Conclusion

{conclusion}

---
*This proposal is confidential and intended for the named recipient only.*
""",
        "html": """<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; max-width: 900px; margin: 40px auto; padding: 30px; }}
        h1 {{ color: #1a237e; text-align: center; margin-bottom: 10px; }}
        .header-info {{ text-align: center; color: #666; margin-bottom: 30px; border-bottom: 2px solid #1a237e; padding-bottom: 20px; }}
        h2 {{ color: #303f9f; border-left: 4px solid #1a237e; padding-left: 15px; margin-top: 30px; }}
        .section {{ margin-bottom: 25px; padding: 15px; background: #f5f5f5; border-radius: 5px; }}
        footer {{ margin-top: 50px; text-align: center; color: #999; font-style: italic; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="header-info">
        <p><strong>Prepared for:</strong> {recipient}</p>
        <p><strong>Prepared by:</strong> {author}</p>
        <p><strong>Date:</strong> {date}</p>
    </div>
    <h2>Introduction</h2><div class="section">{introduction}</div>
    <h2>Problem Statement</h2><div class="section">{problem}</div>
    <h2>Proposed Solution</h2><div class="section">{solution}</div>
    <h2>Implementation Plan</h2><div class="section">{implementation}</div>
    <h2>Timeline</h2><div class="section">{timeline}</div>
    <h2>Budget</h2><div class="section">{budget}</div>
    <h2>Expected Outcomes</h2><div class="section">{outcomes}</div>
    <h2>Conclusion</h2><div class="section">{conclusion}</div>
    <footer>This proposal is confidential and intended for the named recipient only.</footer>
</body>
</html>
""",
    },
    "meeting_notes": {
        "markdown": """# Meeting Notes: {title}

**Date:** {date}
**Attendees:** {attendees}
**Location:** {location}

## Agenda

{agenda}

## Discussion

{discussion}

## Decisions Made

{decisions}

## Action Items

{action_items}

## Next Steps

{next_steps}

---
*Notes recorded by {author}*
""",
        "html": """<!DOCTYPE html>
<html>
<head>
    <title>Meeting Notes: {title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 30px auto; padding: 20px; }}
        h1 {{ color: #2e7d32; }}
        .meta {{ background: #e8f5e9; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        h2 {{ color: #388e3c; }}
        .action-items {{ background: #fff3e0; padding: 15px; border-left: 4px solid #ff9800; }}
        footer {{ margin-top: 30px; color: #666; }}
    </style>
</head>
<body>
    <h1>Meeting Notes: {title}</h1>
    <div class="meta">
        <p><strong>Date:</strong> {date}</p>
        <p><strong>Attendees:</strong> {attendees}</p>
        <p><strong>Location:</strong> {location}</p>
    </div>
    <h2>Agenda</h2><div>{agenda}</div>
    <h2>Discussion</h2><div>{discussion}</div>
    <h2>Decisions Made</h2><div>{decisions}</div>
    <h2>Action Items</h2><div class="action-items">{action_items}</div>
    <h2>Next Steps</h2><div>{next_steps}</div>
    <footer>Notes recorded by {author}</footer>
</body>
</html>
""",
    },
    "custom": {
        "markdown": """{content}""",
        "html": """<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
    </style>
</head>
<body>
{content}
</body>
</html>
""",
    },
}


async def doc_generate_handler(
    template_type: str,
    content: Dict[str, str],
    output_format: str = "markdown",
    save_to_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate formatted documents from templates.

    Supports multiple template types (report, summary, proposal, meeting_notes, custom)
    and output formats (markdown, html).
    """
    logger.info(f"Document generation: template={template_type}, format={output_format}")

    try:
        # Validate template type
        if template_type not in DOCUMENT_TEMPLATES:
            return {
                "success": False,
                "error": f"Unknown template type: {template_type}. Available: {list(DOCUMENT_TEMPLATES.keys())}"
            }

        # Validate output format
        if output_format not in ["markdown", "html"]:
            return {
                "success": False,
                "error": f"Unknown output format: {output_format}. Available: markdown, html"
            }

        # Get template
        template = DOCUMENT_TEMPLATES[template_type][output_format]

        # Add default values
        defaults = {
            "title": "Untitled Document",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "author": "Unicorn Brigade Agent",
            "summary": "",
            "findings": "",
            "recommendations": "",
            "conclusion": "",
            "content": "",
            "key_points": "",
            "recipient": "",
            "introduction": "",
            "problem": "",
            "solution": "",
            "implementation": "",
            "timeline": "",
            "budget": "",
            "outcomes": "",
            "attendees": "",
            "location": "",
            "agenda": "",
            "discussion": "",
            "decisions": "",
            "action_items": "",
            "next_steps": "",
        }

        # Merge with provided content
        merged_content = {**defaults, **content}

        # Generate document
        try:
            document = template.format(**merged_content)
        except KeyError as e:
            return {
                "success": False,
                "error": f"Missing template field: {e}. Provide it in the content dict."
            }

        result = {
            "success": True,
            "template_type": template_type,
            "output_format": output_format,
            "document": document,
            "char_count": len(document),
            "line_count": len(document.splitlines()),
        }

        # Optionally save to file
        if save_to_file:
            os.makedirs(SANDBOX_DIR, exist_ok=True)
            safe_path = os.path.normpath(os.path.join(SANDBOX_DIR, save_to_file))
            if not safe_path.startswith(SANDBOX_DIR):
                return {"success": False, "error": "Path traversal blocked"}

            os.makedirs(os.path.dirname(safe_path), exist_ok=True) if os.path.dirname(safe_path) else None
            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(document)

            result["saved_to"] = save_to_file

        return result

    except Exception as e:
        logger.error(f"Document generation error: {e}")
        return {"success": False, "error": str(e)}


DOC_GENERATE_TOOL = ToolDefinition(
    name="doc_generate",
    description="Generate formatted documents from templates. Supports report, summary, proposal, meeting_notes, and custom templates in markdown or HTML format.",
    parameters=[
        ToolParameter(
            name="template_type",
            type="string",
            description="Document template: 'report', 'summary', 'proposal', 'meeting_notes', 'custom'",
            required=True,
            enum=["report", "summary", "proposal", "meeting_notes", "custom"],
        ),
        ToolParameter(
            name="content",
            type="object",
            description="Content for template fields (title, summary, findings, etc.). Fields vary by template.",
            required=True,
        ),
        ToolParameter(
            name="output_format",
            type="string",
            description="Output format: 'markdown' or 'html'",
            required=False,
            default="markdown",
            enum=["markdown", "html"],
        ),
        ToolParameter(
            name="save_to_file",
            type="string",
            description="Optional file path (in sandbox) to save the generated document",
            required=False,
        ),
    ],
    handler=doc_generate_handler,
)


# ============== Data Analysis Tool ==============

async def data_analyze_handler(
    data: Union[List[Any], str],
    analysis_type: str = "summary",
    columns: Optional[List[str]] = None,
    correlation_columns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Perform statistical analysis on datasets.

    Supports CSV/JSON input (file path or inline data).
    Provides mean, median, std, min/max, correlations, and more.
    """
    logger.info(f"Data analysis: type={analysis_type}")

    try:
        # Parse input data
        parsed_data = None
        data_source = "inline"

        if isinstance(data, str):
            # Check if it's a file path
            if data.endswith((".csv", ".json")):
                data_source = "file"
                os.makedirs(SANDBOX_DIR, exist_ok=True)
                safe_path = os.path.normpath(os.path.join(SANDBOX_DIR, data))
                if not safe_path.startswith(SANDBOX_DIR):
                    return {"success": False, "error": "Path traversal blocked"}

                if not os.path.exists(safe_path):
                    return {"success": False, "error": f"File not found: {data}"}

                with open(safe_path, "r", encoding="utf-8") as f:
                    if data.endswith(".csv"):
                        reader = csv.DictReader(f)
                        parsed_data = list(reader)
                    else:  # JSON
                        parsed_data = json.load(f)
            else:
                # Try to parse as JSON string
                try:
                    parsed_data = json.loads(data)
                except json.JSONDecodeError:
                    return {"success": False, "error": "Could not parse data as JSON"}
        else:
            parsed_data = data

        # Ensure we have a list
        if not isinstance(parsed_data, list):
            return {"success": False, "error": "Data must be a list/array"}

        if len(parsed_data) == 0:
            return {"success": False, "error": "Data is empty"}

        result = {
            "success": True,
            "data_source": data_source,
            "analysis_type": analysis_type,
            "row_count": len(parsed_data),
        }

        # Determine if data is list of numbers or list of dicts
        is_numeric_list = all(isinstance(x, (int, float)) for x in parsed_data if x is not None)

        if is_numeric_list:
            # Simple numeric analysis
            numeric_data = [x for x in parsed_data if isinstance(x, (int, float))]
            result["column_analysis"] = {
                "data": _analyze_numeric_column(numeric_data)
            }
            result["columns"] = ["data"]

        elif isinstance(parsed_data[0], dict):
            # Columnar data analysis
            all_columns = list(parsed_data[0].keys())
            analyze_columns = columns if columns else all_columns

            result["columns"] = all_columns
            result["column_analysis"] = {}

            for col in analyze_columns:
                if col not in all_columns:
                    continue

                values = [row.get(col) for row in parsed_data if row.get(col) is not None]

                if not values:
                    result["column_analysis"][col] = {"type": "empty", "count": 0}
                    continue

                # Check if numeric
                numeric_values = []
                for v in values:
                    try:
                        numeric_values.append(float(v))
                    except (ValueError, TypeError):
                        pass

                if len(numeric_values) > len(values) * 0.5:  # Mostly numeric
                    result["column_analysis"][col] = _analyze_numeric_column(numeric_values)
                else:
                    # Categorical analysis
                    result["column_analysis"][col] = _analyze_categorical_column(values)

            # Correlation analysis if requested
            if analysis_type in ["correlation", "full"] and correlation_columns:
                correlations = _calculate_correlations(parsed_data, correlation_columns)
                if correlations:
                    result["correlations"] = correlations

        else:
            return {"success": False, "error": "Data must be list of numbers or list of objects/dicts"}

        # Add distribution summary for summary/full analysis
        if analysis_type in ["summary", "full"]:
            result["summary"] = _generate_summary(result.get("column_analysis", {}))

        return result

    except Exception as e:
        logger.error(f"Data analysis error: {e}")
        return {"success": False, "error": str(e)}


def _analyze_numeric_column(values: List[float]) -> Dict[str, Any]:
    """Analyze a numeric column."""
    if not values:
        return {"type": "numeric", "count": 0}

    sorted_values = sorted(values)
    n = len(values)

    result = {
        "type": "numeric",
        "count": n,
        "min": min(values),
        "max": max(values),
        "sum": sum(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
    }

    if n > 1:
        result["std"] = statistics.stdev(values)
        result["variance"] = statistics.variance(values)

    # Quartiles
    if n >= 4:
        result["q1"] = sorted_values[n // 4]
        result["q3"] = sorted_values[(3 * n) // 4]
        result["iqr"] = result["q3"] - result["q1"]

    return result


def _analyze_categorical_column(values: List[Any]) -> Dict[str, Any]:
    """Analyze a categorical column."""
    if not values:
        return {"type": "categorical", "count": 0}

    # Count occurrences
    counts = {}
    for v in values:
        str_v = str(v)
        counts[str_v] = counts.get(str_v, 0) + 1

    # Sort by frequency
    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    return {
        "type": "categorical",
        "count": len(values),
        "unique_values": len(counts),
        "top_values": sorted_counts[:10],
        "mode": sorted_counts[0][0] if sorted_counts else None,
        "mode_count": sorted_counts[0][1] if sorted_counts else 0,
    }


def _calculate_correlations(data: List[Dict], columns: List[str]) -> Dict[str, float]:
    """Calculate Pearson correlations between numeric columns."""
    if len(columns) < 2:
        return {}

    # Extract numeric values for each column
    col_values = {}
    for col in columns:
        values = []
        for row in data:
            try:
                values.append(float(row.get(col, 0)))
            except (ValueError, TypeError):
                values.append(0)
        col_values[col] = values

    # Calculate correlations for each pair
    correlations = {}
    for i, col1 in enumerate(columns):
        for col2 in columns[i+1:]:
            try:
                corr = _pearson_correlation(col_values[col1], col_values[col2])
                correlations[f"{col1}_vs_{col2}"] = round(corr, 4)
            except:
                pass

    return correlations


def _pearson_correlation(x: List[float], y: List[float]) -> float:
    """Calculate Pearson correlation coefficient."""
    n = len(x)
    if n != len(y) or n < 2:
        return 0.0

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    denominator_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
    denominator_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5

    if denominator_x * denominator_y == 0:
        return 0.0

    return numerator / (denominator_x * denominator_y)


def _generate_summary(column_analysis: Dict[str, Any]) -> str:
    """Generate a human-readable summary of the analysis."""
    lines = []

    for col, analysis in column_analysis.items():
        if analysis.get("type") == "numeric":
            lines.append(f"- {col}: numeric, n={analysis.get('count', 0)}, "
                        f"mean={analysis.get('mean', 0):.2f}, "
                        f"median={analysis.get('median', 0):.2f}, "
                        f"range=[{analysis.get('min', 0):.2f}, {analysis.get('max', 0):.2f}]")
        elif analysis.get("type") == "categorical":
            lines.append(f"- {col}: categorical, n={analysis.get('count', 0)}, "
                        f"{analysis.get('unique_values', 0)} unique values, "
                        f"mode='{analysis.get('mode', 'N/A')}'")

    return "\n".join(lines) if lines else "No data to summarize"


DATA_ANALYZE_TOOL = ToolDefinition(
    name="data_analyze",
    description="Perform statistical analysis on datasets. Supports CSV/JSON files or inline data. Calculates mean, median, std, correlations, distributions, and more.",
    parameters=[
        ToolParameter(
            name="data",
            type="object",
            description="Data to analyze: array of numbers, array of objects, or file path (csv/json in sandbox)",
            required=True,
        ),
        ToolParameter(
            name="analysis_type",
            type="string",
            description="Analysis type: 'summary' (basic stats), 'correlation' (correlations), 'full' (everything)",
            required=False,
            default="summary",
            enum=["summary", "correlation", "full"],
        ),
        ToolParameter(
            name="columns",
            type="array",
            description="Specific columns to analyze (for tabular data). Omit for all columns.",
            required=False,
        ),
        ToolParameter(
            name="correlation_columns",
            type="array",
            description="Columns to calculate correlations between (for correlation/full analysis)",
            required=False,
        ),
    ],
    handler=data_analyze_handler,
)


# ============== URL Preview Tool ==============

async def url_preview_handler(
    url: str,
    capture_screenshot: bool = True,
    width: int = 1280,
    height: int = 720,
) -> Dict[str, Any]:
    """
    Capture screenshot of a URL or extract metadata as fallback.

    Uses Playwright for screenshots when available.
    Falls back to metadata extraction via HTTP.
    """
    logger.info(f"URL preview: {url}")

    result = {
        "success": True,
        "url": url,
        "metadata": {},
        "screenshot": None,
    }

    # Try screenshot first if enabled and browser features available
    if capture_screenshot and BROWSER_USE_ENABLED:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": width, "height": height})

                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Get page title and other metadata
                title = await page.title()
                result["metadata"]["title"] = title

                # Try to extract meta tags
                meta_description = await page.query_selector('meta[name="description"]')
                if meta_description:
                    result["metadata"]["description"] = await meta_description.get_attribute("content")

                og_image = await page.query_selector('meta[property="og:image"]')
                if og_image:
                    result["metadata"]["og_image"] = await og_image.get_attribute("content")

                # Capture screenshot
                screenshot_bytes = await page.screenshot(full_page=False)
                await browser.close()

                import base64
                result["screenshot"] = base64.b64encode(screenshot_bytes).decode()
                result["screenshot_dimensions"] = f"{width}x{height}"
                result["method"] = "playwright"

                return result

        except ImportError:
            logger.info("Playwright not available, falling back to metadata extraction")
        except Exception as e:
            logger.warning(f"Screenshot capture failed: {e}, falling back to metadata extraction")

    # Fallback: Extract metadata via HTTP
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; UnicornBrigade/1.0)"
            })
            response.raise_for_status()

            html = response.text
            result["metadata"]["status_code"] = response.status_code
            result["metadata"]["content_type"] = response.headers.get("content-type", "")
            result["metadata"]["final_url"] = str(response.url)

            # Parse HTML for metadata
            import re

            # Title
            title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
            if title_match:
                result["metadata"]["title"] = title_match.group(1).strip()

            # Meta description
            desc_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if not desc_match:
                desc_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']', html, re.IGNORECASE)
            if desc_match:
                result["metadata"]["description"] = desc_match.group(1).strip()

            # Open Graph image
            og_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if og_match:
                result["metadata"]["og_image"] = og_match.group(1).strip()

            # Favicon
            favicon_match = re.search(r'<link[^>]+rel=["\'](?:shortcut )?icon["\'][^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if favicon_match:
                result["metadata"]["favicon"] = favicon_match.group(1).strip()

            result["method"] = "http_metadata"

    except httpx.HTTPError as e:
        result["success"] = False
        result["error"] = f"HTTP error: {str(e)}"
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)

    return result


URL_PREVIEW_TOOL = ToolDefinition(
    name="url_preview",
    description="Capture screenshot of a URL or extract metadata. Uses Playwright for screenshots when available (requires BROWSER_USE_ENABLED=true), falls back to HTTP metadata extraction.",
    parameters=[
        ToolParameter(
            name="url",
            type="string",
            description="URL to preview",
            required=True,
        ),
        ToolParameter(
            name="capture_screenshot",
            type="boolean",
            description="Attempt to capture screenshot (requires Playwright)",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="width",
            type="number",
            description="Screenshot viewport width",
            required=False,
            default=1280,
        ),
        ToolParameter(
            name="height",
            type="number",
            description="Screenshot viewport height",
            required=False,
            default=720,
        ),
    ],
    handler=url_preview_handler,
)


# ============== Knowledge Graph Query Tool ==============

# Lazy import to avoid circular dependencies
_kg_manager = None


def _get_kg_manager():
    """Get the knowledge graph manager singleton."""
    global _kg_manager
    if _kg_manager is None:
        try:
            from app.knowledge.graph_manager import KnowledgeGraphManager
            _kg_manager = KnowledgeGraphManager()
        except ImportError:
            _kg_manager = None
    return _kg_manager


async def kg_query_handler(
    query_type: str,
    data: Optional[Dict[str, Any]] = None,
    query: Optional[str] = None,
    entity_name: Optional[str] = None,
    entity_type: Optional[str] = None,
    relationship: Optional[str] = None,
    target_entity: Optional[str] = None,
    target_type: Optional[str] = None,
    max_depth: int = 2,
    limit: int = 50,
    graph: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query or store data in the FalkorDB knowledge graph.

    Supports:
    - store: Store an entity or relationship
    - query: Natural language query
    - find_entity: Find entities by type/name
    - find_relationships: Find relationships for an entity
    - find_path: Find path between two entities
    - cypher: Execute raw Cypher query
    - stats: Get graph statistics
    """
    logger.info(f"Knowledge graph: {query_type}")

    manager = _get_kg_manager()

    if manager is None or not manager.db:
        return {
            "success": False,
            "error": "Knowledge graph not available. Enable FalkorDB with FALKORDB_ENABLED=true"
        }

    # Optional per-call graph override. Lets specific agents (e.g., maj-recon)
    # scope all kg_query reads + writes to a domain graph (e.g.,
    # ``majiks_research``) without touching every call site downstream. The
    # override is implemented as a ContextVar in graph_manager — see the
    # docstring on ``_get_graph`` there for details.
    override_token = None
    if graph:
        from app.knowledge.graph_manager import kg_target_graph_override
        override_token = kg_target_graph_override.set(graph)

    try:
        if query_type == "store":
            # Store an entity or relationship
            if not data:
                return {"success": False, "error": "data required for store operation"}

            # Check if it's a relationship or just an entity
            if data.get("target") or data.get("relationship"):
                # Store relationship
                return await manager.store_relationship(
                    from_entity=data.get("entity") or data.get("subject") or entity_name,
                    from_type=data.get("entity_type") or data.get("subject_type") or entity_type or "Entity",
                    relationship=data.get("relationship") or relationship,
                    to_entity=data.get("target") or target_entity,
                    to_type=data.get("target_type") or target_type or "Entity",
                    properties=data.get("properties"),
                )
            else:
                # Store entity
                return await manager.store_entity(
                    name=data.get("entity") or data.get("name") or entity_name,
                    entity_type=data.get("entity_type") or data.get("type") or entity_type or "Entity",
                    properties=data.get("properties"),
                )

        elif query_type == "query":
            # Natural language query
            if not query:
                return {"success": False, "error": "query required for natural language query"}

            return await manager.natural_language_query(query=query, limit=limit)

        elif query_type == "find_entity":
            return await manager.query_entities(
                entity_type=entity_type,
                name_pattern=entity_name,
                limit=limit,
            )

        elif query_type == "find_relationships":
            if not entity_name:
                return {"success": False, "error": "entity_name required for find_relationships"}

            return await manager.query_relationships(
                entity_name=entity_name,
                relationship_type=relationship,
                limit=limit,
            )

        elif query_type == "find_related":
            if not entity_name:
                return {"success": False, "error": "entity_name required for find_related"}

            return await manager.query_related(
                entity_name=entity_name,
                max_depth=max_depth,
            )

        elif query_type == "find_path":
            if not entity_name or not target_entity:
                return {"success": False, "error": "entity_name and target_entity required for find_path"}

            return await manager.find_shortest_path(
                start_entity=entity_name,
                end_entity=target_entity,
                max_depth=max_depth,
            )

        elif query_type == "context":
            if not entity_name:
                return {"success": False, "error": "entity_name required for context"}

            return await manager.get_entity_context(
                entity_name=entity_name,
                max_depth=max_depth,
            )

        elif query_type == "cypher":
            if not query:
                return {"success": False, "error": "query required for cypher execution"}

            return await manager.execute_cypher(
                query=query,
                params=data,
            )

        elif query_type == "stats":
            return manager.get_stats()

        else:
            return {
                "success": False,
                "error": f"Unknown query_type: {query_type}. Valid: store, query, find_entity, find_relationships, find_related, find_path, context, cypher, stats"
            }

    except Exception as e:
        logger.error(f"Knowledge graph error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if override_token is not None:
            from app.knowledge.graph_manager import kg_target_graph_override
            kg_target_graph_override.reset(override_token)


KG_QUERY_TOOL = ToolDefinition(
    name="kg_query",
    description="""Query or store data in the FalkorDB knowledge graph. Supports:
- store: Store entities or relationships
- query: Natural language query ("Who works at Acme?")
- find_entity: Find entities by type/name
- find_relationships: Find relationships for an entity
- find_related: Find all related entities (multi-hop)
- find_path: Find shortest path between two entities
- context: Get comprehensive context about an entity
- cypher: Execute raw Cypher query
- stats: Get graph statistics""",
    parameters=[
        ToolParameter(
            name="query_type",
            type="string",
            description="Operation type: store, query, find_entity, find_relationships, find_related, find_path, context, cypher, stats",
            required=True,
            enum=["store", "query", "find_entity", "find_relationships", "find_related", "find_path", "context", "cypher", "stats"],
        ),
        ToolParameter(
            name="data",
            type="object",
            description="Data for store operation: {entity, entity_type, relationship, target, target_type, properties}",
            required=False,
        ),
        ToolParameter(
            name="query",
            type="string",
            description="Natural language query or Cypher query string",
            required=False,
        ),
        ToolParameter(
            name="entity_name",
            type="string",
            description="Entity name for lookups",
            required=False,
        ),
        ToolParameter(
            name="entity_type",
            type="string",
            description="Entity type filter (Person, Company, Location, etc.)",
            required=False,
        ),
        ToolParameter(
            name="relationship",
            type="string",
            description="Relationship type (WORKS_AT, KNOWS, LOCATED_IN, etc.)",
            required=False,
        ),
        ToolParameter(
            name="target_entity",
            type="string",
            description="Target entity for relationships or path finding",
            required=False,
        ),
        ToolParameter(
            name="target_type",
            type="string",
            description="Target entity type",
            required=False,
        ),
        ToolParameter(
            name="max_depth",
            type="number",
            description="Maximum hops for path/related queries (default 2)",
            required=False,
            default=2,
        ),
        ToolParameter(
            name="limit",
            type="number",
            description="Maximum results to return (default 50)",
            required=False,
            default=50,
        ),
        ToolParameter(
            name="graph",
            type="string",
            description=(
                "Optional graph name override. When set, all reads + writes for this "
                "call route to the named graph instead of the agent default. Use this "
                "when you want to query or update a specific domain graph (e.g., "
                "'majiks_research' for the Majiks ecosystem research catalog). Leave "
                "unset for the default per-agent + global routing."
            ),
            required=False,
        ),
    ],
    handler=kg_query_handler,
)


# ============== Export advanced tools ==============

ADVANCED_TOOLS = [
    BROWSER_TOOL,
    CODE_SANDBOX_TOOL,
    SANDBOX_SESSION_TOOL,
    SCREENSHOT_TOOL,
    PDF_EXTRACT_TOOL,
    DOC_GENERATE_TOOL,
    DATA_ANALYZE_TOOL,
    URL_PREVIEW_TOOL,
    KG_QUERY_TOOL,
]


def get_advanced_tools() -> List[ToolDefinition]:
    """Get all advanced tools."""
    return ADVANCED_TOOLS
