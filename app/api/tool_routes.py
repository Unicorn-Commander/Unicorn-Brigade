"""
Tool listing and metadata routes.
Exposes the built-in tools in a format the frontend expects.
"""

from fastapi import APIRouter, Depends
from typing import List, Annotated
import logging

from app.llm.builtin_tools import get_default_tools, get_safe_tools
from app.llm.extended_tools import (
    EMAIL_TOOL, FILE_TOOL, CODE_TOOL, TEXT_TOOL, IMAGE_TOOL,
    DATABASE_TOOL, NOTIFY_TOOL, QRCODE_TOOL, AGENTIC_RAG_TOOL
)
from app.llm.advanced_tools import (
    BROWSER_TOOL, CODE_SANDBOX_TOOL, SCREENSHOT_TOOL,
    PDF_EXTRACT_TOOL, DOC_GENERATE_TOOL, DATA_ANALYZE_TOOL,
    URL_PREVIEW_TOOL, KG_QUERY_TOOL
)
from app.auth.middleware import require_api_key, AuthUser

logger = logging.getLogger(__name__)
router = APIRouter()

# Display metadata for each tool
TOOL_META = {
    # Builtin tools (7)
    "web_search": {
        "icon": "🔍",
        "type": "Python",
        "domain": "general",
        "provider": "Built-in",
        "capabilities": ["Real-time web search", "Multi-provider support", "Result filtering"],
    },
    "http_request": {
        "icon": "🌐",
        "type": "Python",
        "domain": "general",
        "provider": "Built-in",
        "capabilities": ["REST API calls", "Multiple HTTP methods", "JSON parsing", "Custom headers"],
    },
    "calculator": {
        "icon": "🧮",
        "type": "Python",
        "domain": "general",
        "provider": "Built-in",
        "capabilities": ["Arithmetic", "Trigonometry", "Scientific functions", "Safe evaluation"],
    },
    "datetime": {
        "icon": "🕐",
        "type": "Python",
        "domain": "general",
        "provider": "Built-in",
        "capabilities": ["Current time", "Timezone conversion", "Date formatting", "Time math"],
    },
    "json": {
        "icon": "📋",
        "type": "Python",
        "domain": "technology",
        "provider": "Built-in",
        "capabilities": ["Parse JSON", "Stringify", "JSONPath access", "Schema validation"],
    },
    "shell": {
        "icon": "💻",
        "type": "Python",
        "domain": "technology",
        "provider": "Built-in",
        "capabilities": ["Shell command execution", "Sandboxed environment", "Timeout support"],
    },
    "memory": {
        "icon": "🧠",
        "type": "Python",
        "domain": "general",
        "provider": "Built-in",
        "capabilities": ["Key-value storage", "Session persistence", "Conversation memory"],
    },
    # Extended tools (9)
    "email": {
        "icon": "📧",
        "type": "Python",
        "domain": "business",
        "provider": "Extended",
        "capabilities": ["Send emails", "Multi-provider", "MS365/Google/Resend/SendGrid", "HTML support"],
    },
    "file": {
        "icon": "📁",
        "type": "Python",
        "domain": "technology",
        "provider": "Extended",
        "capabilities": ["Read files", "Write files", "List directories", "File operations"],
    },
    "code": {
        "icon": "⚙️",
        "type": "Python",
        "domain": "technology",
        "provider": "Extended",
        "capabilities": ["Code execution", "Python/JavaScript", "Safe environment", "Result capture"],
    },
    "text": {
        "icon": "📝",
        "type": "Python",
        "domain": "general",
        "provider": "Extended",
        "capabilities": ["Text manipulation", "Search/replace", "Formatting", "Encoding"],
    },
    "image": {
        "icon": "🖼️",
        "type": "Python",
        "domain": "creative",
        "provider": "Extended",
        "capabilities": ["Image generation", "AI models", "Stable Diffusion", "DALL-E"],
    },
    "database": {
        "icon": "🗄️",
        "type": "Python",
        "domain": "technology",
        "provider": "Extended",
        "capabilities": ["SQL queries", "PostgreSQL/MySQL", "CRUD operations", "Schema access"],
    },
    "notify": {
        "icon": "🔔",
        "type": "Python",
        "domain": "business",
        "provider": "Extended",
        "capabilities": ["Push notifications", "Webhook calls", "Multi-channel", "Event triggers"],
    },
    "qrcode": {
        "icon": "📱",
        "type": "Python",
        "domain": "general",
        "provider": "Extended",
        "capabilities": ["QR code generation", "Custom data", "Image output", "Error correction"],
    },
    "agentic_rag": {
        "icon": "🤖",
        "type": "Python",
        "domain": "ai",
        "provider": "Extended",
        "capabilities": ["RAG pipeline", "Document retrieval", "AI-powered search", "Context injection"],
    },
    # Advanced tools (8)
    "browser": {
        "icon": "🌐",
        "type": "Python",
        "domain": "automation",
        "provider": "Advanced",
        "capabilities": ["Web automation", "Playwright", "AI-driven clicks", "Form filling"],
    },
    "code_sandbox": {
        "icon": "🐳",
        "type": "Python",
        "domain": "technology",
        "provider": "Advanced",
        "capabilities": ["Sandboxed execution", "Docker/E2B", "Multi-language", "Package install"],
    },
    "screenshot": {
        "icon": "📸",
        "type": "Python",
        "domain": "automation",
        "provider": "Advanced",
        "capabilities": ["Webpage capture", "Full page/element", "PNG output", "Headless browser"],
    },
    "pdf_extract": {
        "icon": "📄",
        "type": "Python",
        "domain": "documents",
        "provider": "Advanced",
        "capabilities": ["PDF parsing", "Text extraction", "Table detection", "Layout analysis"],
    },
    "doc_generate": {
        "icon": "📋",
        "type": "Python",
        "domain": "documents",
        "provider": "Advanced",
        "capabilities": ["Document generation", "PDF/DOCX/PPTX", "Template filling", "Export formats"],
    },
    "data_analyze": {
        "icon": "📊",
        "type": "Python",
        "domain": "analytics",
        "provider": "Advanced",
        "capabilities": ["Data analysis", "Pandas/NumPy", "Statistics", "Visualization"],
    },
    "url_preview": {
        "icon": "🔗",
        "type": "Python",
        "domain": "general",
        "provider": "Advanced",
        "capabilities": ["URL metadata", "Open Graph", "Twitter Cards", "Link previews"],
    },
    "kg_query": {
        "icon": "🕸️",
        "type": "Python",
        "domain": "ai",
        "provider": "Advanced",
        "capabilities": ["Knowledge graph", "Cypher queries", "FalkorDB", "Graph relationships"],
    },
}


def _format_tool(tool) -> dict:
    """Format a ToolDefinition for the frontend."""
    meta = TOOL_META.get(tool.name, {})
    return {
        "id": tool.name,
        "name": tool.name.replace("_", " ").title(),
        "description": tool.description,
        "type": meta.get("type", "Python"),
        "domain": meta.get("domain", "general"),
        "icon": meta.get("icon", "🔧"),
        "provider": meta.get("provider", "Built-in"),
        "parameters": [p.name for p in tool.parameters],
        "capabilities": meta.get("capabilities", []),
        "status": "active",
        "schema": tool.to_openai_format(),
    }


@router.get("/tools")
async def list_tools(
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """List all available tools (builtin + extended + advanced)."""
    # Combine all tool types
    all_tools = get_default_tools() + [
        # Extended tools
        EMAIL_TOOL, FILE_TOOL, CODE_TOOL, TEXT_TOOL, IMAGE_TOOL,
        DATABASE_TOOL, NOTIFY_TOOL, QRCODE_TOOL, AGENTIC_RAG_TOOL,
        # Advanced tools
        BROWSER_TOOL, CODE_SANDBOX_TOOL, SCREENSHOT_TOOL,
        PDF_EXTRACT_TOOL, DOC_GENERATE_TOOL, DATA_ANALYZE_TOOL,
        URL_PREVIEW_TOOL, KG_QUERY_TOOL,
    ]
    result = [_format_tool(t) for t in all_tools]
    return {"tools": result, "count": len(result)}


@router.get("/tools/available")
async def list_available_tools(
    permission_level: str = "public",
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """List tools filtered by permission level."""
    tools = get_safe_tools() if permission_level in ("public", "authenticated") else get_default_tools()
    result = [_format_tool(t) for t in tools]
    return {"tools": result, "count": len(result), "permission_level": permission_level}
