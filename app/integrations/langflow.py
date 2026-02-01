"""
Langflow Integration Client

Provides integration with Langflow visual workflow builder for:
- Flow management (list, get, create, update, delete)
- Flow execution (run flows with inputs)
- Flow import/export (JSON format)
- Converting Langflow flows to/from Unicorn Brigade workflow format
"""

import httpx
import logging
import os
import json
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

# Configuration from environment
LANGFLOW_ENABLED = os.getenv("LANGFLOW_ENABLED", "false").lower() == "true"
LANGFLOW_HOST = os.getenv("LANGFLOW_HOST", "http://localhost:7860")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY", "")


class LangflowError(Exception):
    """Base exception for Langflow operations"""
    pass


class LangflowConnectionError(LangflowError):
    """Error connecting to Langflow service"""
    pass


class LangflowAPIError(LangflowError):
    """Error from Langflow API"""
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class FlowStatus(str, Enum):
    """Langflow flow status"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


@dataclass
class LangflowComponent:
    """A component/node in a Langflow flow"""
    id: str
    type: str
    name: str
    template: Dict[str, Any] = field(default_factory=dict)
    position: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LangflowComponent":
        return cls(
            id=data.get("id", ""),
            type=data.get("type", ""),
            name=data.get("data", {}).get("node", {}).get("display_name", data.get("type", "")),
            template=data.get("data", {}).get("node", {}).get("template", {}),
            position=data.get("position", {}),
        )


@dataclass
class LangflowEdge:
    """An edge/connection in a Langflow flow"""
    id: str
    source: str
    target: str
    source_handle: str = ""
    target_handle: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LangflowEdge":
        return cls(
            id=data.get("id", ""),
            source=data.get("source", ""),
            target=data.get("target", ""),
            source_handle=data.get("sourceHandle", ""),
            target_handle=data.get("targetHandle", ""),
        )


@dataclass
class LangflowFlow:
    """Representation of a Langflow flow"""
    id: str
    name: str
    description: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    is_component: bool = False
    endpoint_name: Optional[str] = None
    folder_id: Optional[str] = None
    user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LangflowFlow":
        created_at = None
        updated_at = None

        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        if data.get("updated_at"):
            try:
                updated_at = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        return cls(
            id=data.get("id", ""),
            name=data.get("name", "Untitled Flow"),
            description=data.get("description", ""),
            data=data.get("data", {}),
            is_component=data.get("is_component", False),
            endpoint_name=data.get("endpoint_name"),
            folder_id=data.get("folder_id"),
            user_id=data.get("user_id"),
            created_at=created_at,
            updated_at=updated_at,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "data": self.data,
            "is_component": self.is_component,
            "endpoint_name": self.endpoint_name,
            "folder_id": self.folder_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_components(self) -> List[LangflowComponent]:
        """Extract components/nodes from flow data"""
        nodes = self.data.get("nodes", [])
        return [LangflowComponent.from_dict(n) for n in nodes]

    def get_edges(self) -> List[LangflowEdge]:
        """Extract edges/connections from flow data"""
        edges = self.data.get("edges", [])
        return [LangflowEdge.from_dict(e) for e in edges]


@dataclass
class FlowRunResult:
    """Result from running a Langflow flow"""
    session_id: str
    outputs: Dict[str, Any]
    artifacts: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    duration_ms: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlowRunResult":
        return cls(
            session_id=data.get("session_id", ""),
            outputs=data.get("outputs", {}),
            artifacts=data.get("artifacts", {}),
            logs=data.get("logs", []),
            duration_ms=data.get("duration_ms"),
        )


class LangflowClient:
    """
    Client for interacting with Langflow API.

    Langflow provides a visual workflow builder for LLM applications.
    This client enables programmatic management and execution of flows.

    API Reference:
    - Flow management: /api/v1/flows
    - Flow execution: /api/v1/run/{flow_id}
    - Health: /health
    """

    def __init__(
        self,
        host: str = None,
        api_key: str = None,
        timeout: float = 120.0,
    ):
        self.host = (host or LANGFLOW_HOST).rstrip("/")
        self.api_key = api_key or LANGFLOW_API_KEY
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

        logger.info(f"LangflowClient initialized: {self.host}")

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    def _headers(self) -> Dict[str, str]:
        """Build request headers"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            # Langflow also supports x-api-key header
            headers["x-api-key"] = self.api_key
        return headers

    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # Health & Status
    # =========================================================================

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Langflow service health.

        Returns:
            Health status dict with status and version info
        """
        try:
            response = await self.client.get(
                f"{self.host}/health",
                headers=self._headers(),
            )

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "langflow_url": self.host,
                    "response": response.json() if response.content else {},
                }
            else:
                return {
                    "status": "unhealthy",
                    "langflow_url": self.host,
                    "status_code": response.status_code,
                }

        except httpx.ConnectError as e:
            logger.error(f"Cannot connect to Langflow: {e}")
            return {
                "status": "unreachable",
                "langflow_url": self.host,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "error",
                "langflow_url": self.host,
                "error": str(e),
            }

    async def get_version(self) -> Optional[str]:
        """Get Langflow version"""
        try:
            response = await self.client.get(
                f"{self.host}/api/v1/version",
                headers=self._headers(),
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("version")
        except Exception as e:
            logger.warning(f"Failed to get Langflow version: {e}")
        return None

    # =========================================================================
    # Flow Management
    # =========================================================================

    async def list_flows(
        self,
        folder_id: Optional[str] = None,
        components_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[LangflowFlow]:
        """
        List available flows.

        Args:
            folder_id: Filter by folder
            components_only: Only return component flows
            limit: Maximum number of flows to return
            offset: Pagination offset

        Returns:
            List of LangflowFlow objects
        """
        try:
            params = {
                "remove_example_flows": "true",
            }
            if folder_id:
                params["folder_id"] = folder_id
            if components_only:
                params["components_only"] = "true"

            response = await self.client.get(
                f"{self.host}/api/v1/flows/",
                headers=self._headers(),
                params=params,
            )
            response.raise_for_status()

            data = response.json()

            # Handle different response formats
            if isinstance(data, list):
                flows = data
            elif isinstance(data, dict):
                flows = data.get("flows", data.get("data", []))
            else:
                flows = []

            return [LangflowFlow.from_dict(f) for f in flows]

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to list flows: {e.response.status_code}")
            raise LangflowAPIError(
                f"Failed to list flows: {e.response.text}",
                status_code=e.response.status_code,
            )
        except Exception as e:
            logger.error(f"Error listing flows: {e}")
            raise LangflowError(f"Error listing flows: {e}")

    async def get_flow(self, flow_id: str) -> Optional[LangflowFlow]:
        """
        Get a specific flow by ID.

        Args:
            flow_id: The flow UUID

        Returns:
            LangflowFlow object or None if not found
        """
        try:
            response = await self.client.get(
                f"{self.host}/api/v1/flows/{flow_id}",
                headers=self._headers(),
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            return LangflowFlow.from_dict(response.json())

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"Failed to get flow {flow_id}: {e}")
            raise LangflowAPIError(
                f"Failed to get flow: {e.response.text}",
                status_code=e.response.status_code,
            )
        except Exception as e:
            logger.error(f"Error getting flow {flow_id}: {e}")
            raise LangflowError(f"Error getting flow: {e}")

    async def create_flow(
        self,
        name: str,
        data: Dict[str, Any],
        description: str = "",
        folder_id: Optional[str] = None,
        endpoint_name: Optional[str] = None,
    ) -> LangflowFlow:
        """
        Create a new flow.

        Args:
            name: Flow name
            data: Flow data (nodes and edges)
            description: Flow description
            folder_id: Folder to place flow in
            endpoint_name: Custom endpoint name for running

        Returns:
            Created LangflowFlow object
        """
        try:
            payload = {
                "name": name,
                "description": description,
                "data": data,
            }
            if folder_id:
                payload["folder_id"] = folder_id
            if endpoint_name:
                payload["endpoint_name"] = endpoint_name

            response = await self.client.post(
                f"{self.host}/api/v1/flows/",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            return LangflowFlow.from_dict(response.json())

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to create flow: {e}")
            raise LangflowAPIError(
                f"Failed to create flow: {e.response.text}",
                status_code=e.response.status_code,
            )
        except Exception as e:
            logger.error(f"Error creating flow: {e}")
            raise LangflowError(f"Error creating flow: {e}")

    async def update_flow(
        self,
        flow_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        endpoint_name: Optional[str] = None,
    ) -> LangflowFlow:
        """
        Update an existing flow.

        Args:
            flow_id: Flow UUID to update
            name: New name (optional)
            description: New description (optional)
            data: New flow data (optional)
            endpoint_name: New endpoint name (optional)

        Returns:
            Updated LangflowFlow object
        """
        try:
            payload = {}
            if name is not None:
                payload["name"] = name
            if description is not None:
                payload["description"] = description
            if data is not None:
                payload["data"] = data
            if endpoint_name is not None:
                payload["endpoint_name"] = endpoint_name

            response = await self.client.patch(
                f"{self.host}/api/v1/flows/{flow_id}",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            return LangflowFlow.from_dict(response.json())

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to update flow {flow_id}: {e}")
            raise LangflowAPIError(
                f"Failed to update flow: {e.response.text}",
                status_code=e.response.status_code,
            )
        except Exception as e:
            logger.error(f"Error updating flow {flow_id}: {e}")
            raise LangflowError(f"Error updating flow: {e}")

    async def delete_flow(self, flow_id: str) -> bool:
        """
        Delete a flow.

        Args:
            flow_id: Flow UUID to delete

        Returns:
            True if deleted successfully
        """
        try:
            response = await self.client.delete(
                f"{self.host}/api/v1/flows/{flow_id}",
                headers=self._headers(),
            )

            if response.status_code == 404:
                return False

            response.raise_for_status()
            return True

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            logger.error(f"Failed to delete flow {flow_id}: {e}")
            raise LangflowAPIError(
                f"Failed to delete flow: {e.response.text}",
                status_code=e.response.status_code,
            )
        except Exception as e:
            logger.error(f"Error deleting flow {flow_id}: {e}")
            raise LangflowError(f"Error deleting flow: {e}")

    # =========================================================================
    # Flow Execution
    # =========================================================================

    async def run_flow(
        self,
        flow_id: str,
        inputs: Dict[str, Any] = None,
        tweaks: Dict[str, Any] = None,
        session_id: Optional[str] = None,
        stream: bool = False,
    ) -> FlowRunResult:
        """
        Execute a flow with given inputs.

        Args:
            flow_id: Flow UUID or endpoint name to run
            inputs: Input values for the flow
            tweaks: Component parameter overrides
            session_id: Session ID for conversation continuity
            stream: Whether to stream results (not implemented yet)

        Returns:
            FlowRunResult with outputs and metadata
        """
        try:
            import time
            start_time = time.time()

            payload = {
                "input_value": inputs.get("input_value", "") if inputs else "",
                "output_type": "chat",
                "input_type": "chat",
            }

            # Add tweaks if provided
            if tweaks:
                payload["tweaks"] = tweaks

            # Add session ID for conversation continuity
            if session_id:
                payload["session_id"] = session_id

            # Use the run endpoint
            response = await self.client.post(
                f"{self.host}/api/v1/run/{flow_id}",
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

            duration_ms = (time.time() - start_time) * 1000
            data = response.json()

            # Parse the response structure
            outputs = {}
            artifacts = {}
            logs = []
            result_session_id = session_id or ""

            # Handle different response formats from Langflow
            if isinstance(data, dict):
                # Check for outputs array format
                if "outputs" in data:
                    output_list = data["outputs"]
                    if isinstance(output_list, list) and len(output_list) > 0:
                        first_output = output_list[0]
                        if isinstance(first_output, dict):
                            # Get outputs from the first output group
                            if "outputs" in first_output:
                                inner_outputs = first_output["outputs"]
                                if isinstance(inner_outputs, list) and len(inner_outputs) > 0:
                                    result_data = inner_outputs[0]
                                    if isinstance(result_data, dict):
                                        # Extract the actual result
                                        results = result_data.get("results", {})
                                        message = results.get("message", {})
                                        if isinstance(message, dict):
                                            outputs["text"] = message.get("text", "")
                                            outputs["data"] = message.get("data", {})
                                        else:
                                            outputs["text"] = str(message)
                                        artifacts = result_data.get("artifacts", {})
                                        logs = result_data.get("logs", [])

                # Also check for session_id in response
                result_session_id = data.get("session_id", result_session_id)

            return FlowRunResult(
                session_id=result_session_id,
                outputs=outputs,
                artifacts=artifacts,
                logs=logs,
                duration_ms=duration_ms,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to run flow {flow_id}: {e}")
            raise LangflowAPIError(
                f"Failed to run flow: {e.response.text}",
                status_code=e.response.status_code,
            )
        except Exception as e:
            logger.error(f"Error running flow {flow_id}: {e}")
            raise LangflowError(f"Error running flow: {e}")

    # =========================================================================
    # Import/Export
    # =========================================================================

    async def export_flow(self, flow_id: str) -> Dict[str, Any]:
        """
        Export a flow as JSON.

        Args:
            flow_id: Flow UUID to export

        Returns:
            Flow data as JSON-serializable dict
        """
        flow = await self.get_flow(flow_id)
        if not flow:
            raise LangflowError(f"Flow not found: {flow_id}")

        # Return complete flow data for export
        return {
            "name": flow.name,
            "description": flow.description,
            "data": flow.data,
            "is_component": flow.is_component,
            "endpoint_name": flow.endpoint_name,
            # Metadata
            "_export_version": "1.0",
            "_exported_at": datetime.utcnow().isoformat(),
            "_source": "unicorn-brigade",
        }

    async def import_flow(
        self,
        flow_data: Dict[str, Any],
        name: Optional[str] = None,
        folder_id: Optional[str] = None,
    ) -> LangflowFlow:
        """
        Import a flow from JSON.

        Args:
            flow_data: Flow data dict (from export or Langflow UI export)
            name: Override the flow name
            folder_id: Folder to place imported flow

        Returns:
            Created LangflowFlow object
        """
        # Handle different export formats
        if "data" in flow_data:
            # Standard export format
            data = flow_data["data"]
            flow_name = name or flow_data.get("name", "Imported Flow")
            description = flow_data.get("description", "")
        else:
            # Raw flow data (from Langflow UI export)
            data = flow_data
            flow_name = name or "Imported Flow"
            description = ""

        return await self.create_flow(
            name=flow_name,
            data=data,
            description=description,
            folder_id=folder_id,
        )

    async def export_flows_batch(self, flow_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Export multiple flows.

        Args:
            flow_ids: List of flow UUIDs to export

        Returns:
            List of flow export dicts
        """
        exports = []
        for flow_id in flow_ids:
            try:
                export = await self.export_flow(flow_id)
                exports.append(export)
            except LangflowError as e:
                logger.warning(f"Failed to export flow {flow_id}: {e}")
                continue
        return exports

    # =========================================================================
    # Workflow Conversion
    # =========================================================================

    def convert_to_brigade_workflow(self, flow: LangflowFlow) -> Dict[str, Any]:
        """
        Convert a Langflow flow to Unicorn Brigade workflow format.

        This allows Langflow flows to be used as Brigade workflows.

        Args:
            flow: LangflowFlow to convert

        Returns:
            Brigade workflow definition dict
        """
        components = flow.get_components()
        edges = flow.get_edges()

        # Map Langflow component types to Brigade step types
        type_mapping = {
            "ChatInput": "input",
            "ChatOutput": "output",
            "OpenAIModel": "llm",
            "ChatOpenAI": "llm",
            "AnthropicModel": "llm",
            "Prompt": "prompt",
            "TextInput": "input",
            "TextOutput": "output",
            "ConditionalRouter": "router",
            "Agent": "agent",
            "Tool": "tool",
        }

        # Build workflow steps
        steps = []
        for component in components:
            step_type = "custom"
            for lf_type, brigade_type in type_mapping.items():
                if lf_type.lower() in component.type.lower():
                    step_type = brigade_type
                    break

            steps.append({
                "id": component.id,
                "name": component.name,
                "type": step_type,
                "langflow_type": component.type,
                "config": component.template,
                "position": component.position,
            })

        # Build workflow connections
        connections = []
        for edge in edges:
            connections.append({
                "from": edge.source,
                "to": edge.target,
                "from_output": edge.source_handle,
                "to_input": edge.target_handle,
            })

        return {
            "id": flow.id,
            "name": flow.name,
            "description": flow.description,
            "type": "langflow",
            "source": "langflow",
            "steps": steps,
            "connections": connections,
            "metadata": {
                "langflow_endpoint": flow.endpoint_name,
                "is_component": flow.is_component,
                "created_at": flow.created_at.isoformat() if flow.created_at else None,
            },
        }

    def convert_from_brigade_workflow(
        self,
        workflow: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert a Unicorn Brigade workflow to Langflow format.

        This allows Brigade workflows to be edited in Langflow UI.

        Args:
            workflow: Brigade workflow definition

        Returns:
            Langflow flow data dict
        """
        nodes = []
        edges = []

        steps = workflow.get("steps", [])
        connections = workflow.get("connections", [])

        # Convert steps to nodes
        for i, step in enumerate(steps):
            node = {
                "id": step.get("id", f"node_{i}"),
                "type": step.get("langflow_type", "GenericNode"),
                "position": step.get("position", {"x": i * 200, "y": 100}),
                "data": {
                    "node": {
                        "display_name": step.get("name", f"Step {i}"),
                        "template": step.get("config", {}),
                    }
                }
            }
            nodes.append(node)

        # Convert connections to edges
        for i, conn in enumerate(connections):
            edge = {
                "id": f"edge_{i}",
                "source": conn.get("from", ""),
                "target": conn.get("to", ""),
                "sourceHandle": conn.get("from_output", ""),
                "targetHandle": conn.get("to_input", ""),
            }
            edges.append(edge)

        return {
            "nodes": nodes,
            "edges": edges,
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        }


# Module-level client instance (lazy initialization)
_langflow_client: Optional[LangflowClient] = None


def get_langflow_client() -> LangflowClient:
    """Get or create the module-level Langflow client."""
    global _langflow_client

    if _langflow_client is None:
        _langflow_client = LangflowClient()

    return _langflow_client


async def close_langflow_client():
    """Close the module-level Langflow client."""
    global _langflow_client

    if _langflow_client:
        await _langflow_client.close()
        _langflow_client = None
