"""
API routes for remote code execution
"""

from fastapi import APIRouter, HTTPException, status, Header
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging
from datetime import datetime

from app.services.remote_executor import RemoteExecutor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/execution", tags=["execution"])


class CodeExecutionRequest(BaseModel):
    """Request to execute code"""
    code: str = Field(..., description="Source code to execute")
    language: str = Field(..., description="Programming language (python, javascript, etc.)")
    timeout: Optional[int] = Field(30, ge=1, le=300, description="Execution timeout in seconds")
    workspace: Optional[str] = Field(None, description="Optional workspace directory path")


class CodeExecutionResponse(BaseModel):
    """Response from code execution"""
    success: bool
    execution_id: str
    language: str
    output: str
    error: str
    exit_code: int
    execution_type: str
    duration_seconds: float
    timeout: int
    timestamp: str


class FileReadRequest(BaseModel):
    """Request to read a file"""
    path: str = Field(..., description="File path to read")


class FileWriteRequest(BaseModel):
    """Request to write a file"""
    path: str = Field(..., description="File path to write")
    content: str = Field(..., description="File content")


@router.post("/execute", response_model=CodeExecutionResponse)
async def execute_code(
    request: CodeExecutionRequest,
    user_id: str = Header(..., alias="X-User-ID")
):
    """
    Execute code on user's configured remote server

    Requires X-User-ID header to identify the user.
    """
    logger.info(f"Code execution request: {request.language} for user {user_id}")

    try:
        executor = RemoteExecutor(user_id)

        result = await executor.execute_code(
            language=request.language,
            code=request.code,
            timeout=request.timeout,
            workspace=request.workspace
        )

        return CodeExecutionResponse(**result)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Execution error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code execution failed: {str(e)}"
        )


@router.post("/files/read")
async def read_file(
    request: FileReadRequest,
    user_id: str = Header(..., alias="X-User-ID")
):
    """Read file from user's configured remote server"""
    logger.info(f"File read request: {request.path} for user {user_id}")

    try:
        executor = RemoteExecutor(user_id)
        content = await executor.read_file(request.path)

        return {
            "success": True,
            "path": request.path,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"File read error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}"
        )


@router.post("/files/write")
async def write_file(
    request: FileWriteRequest,
    user_id: str = Header(..., alias="X-User-ID")
):
    """Write file to user's configured remote server"""
    logger.info(f"File write request: {request.path} for user {user_id}")

    try:
        executor = RemoteExecutor(user_id)
        success = await executor.write_file(request.path, request.content)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to write file"
            )

        return {
            "success": True,
            "path": request.path,
            "timestamp": datetime.utcnow().isoformat()
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"File write error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write file: {str(e)}"
        )


@router.get("/languages")
async def list_supported_languages():
    """List all supported programming languages"""
    languages = []

    for lang, config in RemoteExecutor.LANGUAGE_COMMANDS.items():
        languages.append({
            "language": lang,
            "extension": config["ext"],
            "command": config["cmd"]
        })

    return {
        "languages": languages,
        "count": len(languages)
    }


@router.get("/server-config")
async def get_server_config(
    user_id: str = Header(..., alias="X-User-ID")
):
    """Get user's execution server configuration (masked)"""
    try:
        executor = RemoteExecutor(user_id)
        config = await executor.get_server_config()

        # Mask sensitive fields
        masked_config = config.copy()
        if "connection" in masked_config:
            conn = masked_config["connection"].copy()
            if "password" in conn:
                conn["password"] = "***MASKED***"
            if "keyPath" in conn:
                conn["keyPath"] = "***MASKED***"
            masked_config["connection"] = conn

        return {
            "server_type": config.get("type"),
            "enabled": config.get("enabled"),
            "config": masked_config
        }

    except Exception as e:
        logger.error(f"Error fetching server config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch server config: {str(e)}"
        )
