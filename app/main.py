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
from app.db.database import init_db, close_db
from app.db.init_db import seed_agents

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
    # apikey_routes and conversation_routes use Depends(get_session) directly
    logger.info("All route modules initialized")

    yield

    # Cleanup
    await close_db()
    if llm_client:
        await llm_client.close()
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
