"""Main FastAPI application"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os
from dotenv import load_dotenv

from app.api import router
from app.api.routes import init_managers
from app.memory.manager import MemoryManager
from app.graph.workflow import WorkflowManager

# Stores and route modules
from app.stores.model_catalog import ModelCatalog
from app.llm.ops_center_client import OpsCenterLLMClient
from app.api.agent_routes import router as agent_router, init_agent_routes
from app.api.tool_routes import router as tool_router
from app.api.system_routes import router as system_router, init_system_routes
from app.api.builder_routes import router as builder_router, init_builder_routes
from app.api.apikey_routes import router as apikey_router
from app.api.conversation_routes import router as conversation_router
from app.api.mcp_routes import router as mcp_router
from app.api.a2a_routes import router as a2a_router, init_a2a_routes
from app.api.orchestration_routes import router as orchestration_router, init_orchestration_routes
from app.api.voice_routes import router as voice_router, init_voice_routes
from app.api.voice_settings_routes import router as voice_settings_router, init_voice_settings_routes
from app.api.langflow_routes import router as langflow_router, init_langflow_routes
from app.api.slack_routes import router as slack_router, init_slack_routes
from app.api.knowledge_routes import router as knowledge_router, init_knowledge_routes
from app.api.mcp_registry_routes import router as mcp_registry_router
from app.api.user_routes import router as user_router
from app.api.support_routes import router as support_router, init_support_routes
from app.api.github_routes import router as github_router, shutdown_github_routes
from app.api.document_routes import router as document_router
from app.api.calendar_routes import router as calendar_router, init_calendar_routes
from app.api.sales_routes import router as sales_router, init_sales_routes
from app.api.content_routes import router as content_router, init_content_routes
from app.api.finance_routes import router as finance_router, init_finance_routes
from app.api.monitoring_routes import router as monitoring_router, init_monitoring_routes, shutdown_monitoring_routes
from app.api.hierarchical_routes import router as hierarchical_router, init_hierarchical_routes
from app.api.medical_routes import router as medical_router, init_medical_routes, shutdown_medical_routes
from app.api.benchmark_routes import router as benchmark_router
from app.api.ralph_routes import router as ralph_router
from app.api.trace_routes import router as trace_router
from app.workflows.benchmark import init_benchmark_engine
from app.db.database import init_db, close_db
from app.db.init_db import seed_agents
from app.observability import flush as langfuse_flush, shutdown as langfuse_shutdown

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global managers
memory_manager = None
workflow_manager = None
llm_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global memory_manager, workflow_manager, llm_client

    logger.info("Starting Unicorn Brigade...")

    # Initialize memory manager
    memory_manager = MemoryManager()
    logger.info("Memory manager initialized")

    # Initialize workflow manager
    workflow_manager = WorkflowManager(memory_manager)
    logger.info("Workflow manager initialized")

    # Initialize API routes with managers (existing routes)
    init_managers(memory_manager, workflow_manager)
    logger.info("API routes initialized")

    # Initialize model catalog (static, stays in-memory)
    model_catalog = ModelCatalog()
    logger.info(f"Model catalog initialized: {model_catalog.count()} models")

    # Initialize LLM client
    llm_client = OpsCenterLLMClient()
    logger.info("OpsCenterLLMClient initialized")

    # Initialize database and seed agents
    await init_db()
    await seed_agents()
    logger.info("Database initialized and seeded")

    # Inject dependencies into route modules (no more AgentStore)
    init_agent_routes(llm_client)
    init_system_routes(model_catalog, llm_client)
    init_builder_routes(llm_client)
    init_a2a_routes(llm_client)
    init_orchestration_routes(llm_client)
    init_voice_routes()  # Voice routes initialize their own room manager
    init_voice_settings_routes()  # Register voice providers and settings
    init_langflow_routes()  # Langflow visual workflow integration
    init_slack_routes(llm_client)  # Slack webhook handlers
    init_knowledge_routes()  # Knowledge graph browser routes
    init_support_routes(memory_manager, llm_client)  # Customer support agent routes
    init_calendar_routes()  # Calendar and meeting scheduling routes
    init_sales_routes(llm_client, memory_manager)  # Sales outreach multi-agent routes
    init_content_routes(llm_client, memory_manager)  # Content generation routes
    init_finance_routes(memory_manager, llm_client)  # Financial analysis routes

    # Initialize monitoring routes with Slack integration
    try:
        from app.integrations.slack import get_slack_client
        slack_client = get_slack_client()
        init_monitoring_routes(slack_client=slack_client, memory_manager=memory_manager)
    except Exception as e:
        logger.warning(f"Slack client not available for monitoring: {e}")
        init_monitoring_routes(memory_manager=memory_manager)

    # Initialize hierarchical workflow routes (3-tier: Orchestrator → Team Leads → Workers)
    init_hierarchical_routes(llm_client, enable_local_models=True)
    logger.info("Hierarchical workflow routes initialized (8 domains, 40 workers)")

    # Initialize medical AI routes (HuggingFace medical models)
    init_medical_routes()
    logger.info("Medical AI routes initialized (HuggingFace integration)")

    # Initialize benchmark engine for A/B testing workflows
    init_benchmark_engine(llm_client, judge_model="openai/gpt-4o-mini")
    logger.info("Benchmark engine initialized for A/B testing")

    # apikey_routes and conversation_routes use Depends(get_session) directly
    logger.info("All route modules initialized")

    yield

    # Cleanup
    await close_db()
    if llm_client:
        await llm_client.close()
    # Shutdown GitHub routes
    await shutdown_github_routes()
    # Shutdown monitoring routes
    await shutdown_monitoring_routes()
    # Shutdown medical routes
    await shutdown_medical_routes()
    # Flush and shutdown Langfuse observability
    try:
        langfuse_flush()
        langfuse_shutdown()
        logger.info("Langfuse observability shutdown complete")
    except Exception as e:
        logger.warning(f"Error shutting down Langfuse: {e}")
    logger.info("Shutting down Unicorn Brigade...")

# Create FastAPI app
app = FastAPI(
    title=os.getenv("API_TITLE", "Unicorn Brigade API"),
    version=os.getenv("API_VERSION", "1.0.0"),
    description="Multi-Agent Orchestration System with LangGraph and mem0",
    lifespan=lifespan
)

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers — existing router FIRST (has /agents/execute which must match before /agents/{id})
app.include_router(router, prefix="/api/v1", tags=["core"])
app.include_router(agent_router, prefix="/api/v1", tags=["agents"])
app.include_router(tool_router, prefix="/api/v1", tags=["tools"])
app.include_router(system_router, prefix="/api/v1", tags=["system"])
app.include_router(builder_router, prefix="/api/v1", tags=["builder"])
app.include_router(apikey_router, prefix="/api/v1", tags=["api-keys"])
app.include_router(conversation_router, prefix="/api/v1", tags=["conversations"])
app.include_router(mcp_router, prefix="/api/v1", tags=["mcp"])
app.include_router(a2a_router, prefix="/api/v1", tags=["a2a"])
app.include_router(orchestration_router, prefix="/api/v1", tags=["orchestration"])
app.include_router(voice_router, prefix="/api/v1", tags=["voice"])
app.include_router(voice_settings_router, prefix="/api/v1", tags=["voice-settings"])
app.include_router(langflow_router, prefix="/api/v1", tags=["langflow"])
app.include_router(slack_router, prefix="/api/v1", tags=["slack"])
app.include_router(knowledge_router, prefix="/api/v1", tags=["knowledge"])
app.include_router(mcp_registry_router, prefix="/api/v1", tags=["mcp-registry"])
app.include_router(user_router, prefix="/api/v1", tags=["users"])
app.include_router(support_router, prefix="/api/v1", tags=["support"])
app.include_router(github_router, prefix="/api/v1", tags=["github"])
app.include_router(document_router, prefix="/api/v1", tags=["documents"])
app.include_router(calendar_router, prefix="/api/v1", tags=["calendar"])
app.include_router(sales_router, prefix="/api/v1", tags=["sales"])
app.include_router(content_router, prefix="/api/v1", tags=["content"])
app.include_router(finance_router, prefix="/api/v1", tags=["finance"])
app.include_router(monitoring_router, prefix="/api/v1", tags=["monitoring"])
app.include_router(hierarchical_router, prefix="/api/v1", tags=["hierarchical"])
app.include_router(medical_router, prefix="/api/v1", tags=["medical"])
app.include_router(benchmark_router, prefix="/api/v1", tags=["benchmarks"])
app.include_router(trace_router, prefix="/api/v1", tags=["trace"])
app.include_router(ralph_router, tags=["ralph"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Unicorn Brigade API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "health": "/api/v1/health",
            "stats": "/api/v1/stats",
            "agents": "/api/v1/agents",
            "agents_domains": "/api/v1/agents/domains",
            "chat": "/api/v1/agents/{id}/chat",
            "chat_local": "/api/v1/agents/{id}/chat/local",
            "chat_completions": "/api/v1/chat/completions",
            "models": "/api/v1/chat/models",
            "providers": "/api/v1/providers",
            "tools": "/api/v1/tools",
            "execute_task": "/api/v1/agents/execute",
            "execute_stream": "/api/v1/agents/execute/stream",
            "query_memory": "/api/v1/memory/query",
            "conversations": "/api/v1/conversations",
            "docs": "/docs"
        },
        "protocols": {
            "mcp": {
                "info": "/api/v1/mcp/info",
                "tools_list": "/api/v1/mcp/tools/list",
                "tools_call": "/api/v1/mcp/tools/call",
                "config": "/api/v1/mcp/config"
            },
            "a2a": {
                "info": "/api/v1/a2a/info",
                "agents": "/api/v1/a2a/agents",
                "discover": "/api/v1/a2a/discover",
                "invoke": "/api/v1/a2a/agents/{id}/invoke",
                "card": "/api/v1/a2a/agents/{id}/card"
            }
        },
        "voice": {
            "rooms": "/api/v1/voice/rooms",
            "create_room": "POST /api/v1/voice/rooms",
            "get_token": "/api/v1/voice/rooms/{room_id}/token",
            "config": "/api/v1/voice/config",
            "health": "/api/v1/voice/health",
            "settings": "/api/v1/voice/settings",
            "providers": "/api/v1/voice/providers",
            "providers_stt": "/api/v1/voice/providers/stt",
            "providers_tts": "/api/v1/voice/providers/tts",
            "voices": "/api/v1/voice/voices",
            "test_stt": "POST /api/v1/voice/test/stt",
            "test_tts": "POST /api/v1/voice/test/tts"
        },
        "slack": {
            "events": "POST /api/v1/slack/events",
            "interactions": "POST /api/v1/slack/interactions",
            "commands": "POST /api/v1/slack/commands",
            "health": "/api/v1/slack/health",
            "test": "POST /api/v1/slack/test"
        },
        "langflow": {
            "health": "/api/v1/langflow/health",
            "flows": "/api/v1/langflow/flows",
            "flow_detail": "/api/v1/langflow/flows/{id}",
            "run_flow": "POST /api/v1/langflow/flows/{id}/run",
            "import_flow": "POST /api/v1/langflow/flows/import",
            "export_flow": "/api/v1/langflow/flows/{id}/export",
            "convert_to_workflow": "/api/v1/langflow/flows/{id}/convert"
        },
        "knowledge": {
            "entities": "/api/v1/knowledge/entities",
            "relationships": "/api/v1/knowledge/relationships",
            "graph": "/api/v1/knowledge/graph",
            "stats": "/api/v1/knowledge/stats",
            "entity_detail": "/api/v1/knowledge/entity/{name}",
            "search": "/api/v1/knowledge/search",
            "nl_query": "POST /api/v1/knowledge/query",
            "rag_query": "POST /api/v1/knowledge/rag",
            "store_entity": "POST /api/v1/knowledge/store/entity",
            "store_relationship": "POST /api/v1/knowledge/store/relationship",
            "store_fact": "POST /api/v1/knowledge/store/fact",
            "find_path": "POST /api/v1/knowledge/path",
            "entity_context": "/api/v1/knowledge/context/{entity_name}"
        },
        "users": {
            "register": "POST /api/v1/users/register",
            "login": "POST /api/v1/users/login",
            "profile": "/api/v1/users/me",
            "update_profile": "PUT /api/v1/users/me",
            "api_keys": "/api/v1/users/me/api-keys",
            "create_api_key": "POST /api/v1/users/me/api-keys",
            "revoke_api_key": "DELETE /api/v1/users/me/api-keys/{key_id}"
        },
        "support": {
            "create_ticket": "POST /api/v1/support/ticket",
            "send_message": "POST /api/v1/support/message",
            "list_tickets": "/api/v1/support/tickets",
            "get_ticket": "/api/v1/support/ticket/{ticket_id}",
            "update_ticket_status": "PUT /api/v1/support/ticket/{ticket_id}/status",
            "escalate_ticket": "POST /api/v1/support/ticket/{ticket_id}/escalate",
            "add_faq": "POST /api/v1/support/faq",
            "list_faqs": "/api/v1/support/faq",
            "search_faqs": "/api/v1/support/faq/search",
            "status": "/api/v1/support/status"
        },
        "github": {
            "health": "/api/v1/github/health",
            "trigger_review": "POST /api/v1/github/review",
            "list_reviews": "/api/v1/github/reviews",
            "get_review": "/api/v1/github/reviews/{repo}/{pr_number}",
            "webhook": "POST /api/v1/github/webhook"
        },
        "documents": {
            "process": "POST /api/v1/documents/process",
            "extract": "POST /api/v1/documents/extract",
            "templates": "/api/v1/documents/templates",
            "supported_types": "/api/v1/documents/supported-types",
            "analyze": "POST /api/v1/documents/analyze"
        },
        "calendar": {
            "health": "/api/v1/calendar/health",
            "schedule": "POST /api/v1/calendar/schedule",
            "parse": "POST /api/v1/calendar/parse",
            "availability": "/api/v1/calendar/availability",
            "find_slots": "POST /api/v1/calendar/find-slots",
            "reschedule": "POST /api/v1/calendar/reschedule",
            "cancel": "DELETE /api/v1/calendar/meeting/{id}",
            "get_meeting": "/api/v1/calendar/meeting/{id}",
            "list_events": "/api/v1/calendar/events",
            "create_event": "POST /api/v1/calendar/events"
        },
        "sales": {
            "create_campaign": "POST /api/v1/sales/campaign",
            "list_campaigns": "/api/v1/sales/campaigns",
            "get_campaign": "/api/v1/sales/campaigns/{id}",
            "add_leads": "POST /api/v1/sales/leads",
            "list_leads": "/api/v1/sales/leads",
            "get_lead": "/api/v1/sales/leads/{id}",
            "enrich_lead": "POST /api/v1/sales/enrich",
            "personalize": "POST /api/v1/sales/personalize",
            "list_sequences": "/api/v1/sales/sequences",
            "create_sequence": "POST /api/v1/sales/sequences",
            "pending_actions": "/api/v1/sales/sequences/pending",
            "process_reply": "POST /api/v1/sales/reply",
            "book_meeting": "POST /api/v1/sales/meeting",
            "execute_outreach": "POST /api/v1/sales/outreach/execute",
            "stats": "/api/v1/sales/stats",
            "health": "/api/v1/sales/health"
        },
        "content": {
            "generate_blog": "POST /api/v1/content/blog",
            "stream_blog": "POST /api/v1/content/blog/stream",
            "generate_social": "POST /api/v1/content/social",
            "generate_marketing": "POST /api/v1/content/marketing",
            "repurpose_content": "POST /api/v1/content/repurpose",
            "generate_variants": "POST /api/v1/content/variants",
            "list_templates": "/api/v1/content/templates",
            "get_template": "/api/v1/content/templates/{id}",
            "generate_calendar": "POST /api/v1/content/calendar",
            "generate_hashtags": "POST /api/v1/content/hashtags",
            "list_tones": "/api/v1/content/tones",
            "list_formats": "/api/v1/content/formats",
            "list_content_types": "/api/v1/content/content-types",
            "health": "/api/v1/content/health"
        },
        "finance": {
            "record_transaction": "POST /api/v1/finance/transactions",
            "list_transactions": "/api/v1/finance/transactions",
            "get_transaction": "/api/v1/finance/transactions/{id}",
            "spend_analysis": "/api/v1/finance/analysis",
            "forecast": "/api/v1/finance/forecast",
            "cost_cutting": "/api/v1/finance/cost-cutting",
            "set_budget": "POST /api/v1/finance/budget",
            "budget_status": "/api/v1/finance/budget/status",
            "list_budgets": "/api/v1/finance/budgets",
            "get_budget": "/api/v1/finance/budgets/{id}",
            "get_alerts": "/api/v1/finance/alerts",
            "acknowledge_alert": "POST /api/v1/finance/alerts/{id}/acknowledge",
            "generate_report": "/api/v1/finance/report",
            "list_reports": "/api/v1/finance/reports",
            "get_report": "/api/v1/finance/reports/{id}",
            "categories": "/api/v1/finance/categories",
            "currencies": "/api/v1/finance/currencies",
            "transaction_types": "/api/v1/finance/transaction-types",
            "status": "/api/v1/finance/status"
        },
        "monitoring": {
            "health": "/api/v1/monitoring/health",
            "services": "/api/v1/monitoring/services",
            "trigger_check": "POST /api/v1/monitoring/check",
            "register_service": "POST /api/v1/monitoring/services/register",
            "list_service_checks": "/api/v1/monitoring/services/list",
            "check_service": "POST /api/v1/monitoring/services/{name}/check",
            "list_alerts": "/api/v1/monitoring/alerts",
            "get_alert": "/api/v1/monitoring/alerts/{id}",
            "acknowledge_alert": "POST /api/v1/monitoring/alerts/{id}/acknowledge",
            "resolve_alert": "POST /api/v1/monitoring/alerts/{id}/resolve",
            "get_metrics": "/api/v1/monitoring/metrics",
            "record_metric": "POST /api/v1/monitoring/metrics/record",
            "check_anomaly": "POST /api/v1/monitoring/metrics/anomaly",
            "set_threshold": "POST /api/v1/monitoring/thresholds",
            "list_thresholds": "/api/v1/monitoring/thresholds",
            "list_incidents": "/api/v1/monitoring/incidents",
            "create_incident": "POST /api/v1/monitoring/incidents",
            "update_incident": "PUT /api/v1/monitoring/incidents/{id}/status",
            "configure_webhook": "POST /api/v1/monitoring/webhook",
            "list_webhooks": "/api/v1/monitoring/webhooks",
            "analyze_log": "POST /api/v1/monitoring/logs/analyze",
            "error_rates": "/api/v1/monitoring/logs/error-rates",
            "start_scheduled": "POST /api/v1/monitoring/scheduled/start",
            "stop_scheduled": "POST /api/v1/monitoring/scheduled/stop",
            "status": "/api/v1/monitoring/status"
        },
        "hierarchical_workflows": {
            "description": "3-Tier Agent Hierarchy: The General → Team Leads (7B-14B) → Workers (1B-3B)",
            "templates": "/api/v1/hierarchical/templates",
            "template_detail": "/api/v1/hierarchical/templates/{workflow_id}",
            "execute": "POST /api/v1/hierarchical/execute",
            "executions": "/api/v1/hierarchical/executions",
            "execution_detail": "/api/v1/hierarchical/executions/{execution_id}",
            "cancel_execution": "POST /api/v1/hierarchical/executions/{execution_id}/cancel",
            "checkpoint_response": "POST /api/v1/hierarchical/executions/{execution_id}/checkpoint",
            "domains": "/api/v1/hierarchical/domains",
            "domain_detail": "/api/v1/hierarchical/domains/{domain}",
            "domain_execute": "POST /api/v1/hierarchical/domains/{domain}/execute",
            "workers": "/api/v1/hierarchical/workers",
            "worker_detail": "/api/v1/hierarchical/workers/{worker_id}",
            "worker_execute": "POST /api/v1/hierarchical/workers/{worker_id}/execute",
            "models": "/api/v1/hierarchical/models",
            "health": "/api/v1/hierarchical/health"
        },
        "benchmarks": {
            "description": "A/B testing and benchmarking for hierarchical workflows",
            "compare": "POST /api/v1/benchmarks/compare",
            "run_single": "POST /api/v1/benchmarks/run",
            "list_benchmarks": "/api/v1/benchmarks",
            "list_runs": "/api/v1/benchmarks/runs",
            "get_benchmark": "/api/v1/benchmarks/{benchmark_id}",
            "get_run": "/api/v1/benchmarks/runs/{run_id}",
            "leaderboard": "/api/v1/benchmarks/leaderboard",
            "configs": "/api/v1/benchmarks/configs",
            "workflows": "/api/v1/benchmarks/workflows",
            "score_quality": "POST /api/v1/benchmarks/score-quality",
            "health": "/api/v1/benchmarks/health"
        },
        "medical": {
            "description": "Medical AI using HuggingFace models (BioMistral, ClinicalBERT, CheXNet)",
            "health": "/api/v1/medical/health",
            "models": "/api/v1/medical/models",
            "extract_entities": "POST /api/v1/medical/extract-entities",
            "analyze_image": "POST /api/v1/medical/analyze-image",
            "summarize": "POST /api/v1/medical/summarize",
            "drug_interactions": "POST /api/v1/medical/drug-interactions",
            "icd_codes": "POST /api/v1/medical/icd-codes",
            "question": "POST /api/v1/medical/question",
            "generate": "POST /api/v1/medical/generate",
            "embeddings": "POST /api/v1/medical/embeddings",
            "classify": "POST /api/v1/medical/classify"
        },
        "trace": {
            "description": "Agent Trace - Code attribution tracking for AI-generated code",
            "health": "/api/v1/trace/health",
            "file_attributions": "/api/v1/trace/files/{file_path}",
            "agent_attributions": "/api/v1/trace/agents/{agent_id}",
            "session_attributions": "/api/v1/trace/sessions/{session_id}",
            "recent_attributions": "/api/v1/trace/recent",
            "stats": "/api/v1/trace/stats",
            "generate_report": "POST /api/v1/trace/report"
        }
    }

@app.get("/ping")
async def ping():
    """Simple ping endpoint"""
    return {"message": "pong"}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8100)),
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
