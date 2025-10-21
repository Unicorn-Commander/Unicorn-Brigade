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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global memory_manager, workflow_manager

    logger.info("Starting Unicorn Brigade...")

    # Initialize memory manager
    memory_manager = MemoryManager()
    logger.info("Memory manager initialized")

    # Initialize workflow manager
    workflow_manager = WorkflowManager(memory_manager)
    logger.info("Workflow manager initialized")

    # Initialize API routes with managers
    init_managers(memory_manager, workflow_manager)
    logger.info("API routes initialized")

    yield

    logger.info("Shutting down Unicorn Brigade...")

# Create FastAPI app
app = FastAPI(
    title=os.getenv("API_TITLE", "Unicorn Brigade API"),
    version=os.getenv("API_VERSION", "1.0.0"),
    description="Multi-Agent Orchestration System with LangGraph and mem0",
    lifespan=lifespan
)

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router, prefix="/api/v1", tags=["agents"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Unicorn Brigade API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "health": "/api/v1/health",
            "system_status": "/api/v1/system/status",
            "execute_task": "/api/v1/agents/execute",
            "execute_stream": "/api/v1/agents/execute/stream",
            "query_memory": "/api/v1/memory/query",
            "docs": "/docs"
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
