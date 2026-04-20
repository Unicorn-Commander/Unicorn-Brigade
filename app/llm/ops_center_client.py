"""Ops-Center LLM Client - Routes through UC-Cloud's inference infrastructure"""

import httpx
import logging
import os
from typing import Dict, Any, List, Optional, AsyncGenerator, Callable, Union
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)


class ModelUnavailableError(Exception):
    """Raised when a requested model is not available (e.g., Ollama not running)"""
    pass


@dataclass
class ToolParameter:
    """Parameter definition for a tool"""
    name: str
    type: str  # "string", "number", "boolean", "array", "object"
    description: str
    required: bool = True
    enum: Optional[List[str]] = None
    default: Any = None
    items: Optional[Dict[str, Any]] = None  # For array types: {"type": "string"} or {"type": "object", ...}


@dataclass
class ToolDefinition:
    """Definition for a tool/function that the LLM can call"""
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    handler: Optional[Callable] = None  # Async function to execute the tool

    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format"""
        properties = {}
        required = []

        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            # Add items for array types (required by OpenAI)
            if param.type == "array" and param.items:
                prop["items"] = param.items
            elif param.type == "array":
                # Default to string items if not specified
                prop["items"] = {"type": "string"}
            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            }
        }


@dataclass
class ToolCall:
    """A tool call made by the LLM"""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolResult:
    """Result from executing a tool"""
    tool_call_id: str
    name: str
    result: Any
    error: Optional[str] = None

    def to_message(self) -> Dict[str, Any]:
        """Convert to a message for the LLM (OpenAI format)"""
        content = json.dumps(self.result) if not self.error else f"Error: {self.error}"
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "content": content,
        }

    def to_user_message(self) -> Dict[str, Any]:
        """Convert to a user message format (fallback for providers that don't support tool messages)"""
        if self.error:
            content = f"[Tool {self.name} error: {self.error}]"
        else:
            result_str = json.dumps(self.result, indent=2) if isinstance(self.result, (dict, list)) else str(self.result)
            content = f"[Tool {self.name} result]\n{result_str}"
        return {
            "role": "user",
            "content": content,
        }


class ToolRegistry:
    """Registry for available tools"""

    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool"""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name"""
        return self.tools.get(name)

    def list(self) -> List[ToolDefinition]:
        """List all registered tools"""
        return list(self.tools.values())

    def to_openai_format(self) -> List[Dict[str, Any]]:
        """Get all tools in OpenAI format"""
        return [tool.to_openai_format() for tool in self.tools.values()]

# Default URLs for different environments
DEFAULT_INTERNAL_URL = "http://ops-center-direct:8084"
DEFAULT_EXTERNAL_URL = "https://unicorncommander.ai"

# OpenRouter direct — BYOK mode.  When set, non-local models route
# directly to OpenRouter instead of going through Ops-Center.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1"

# Local LLM URL (llama.cpp / Ollama on the Docker network)
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://unicorn-llama-cpp:8080")

# Direct LLM endpoint override: when set, bypass Ops-Center and hit this
# OpenAI-compatible endpoint directly (e.g. llama.cpp router on host).
OPS_CENTER_LLM_ENDPOINT = os.getenv("OPS_CENTER_LLM_ENDPOINT", "")

# Per-node OpenAI-compatible endpoints for explicit model routing by prefix.
MIDBOY1_LLM_URL = os.getenv("MIDBOY1_LLM_URL", "http://192.168.10.68:8087")

# Brigade service key for authentication
BRIGADE_SERVICE_KEY = os.getenv("BRIGADE_SERVICE_KEY", "sk-brigade-service-key-2025")

# Default model to use when "default" is specified
DEFAULT_MODEL = os.getenv("DEFAULT_LLM_MODEL", "claude-3.5-haiku")


class OpsCenterLLMClient:
    """Client for Ops-Center LLM inference (vLLM, OpenRouter, etc.)"""

    def __init__(
        self,
        ops_center_url: str = None,
        service_key: str = None,
    ):
        # Determine URL: env var > explicit > auto-detect
        if ops_center_url:
            self.ops_center_url = ops_center_url
        elif os.getenv("OPS_CENTER_URL"):
            self.ops_center_url = os.getenv("OPS_CENTER_URL")
        else:
            # Auto-detect: use external URL if not in Docker network
            self.ops_center_url = self._detect_url()

        self.service_key = service_key or BRIGADE_SERVICE_KEY
        self.local_llm_url = LOCAL_LLM_URL
        # Disable gzip/deflate: httpx 0.27.x has a bug where gzip-compressed
        # chunked responses from uvicorn return empty bodies
        self.client = httpx.AsyncClient(
            timeout=180.0,
            headers={"Accept-Encoding": "identity"},
        )
        logger.info(f"OpsCenterLLMClient initialized: {self.ops_center_url}")
        logger.info(f"Local LLM URL: {self.local_llm_url}")

    def _resolve_local_model(self, model: str) -> tuple:
        """
        Determine where to route a model request.

        Returns (url, model_name, route_type) tuple where route_type is one of:
          "local"       — local llama.cpp / Ollama (models prefixed 'local/')
          "openrouter"  — direct OpenRouter BYOK (when OPENROUTER_API_KEY is set)
          "ops-center"  — Ops-Center cloud proxy (default)
        """
        if model.startswith("local/"):
            local_model = model[6:]  # Remove 'local/' prefix
            return self.local_llm_url, local_model, "local"
        if model.startswith("midboy1/"):
            midboy1_model = model[len("midboy1/"):]
            return MIDBOY1_LLM_URL, midboy1_model, "local"
        if OPENROUTER_API_KEY:
            return OPENROUTER_URL, model, "openrouter"
        if OPS_CENTER_LLM_ENDPOINT:
            # Direct hit on an OpenAI-compatible endpoint (e.g. llama.cpp router)
            return OPS_CENTER_LLM_ENDPOINT, model, "direct"
        return self.ops_center_url, model, "ops-center"

    def _detect_url(self) -> str:
        """Detect whether to use internal or external URL"""
        # Check if we can reach the internal URL (Docker network)
        try:
            import socket
            socket.setdefaulttimeout(1)
            socket.socket().connect(("ops-center-direct", 8084))
            return DEFAULT_INTERNAL_URL
        except (socket.error, socket.timeout, OSError):
            return DEFAULT_EXTERNAL_URL

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create chat completion via Ops-Center

        Ops-Center routes to:
        - vLLM (local GPU inference)
        - OpenRouter (multiple providers)
        - User's BYOK keys if configured

        Note: Due to a Traefik bug, Ops-Center returns SSE-wrapped responses
        even for non-streaming requests. This method handles both formats.

        Args:
            messages: List of chat messages
            model: Model name (Ops-Center will route appropriately)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream response
            user_id: User ID for billing/BYOK lookup

        Returns:
            OpenAI-compatible response dict
        """
        try:
            # Resolve model aliases
            if model in ("default", "auto"):
                model = DEFAULT_MODEL

            # Check for local model routing (local/ prefix) or OpenRouter BYOK
            target_url, resolved_model, route_type = self._resolve_local_model(model)

            # Build request payload
            payload = {
                "messages": messages,
                "model": resolved_model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream
            }

            if route_type == "local":
                # Local LLM: no auth needed, direct OpenAI-compatible endpoint
                headers = {"Content-Type": "application/json"}
                endpoint = f"{target_url}/v1/chat/completions"
                logger.info(f"Sending chat completion to LOCAL LLM: {resolved_model}")
            elif route_type == "direct":
                # Direct endpoint override (OPS_CENTER_LLM_ENDPOINT)
                headers = {"Content-Type": "application/json"}
                endpoint = target_url
                logger.info(f"Sending chat completion DIRECT to {endpoint}: {resolved_model}")
            elif route_type == "openrouter":
                # OpenRouter BYOK: standard OpenAI-compatible API
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                }
                endpoint = f"{target_url}/chat/completions"
                logger.info(f"Sending chat completion to OpenRouter: {resolved_model}")
            else:
                headers = {
                    "Authorization": f"Bearer {self.service_key}",
                    "Content-Type": "application/json",
                }
                # Only send X-User-ID for real user IDs (not anonymous/dev-bypass)
                # When omitted, Ops-Center bills to the service org instead
                if user_id and user_id not in ("anonymous", "dev-bypass", ""):
                    headers["X-User-ID"] = user_id
                endpoint = f"{target_url}/api/v1/llm/chat/completions"
                logger.info(f"Sending chat completion request to Ops-Center: {resolved_model}")

            # Use streaming client to handle SSE-wrapped responses
            # (Ops-Center returns SSE format due to Traefik chunked encoding bug)
            async with self.client.stream(
                "POST",
                endpoint,
                json=payload,
                headers=headers
            ) as response:
                content_type = response.headers.get("content-type", "")

                # Handle error responses first
                if response.status_code >= 400:
                    # For streaming responses, read all bytes first
                    error_bytes = b""
                    async for chunk in response.aiter_bytes():
                        error_bytes += chunk
                    error_text = error_bytes.decode() if error_bytes else "Unknown error"
                    logger.error(f"Ops-Center error {response.status_code}: {error_text}")
                    logger.error(f"Request model: {model}")

                    # Check if this is an Ollama model error - trigger fallback to API models
                    if "ollama" in model.lower():
                        raise ModelUnavailableError(f"Local Ollama model {model} unavailable: {error_text[:200]}")

                    # For non-Ollama errors, raise HTTP error
                    raise httpx.HTTPStatusError(
                        message=error_text,
                        request=response.request,
                        response=response
                    )

                # Parse successful response based on content-type
                if "text/event-stream" in content_type:
                    result = await self._parse_sse_response(response)
                else:
                    # Standard JSON response - read all bytes for streaming context
                    body_bytes = b""
                    async for chunk in response.aiter_bytes():
                        body_bytes += chunk
                    result = json.loads(body_bytes) if body_bytes else {}

            # Log token usage for billing
            if "usage" in result:
                logger.info(
                    f"Tokens used - Input: {result['usage'].get('prompt_tokens', 0)}, "
                    f"Output: {result['usage'].get('completion_tokens', 0)}"
                )

            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"Ops-Center API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error calling Ops-Center LLM: {e}")
            raise

    async def _parse_sse_response(self, response) -> Dict[str, Any]:
        """
        Parse SSE-wrapped response from Ops-Center.

        Ops-Center wraps non-streaming responses in SSE format due to
        a Traefik bug with chunked encoding. Format:
            data: {json}\n\n
            data: [DONE]\n\n

        Returns:
            Parsed JSON response dict
        """
        result = {}
        async for line in response.aiter_lines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("data: "):
                data = line[6:]  # Remove "data: " prefix
                if data == "[DONE]":
                    break
                try:
                    result = json.loads(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse SSE data: {e}")
                    continue
        return result

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion via Ops-Center

        Yields:
            Server-sent events with tokens
        """
        try:
            # Resolve model aliases
            if model in ("default", "local", "auto"):
                model = DEFAULT_MODEL

            target_url, resolved_model, route_type = self._resolve_local_model(model)

            payload = {
                "messages": messages,
                "model": resolved_model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True
            }

            if route_type == "local":
                headers = {"Content-Type": "application/json"}
                endpoint = f"{target_url}/v1/chat/completions"
            elif route_type == "direct":
                headers = {"Content-Type": "application/json"}
                endpoint = target_url
            elif route_type == "openrouter":
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                }
                endpoint = f"{target_url}/chat/completions"
            else:
                headers = {
                    "Authorization": f"Bearer {self.service_key}",
                    "Content-Type": "application/json",
                }
                if user_id and user_id not in ("anonymous", "dev-bypass", ""):
                    headers["X-User-ID"] = user_id
                endpoint = f"{target_url}/api/v1/llm/chat/completions"

            logger.info(f"Starting streaming request ({route_type}): {resolved_model}")

            async with self.client.stream(
                "POST",
                endpoint,
                json=payload,
                headers=headers
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        if data == "[DONE]":
                            break
                        yield data

        except Exception as e:
            logger.error(f"Error streaming from Ops-Center: {e}")
            raise

    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from Ops-Center"""
        try:
            response = await self.client.get(
                f"{self.ops_center_url}/api/v1/llm/models"
            )
            response.raise_for_status()
            data = response.json()
            # API returns {"object": "list", "data": [...]}
            return data.get("data", data.get("models", []))
        except Exception as e:
            logger.error(f"Error fetching models: {e}")
            return []

    async def check_user_subscription(self, user_id: str) -> Dict[str, Any]:
        """Check user's subscription tier and limits"""
        try:
            response = await self.client.get(
                f"{self.ops_center_url}/api/v1/subscriptions/user/{user_id}"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error checking subscription: {e}")
            return {}

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    async def chat_completion_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[ToolDefinition],
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tool_choice: str = "auto",  # "auto", "none", or {"type": "function", "function": {"name": "..."}}
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Chat completion with function calling support.

        Args:
            messages: List of chat messages
            tools: List of tool definitions
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            tool_choice: How to handle tool calls ("auto", "none", or specific tool)
            user_id: User ID for billing

        Returns:
            Response with potential tool_calls
        """
        try:
            # Resolve model aliases
            if model in ("default", "auto"):
                model = DEFAULT_MODEL

            # Check for local model routing (local/ prefix) or OpenRouter BYOK
            target_url, resolved_model, route_type = self._resolve_local_model(model)

            # Convert tools to OpenAI format
            tools_payload = [tool.to_openai_format() for tool in tools]

            payload = {
                "messages": messages,
                "model": resolved_model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "tools": tools_payload,
                "tool_choice": tool_choice,
            }

            if route_type == "local":
                headers = {"Content-Type": "application/json"}
                endpoint = f"{target_url}/v1/chat/completions"
                logger.info(f"Sending tool-enabled request to LOCAL LLM: {resolved_model} with {len(tools)} tools")
            elif route_type == "direct":
                headers = {"Content-Type": "application/json"}
                endpoint = target_url
                logger.info(f"Sending tool-enabled request DIRECT to {endpoint}: {resolved_model} with {len(tools)} tools")
            elif route_type == "openrouter":
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                }
                endpoint = f"{target_url}/chat/completions"
                logger.info(f"Sending tool-enabled request to OpenRouter: {resolved_model} with {len(tools)} tools")
            else:
                headers = {
                    "Authorization": f"Bearer {self.service_key}",
                    "Content-Type": "application/json",
                }
                # Only send X-User-ID for real user IDs (not anonymous/dev-bypass)
                if user_id and user_id not in ("anonymous", "dev-bypass", ""):
                    headers["X-User-ID"] = user_id
                endpoint = f"{target_url}/api/v1/llm/chat/completions"
                logger.info(f"Sending tool-enabled request to Ops-Center: {resolved_model} with {len(tools)} tools")

            # Debug: log message roles being sent
            msg_roles = [f"{m.get('role', '?')}" for m in messages]
            logger.debug(f"Message roles: {msg_roles}")

            # Extra debug for tool messages
            for m in messages:
                if m.get("role") == "tool":
                    logger.info(f"Tool message being sent: tool_call_id={m.get('tool_call_id')}, name={m.get('name')}")

            async with self.client.stream(
                "POST",
                endpoint,
                json=payload,
                headers=headers
            ) as response:
                # Read response body first (fixes httpx streaming error)
                content_type = response.headers.get("content-type", "")

                # Handle error responses before checking content-type
                if response.status_code >= 400:
                    # For streaming responses, we need to read all bytes first
                    error_bytes = b""
                    async for chunk in response.aiter_bytes():
                        error_bytes += chunk
                    error_text = error_bytes.decode() if error_bytes else "Unknown error"
                    logger.error(f"Ops-Center error {response.status_code}: {error_text}")
                    logger.error(f"Request model: {model}")
                    logger.error(f"Request payload (first 2000 chars): {json.dumps(payload)[:2000]}")

                    # Check if this is an Ollama model error - trigger fallback to API models
                    if "ollama" in model.lower():
                        raise ModelUnavailableError(f"Local Ollama model {model} unavailable: {error_text[:200]}")

                    # For non-Ollama errors, raise HTTP error
                    raise httpx.HTTPStatusError(
                        message=error_text,
                        request=response.request,
                        response=response
                    )

                # Parse successful response based on content-type
                if "text/event-stream" in content_type:
                    result = await self._parse_sse_response(response)
                else:
                    # For streaming responses, read all bytes first
                    body_bytes = b""
                    async for chunk in response.aiter_bytes():
                        body_bytes += chunk
                    result = json.loads(body_bytes) if body_bytes else {}

            return result

        except Exception as e:
            logger.error(f"Error in tool-enabled completion: {e}")
            raise

    def parse_tool_calls(self, response: Dict[str, Any]) -> List[ToolCall]:
        """
        Parse tool calls from LLM response.

        Handles both OpenAI and Claude response formats.
        """
        tool_calls = []

        # Check for OpenAI format
        choices = response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})

            # OpenAI tool_calls format
            if "tool_calls" in message:
                for tc in message["tool_calls"]:
                    try:
                        arguments = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        arguments = {"raw": tc["function"]["arguments"]}

                    tool_calls.append(ToolCall(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments=arguments,
                    ))

            # Claude tool_use format (content blocks)
            elif isinstance(message.get("content"), list):
                for block in message["content"]:
                    if block.get("type") == "tool_use":
                        tool_calls.append(ToolCall(
                            id=block["id"],
                            name=block["name"],
                            arguments=block.get("input", {}),
                        ))

        return tool_calls

    def has_tool_calls(self, response: Dict[str, Any]) -> bool:
        """Check if response contains tool calls"""
        choices = response.get("choices", [])
        if not choices:
            return False

        message = choices[0].get("message", {})

        # Check OpenAI format
        if message.get("tool_calls"):
            return True

        # Check Claude format
        if isinstance(message.get("content"), list):
            for block in message["content"]:
                if block.get("type") == "tool_use":
                    return True

        return False

    def get_response_content(self, response: Dict[str, Any]) -> str:
        """Extract text content from response"""
        choices = response.get("choices", [])
        if not choices:
            return ""

        message = choices[0].get("message", {})
        content = message.get("content", "")

        # Handle Claude format where content is a list
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            return "\n".join(text_parts)

        return content or ""

    async def execute_tool_loop(
        self,
        messages: List[Dict[str, Any]],
        tools: List[ToolDefinition],
        model: str = "default",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        max_iterations: int = 10,
        user_id: Optional[str] = None,
        on_tool_call: Optional[Callable[[ToolCall], None]] = None,
        on_tool_result: Optional[Callable[[ToolResult], None]] = None,
        use_user_message_fallback: bool = True,  # Use user messages for tool results (works with more providers)
        trace_recorder=None,  # Optional AgentTraceRecorder for code attribution
        agent_id: Optional[str] = None,  # Agent ID for tracing
        agent_name: Optional[str] = None,  # Agent name for tracing
    ) -> Dict[str, Any]:
        """
        Execute a complete tool use loop.

        This handles the back-and-forth between the LLM and tools:
        1. Send message to LLM
        2. If tool calls, execute them
        3. Send results back to LLM
        4. Repeat until LLM responds without tool calls

        Args:
            messages: Initial messages
            tools: Available tools (with handlers)
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Max tokens per turn
            max_iterations: Max tool call rounds
            user_id: User ID for billing
            on_tool_call: Callback when a tool is called
            on_tool_result: Callback when a tool returns
            use_user_message_fallback: If True, use user messages for tool results
                (more compatible but less structured than OpenAI tool format)
            trace_recorder: Optional AgentTraceRecorder for code attribution tracking
            agent_id: Agent ID for tracing (required if trace_recorder provided)
            agent_name: Agent name for tracing (required if trace_recorder provided)

        Returns:
            Final response from LLM
        """
        # Build tool registry for execution
        tool_registry = {tool.name: tool for tool in tools}

        current_messages = list(messages)
        iteration = 0
        retry_with_fallback = False

        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Tool loop iteration {iteration}/{max_iterations}")

            try:
                # Get LLM response
                response = await self.chat_completion_with_tools(
                    messages=current_messages,
                    tools=tools,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    user_id=user_id,
                )
            except Exception as e:
                error_msg = str(e)
                # Check if this is a tool message format error
                if "400" in error_msg or "422" in error_msg:
                    if use_user_message_fallback and not retry_with_fallback:
                        logger.warning("Tool message format rejected, switching to user message fallback")
                        retry_with_fallback = True
                        # Don't re-raise, continue with fallback mode
                        # But we need to redo the request - the error happened on second+ iteration
                        # For now, just re-raise since we can't easily undo the message additions
                        raise
                raise

            # Check for tool calls
            if not self.has_tool_calls(response):
                logger.info(f"No tool calls in response, completing loop")

                # Record code attribution if tracing is enabled
                if trace_recorder and agent_id and agent_name:
                    try:
                        response_text = self.get_response_content(response)
                        if response_text:
                            # Extract prompt from original user message
                            user_prompt = None
                            for msg in messages:
                                if msg.get("role") == "user":
                                    user_prompt = msg.get("content", "")
                                    break

                            # Auto-extract and record code from response
                            await trace_recorder.record_from_llm_response(
                                agent_id=agent_id,
                                agent_name=agent_name,
                                model=model,
                                prompt=user_prompt or "",
                                response=response_text,
                                metadata={
                                    "temperature": temperature,
                                    "max_tokens": max_tokens,
                                    "user_id": user_id,
                                },
                            )
                    except Exception as e:
                        logger.warning(f"Error recording code attribution: {e}")

                return response

            # Parse tool calls
            tool_calls = self.parse_tool_calls(response)
            logger.info(f"Processing {len(tool_calls)} tool calls")

            # Execute each tool call and collect results
            tool_results = []
            for tc in tool_calls:
                if on_tool_call:
                    on_tool_call(tc)

                tool_def = tool_registry.get(tc.name)
                if not tool_def or not tool_def.handler:
                    result = ToolResult(
                        tool_call_id=tc.id,
                        name=tc.name,
                        result=None,
                        error=f"Unknown tool or no handler: {tc.name}",
                    )
                else:
                    try:
                        # Execute tool handler
                        tool_output = await tool_def.handler(**tc.arguments)
                        result = ToolResult(
                            tool_call_id=tc.id,
                            name=tc.name,
                            result=tool_output,
                        )
                    except Exception as e:
                        logger.error(f"Tool execution error for {tc.name}: {e}")
                        result = ToolResult(
                            tool_call_id=tc.id,
                            name=tc.name,
                            result=None,
                            error=str(e),
                        )

                if on_tool_result:
                    on_tool_result(result)

                tool_results.append(result)

            # Add messages based on fallback mode
            if use_user_message_fallback:
                # User message fallback mode - more compatible
                # Don't add assistant message with tool_calls (causes issues with some providers)
                # Instead, add a simple assistant acknowledgment and user messages with results
                assistant_ack = {
                    "role": "assistant",
                    "content": f"I'll use the following tools: {', '.join(tc.name for tc in tool_calls)}",
                }
                current_messages.append(assistant_ack)

                # Combine all tool results into a single user message
                result_parts = []
                for result in tool_results:
                    if result.error:
                        result_parts.append(f"[Tool {result.name} error: {result.error}]")
                    else:
                        result_str = json.dumps(result.result, indent=2) if isinstance(result.result, (dict, list)) else str(result.result)
                        result_parts.append(f"[Tool {result.name} result]\n{result_str}")

                user_result_msg = {
                    "role": "user",
                    "content": "\n\n".join(result_parts),
                }
                current_messages.append(user_result_msg)
            else:
                # Standard OpenAI format - add assistant message with tool_calls
                raw_message = response["choices"][0]["message"]
                assistant_message = {
                    "role": "assistant",
                    "content": raw_message.get("content") or "",
                }
                if raw_message.get("tool_calls"):
                    assistant_message["tool_calls"] = [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": tc["function"]["arguments"],
                            }
                        }
                        for tc in raw_message["tool_calls"]
                    ]
                current_messages.append(assistant_message)

                # Add tool result messages
                for result in tool_results:
                    current_messages.append(result.to_message())

        # Max iterations reached
        logger.warning(f"Tool loop reached max iterations ({max_iterations})")
        return response
