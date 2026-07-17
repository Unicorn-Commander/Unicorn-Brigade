"""
Langflow API Routes

Provides REST endpoints for Langflow visual workflow integration:
- GET /api/v1/langflow/flows - List available flows
- GET /api/v1/langflow/flows/{id} - Get flow details
- POST /api/v1/langflow/flows/{id}/run - Execute a flow
- POST /api/v1/langflow/flows/import - Import flow from JSON
- GET /api/v1/langflow/flows/{id}/export - Export flow as JSON
- GET /api/v1/langflow/health - Langflow service health
"""

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Annotated
import logging
import json

# S7 (MED) fix — Langflow routes were fully unauthenticated (no Depends at all),
# so anyone could run/import/create/update/delete flows (arbitrary exec). Mutating
# and flow-execution routes now require OPERATOR; read-only GETs require any valid
# API key/bearer (VIEWER+). ``/langflow/health`` stays public via roles.PUBLIC_PATHS.
from app.auth.middleware import require_api_key, require_operator, AuthUser
from app.integrations.langflow import (
    LangflowClient,
    LangflowFlow,
    LangflowError,
    LangflowAPIError,
    get_langflow_client,
    LANGFLOW_ENABLED,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/langflow", tags=["langflow"])

# Module-level client (initialized via init function)
langflow_client: Optional[LangflowClient] = None


def init_langflow_routes():
    """Initialize Langflow routes with client"""
    global langflow_client

    if LANGFLOW_ENABLED:
        langflow_client = get_langflow_client()
        logger.info("Langflow routes initialized")
    else:
        logger.info("Langflow integration disabled (LANGFLOW_ENABLED=false)")


# ============================================================================
# Request/Response Models
# ============================================================================

class FlowResponse(BaseModel):
    """Response model for a single flow"""
    id: str
    name: str
    description: str = ""
    is_component: bool = False
    endpoint_name: Optional[str] = None
    folder_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class FlowListResponse(BaseModel):
    """Response model for flow list"""
    flows: List[FlowResponse]
    total: int


class FlowDetailResponse(BaseModel):
    """Response model for flow details including data"""
    id: str
    name: str
    description: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    is_component: bool = False
    endpoint_name: Optional[str] = None
    components: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RunFlowRequest(BaseModel):
    """Request model for running a flow"""
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Input values for the flow")
    tweaks: Optional[Dict[str, Any]] = Field(None, description="Component parameter overrides")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")


class RunFlowResponse(BaseModel):
    """Response model for flow execution"""
    session_id: str
    outputs: Dict[str, Any]
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: Optional[float] = None
    success: bool = True
    error: Optional[str] = None


class ImportFlowRequest(BaseModel):
    """Request model for importing a flow"""
    flow_data: Dict[str, Any] = Field(..., description="Flow data from Langflow export")
    name: Optional[str] = Field(None, description="Override flow name")
    folder_id: Optional[str] = Field(None, description="Folder to place flow in")


class ExportFlowResponse(BaseModel):
    """Response model for flow export"""
    name: str
    description: str = ""
    data: Dict[str, Any]
    is_component: bool = False
    endpoint_name: Optional[str] = None
    _export_version: str = "1.0"
    _exported_at: str = ""
    _source: str = "unicorn-brigade"


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    langflow_url: str
    version: Optional[str] = None
    error: Optional[str] = None


class WorkflowConversionResponse(BaseModel):
    """Response model for workflow conversion"""
    id: str
    name: str
    description: str = ""
    type: str = "langflow"
    source: str = "langflow"
    steps: List[Dict[str, Any]]
    connections: List[Dict[str, Any]]
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Health Endpoint
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def langflow_health():
    """
    Check Langflow service health.

    Returns connection status and version information.

    NOTE: ``/api/v1/langflow/health`` is intentionally in
    ``app.auth.roles.PUBLIC_PATHS`` (monitoring), so no auth dependency is added
    — a public path short-circuits ``get_current_user``. Every other langflow
    route below IS authenticated.
    """
    if not LANGFLOW_ENABLED:
        return HealthResponse(
            status="disabled",
            langflow_url="",
            error="Langflow integration is disabled",
        )

    if not langflow_client:
        return HealthResponse(
            status="not_initialized",
            langflow_url="",
            error="Langflow client not initialized",
        )

    health = await langflow_client.health_check()
    version = await langflow_client.get_version() if health.get("status") == "healthy" else None

    return HealthResponse(
        status=health.get("status", "unknown"),
        langflow_url=health.get("langflow_url", ""),
        version=version,
        error=health.get("error"),
    )


# ============================================================================
# Flow Listing & Details
# ============================================================================

@router.get("/flows", response_model=FlowListResponse)
async def list_flows(
    folder_id: Optional[str] = Query(None, description="Filter by folder ID"),
    components_only: bool = Query(False, description="Only return component flows"),
    _user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    List available Langflow flows.

    Returns all flows the user has access to, optionally filtered by folder.
    """
    if not LANGFLOW_ENABLED or not langflow_client:
        raise HTTPException(
            status_code=503,
            detail="Langflow integration is not enabled or not initialized"
        )

    try:
        flows = await langflow_client.list_flows(
            folder_id=folder_id,
            components_only=components_only,
        )

        flow_responses = [
            FlowResponse(
                id=f.id,
                name=f.name,
                description=f.description,
                is_component=f.is_component,
                endpoint_name=f.endpoint_name,
                folder_id=f.folder_id,
                created_at=f.created_at.isoformat() if f.created_at else None,
                updated_at=f.updated_at.isoformat() if f.updated_at else None,
            )
            for f in flows
        ]

        return FlowListResponse(
            flows=flow_responses,
            total=len(flow_responses),
        )

    except LangflowAPIError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=str(e))
    except LangflowError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flows/{flow_id}", response_model=FlowDetailResponse)
async def get_flow(
    flow_id: str,
    _user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Get detailed information about a specific flow.

    Includes flow data, components, and connections.
    """
    if not LANGFLOW_ENABLED or not langflow_client:
        raise HTTPException(
            status_code=503,
            detail="Langflow integration is not enabled or not initialized"
        )

    try:
        flow = await langflow_client.get_flow(flow_id)

        if not flow:
            raise HTTPException(status_code=404, detail=f"Flow not found: {flow_id}")

        # Extract components and edges for easier consumption
        components = [
            {
                "id": c.id,
                "type": c.type,
                "name": c.name,
                "position": c.position,
            }
            for c in flow.get_components()
        ]

        edges = [
            {
                "id": e.id,
                "source": e.source,
                "target": e.target,
                "source_handle": e.source_handle,
                "target_handle": e.target_handle,
            }
            for e in flow.get_edges()
        ]

        return FlowDetailResponse(
            id=flow.id,
            name=flow.name,
            description=flow.description,
            data=flow.data,
            is_component=flow.is_component,
            endpoint_name=flow.endpoint_name,
            components=components,
            edges=edges,
            created_at=flow.created_at.isoformat() if flow.created_at else None,
            updated_at=flow.updated_at.isoformat() if flow.updated_at else None,
        )

    except HTTPException:
        raise
    except LangflowAPIError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=str(e))
    except LangflowError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Flow Execution
# ============================================================================

@router.post("/flows/{flow_id}/run", response_model=RunFlowResponse)
async def run_flow(
    flow_id: str,
    request: RunFlowRequest,
    _user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Execute a Langflow flow.

    Runs the flow with provided inputs and returns outputs.
    Supports session-based conversation continuity.
    """
    if not LANGFLOW_ENABLED or not langflow_client:
        raise HTTPException(
            status_code=503,
            detail="Langflow integration is not enabled or not initialized"
        )

    try:
        result = await langflow_client.run_flow(
            flow_id=flow_id,
            inputs=request.inputs,
            tweaks=request.tweaks,
            session_id=request.session_id,
        )

        return RunFlowResponse(
            session_id=result.session_id,
            outputs=result.outputs,
            artifacts=result.artifacts,
            duration_ms=result.duration_ms,
            success=True,
        )

    except LangflowAPIError as e:
        # Return error in response rather than HTTP error for flow execution
        return RunFlowResponse(
            session_id=request.session_id or "",
            outputs={},
            success=False,
            error=str(e),
        )
    except LangflowError as e:
        return RunFlowResponse(
            session_id=request.session_id or "",
            outputs={},
            success=False,
            error=str(e),
        )


# ============================================================================
# Import/Export
# ============================================================================

@router.post("/flows/import", response_model=FlowResponse)
async def import_flow(
    request: ImportFlowRequest,
    _user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Import a flow from JSON data.

    Accepts flow data exported from Langflow UI or export endpoint.
    """
    if not LANGFLOW_ENABLED or not langflow_client:
        raise HTTPException(
            status_code=503,
            detail="Langflow integration is not enabled or not initialized"
        )

    try:
        flow = await langflow_client.import_flow(
            flow_data=request.flow_data,
            name=request.name,
            folder_id=request.folder_id,
        )

        return FlowResponse(
            id=flow.id,
            name=flow.name,
            description=flow.description,
            is_component=flow.is_component,
            endpoint_name=flow.endpoint_name,
            folder_id=flow.folder_id,
            created_at=flow.created_at.isoformat() if flow.created_at else None,
            updated_at=flow.updated_at.isoformat() if flow.updated_at else None,
        )

    except LangflowAPIError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=str(e))
    except LangflowError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flows/{flow_id}/export")
async def export_flow(
    flow_id: str,
    _user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Export a flow as JSON.

    Returns flow data that can be imported into Langflow
    or used by Unicorn Brigade workflows.
    """
    if not LANGFLOW_ENABLED or not langflow_client:
        raise HTTPException(
            status_code=503,
            detail="Langflow integration is not enabled or not initialized"
        )

    try:
        export_data = await langflow_client.export_flow(flow_id)
        return export_data

    except LangflowAPIError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=str(e))
    except LangflowError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"Flow not found: {flow_id}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Workflow Conversion
# ============================================================================

@router.get("/flows/{flow_id}/convert", response_model=WorkflowConversionResponse)
async def convert_flow_to_workflow(
    flow_id: str,
    _user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Convert a Langflow flow to Unicorn Brigade workflow format.

    This allows Langflow flows to be used as Brigade workflows
    and integrated with the orchestration system.
    """
    if not LANGFLOW_ENABLED or not langflow_client:
        raise HTTPException(
            status_code=503,
            detail="Langflow integration is not enabled or not initialized"
        )

    try:
        flow = await langflow_client.get_flow(flow_id)

        if not flow:
            raise HTTPException(status_code=404, detail=f"Flow not found: {flow_id}")

        workflow = langflow_client.convert_to_brigade_workflow(flow)

        return WorkflowConversionResponse(**workflow)

    except HTTPException:
        raise
    except LangflowAPIError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=str(e))
    except LangflowError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/convert-to-langflow")
async def convert_workflow_to_langflow(
    workflow: Dict[str, Any] = Body(..., description="Brigade workflow definition"),
    # require_api_key (VIEWER+), not require_operator: this is a pure, stateless
    # transform — it neither executes a flow nor mutates any Langflow state — so
    # an authenticated caller is the right floor. The auth dep still closes the
    # unauthenticated-access hole.
    _user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Convert a Unicorn Brigade workflow to Langflow format.

    This allows Brigade workflows to be edited visually in Langflow.
    """
    if not LANGFLOW_ENABLED or not langflow_client:
        raise HTTPException(
            status_code=503,
            detail="Langflow integration is not enabled or not initialized"
        )

    try:
        flow_data = langflow_client.convert_from_brigade_workflow(workflow)

        return {
            "name": workflow.get("name", "Converted Workflow"),
            "description": workflow.get("description", ""),
            "data": flow_data,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {e}")


# ============================================================================
# Flow Management (Create/Update/Delete)
# ============================================================================

class CreateFlowRequest(BaseModel):
    """Request model for creating a flow"""
    name: str = Field(..., description="Flow name")
    description: str = Field("", description="Flow description")
    data: Dict[str, Any] = Field(default_factory=dict, description="Flow data (nodes and edges)")
    folder_id: Optional[str] = Field(None, description="Folder to place flow in")
    endpoint_name: Optional[str] = Field(None, description="Custom endpoint name")


class UpdateFlowRequest(BaseModel):
    """Request model for updating a flow"""
    name: Optional[str] = Field(None, description="New flow name")
    description: Optional[str] = Field(None, description="New description")
    data: Optional[Dict[str, Any]] = Field(None, description="New flow data")
    endpoint_name: Optional[str] = Field(None, description="New endpoint name")


@router.post("/flows", response_model=FlowResponse)
async def create_flow(
    request: CreateFlowRequest,
    _user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Create a new Langflow flow.
    """
    if not LANGFLOW_ENABLED or not langflow_client:
        raise HTTPException(
            status_code=503,
            detail="Langflow integration is not enabled or not initialized"
        )

    try:
        flow = await langflow_client.create_flow(
            name=request.name,
            data=request.data,
            description=request.description,
            folder_id=request.folder_id,
            endpoint_name=request.endpoint_name,
        )

        return FlowResponse(
            id=flow.id,
            name=flow.name,
            description=flow.description,
            is_component=flow.is_component,
            endpoint_name=flow.endpoint_name,
            folder_id=flow.folder_id,
            created_at=flow.created_at.isoformat() if flow.created_at else None,
            updated_at=flow.updated_at.isoformat() if flow.updated_at else None,
        )

    except LangflowAPIError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=str(e))
    except LangflowError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/flows/{flow_id}", response_model=FlowResponse)
async def update_flow(
    flow_id: str,
    request: UpdateFlowRequest,
    _user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Update an existing Langflow flow.
    """
    if not LANGFLOW_ENABLED or not langflow_client:
        raise HTTPException(
            status_code=503,
            detail="Langflow integration is not enabled or not initialized"
        )

    try:
        flow = await langflow_client.update_flow(
            flow_id=flow_id,
            name=request.name,
            description=request.description,
            data=request.data,
            endpoint_name=request.endpoint_name,
        )

        return FlowResponse(
            id=flow.id,
            name=flow.name,
            description=flow.description,
            is_component=flow.is_component,
            endpoint_name=flow.endpoint_name,
            folder_id=flow.folder_id,
            created_at=flow.created_at.isoformat() if flow.created_at else None,
            updated_at=flow.updated_at.isoformat() if flow.updated_at else None,
        )

    except LangflowAPIError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=str(e))
    except LangflowError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/flows/{flow_id}")
async def delete_flow(
    flow_id: str,
    _user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Delete a Langflow flow.
    """
    if not LANGFLOW_ENABLED or not langflow_client:
        raise HTTPException(
            status_code=503,
            detail="Langflow integration is not enabled or not initialized"
        )

    try:
        deleted = await langflow_client.delete_flow(flow_id)

        if not deleted:
            raise HTTPException(status_code=404, detail=f"Flow not found: {flow_id}")

        return {"message": f"Flow {flow_id} deleted successfully"}

    except HTTPException:
        raise
    except LangflowAPIError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=str(e))
    except LangflowError as e:
        raise HTTPException(status_code=500, detail=str(e))
