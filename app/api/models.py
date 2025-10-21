"""API models"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime

class TaskRequest(BaseModel):
    """Request model for agent tasks"""
    agent_type: str = Field(..., description="Type of agent (research, code, analysis)")
    task: str = Field(..., description="Task description")
    user_id: Optional[str] = Field(None, description="User ID for memory context")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    stream: Optional[bool] = Field(False, description="Enable streaming response")

    class Config:
        json_schema_extra = {
            "example": {
                "agent_type": "research",
                "task": "Research best practices for LangGraph",
                "user_id": "user123",
                "context": {},
                "stream": False
            }
        }

class TaskResponse(BaseModel):
    """Response model for agent tasks"""
    task_id: str
    status: str
    message: str
    result: Optional[List[Dict[str, Any]]] = None
    tokens: Optional[Dict[str, int]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task-uuid-here",
                "status": "completed",
                "message": "Task completed successfully",
                "result": [{"agent": "research", "summary": "..."}],
                "tokens": {"input": 150, "output": 500, "total": 650}
            }
        }

class AgentStatus(BaseModel):
    """Agent status model"""
    name: str
    status: str
    memory_enabled: bool

class SystemStatus(BaseModel):
    """System status model"""
    status: str
    version: str
    memory: Dict[str, Any]
    agents: Dict[str, AgentStatus]
    uptime: float
    timestamp: datetime

class MemoryQuery(BaseModel):
    """Memory query model"""
    user_id: str
    query: str
    agent_id: Optional[str] = None
    limit: Optional[int] = 10

class MemoryResponse(BaseModel):
    """Memory response model"""
    memories: List[Dict[str, Any]]
    count: int
