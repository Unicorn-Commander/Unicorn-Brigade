"""
MLX LLM Provider - Local inference using Apple MLX framework.

Uses IBM Granite 3.3 models (2B/8B) for local, on-device inference.
Great for testing and offline usage on Mac with Apple Silicon.
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Lazy load MLX to avoid import errors on non-Mac systems
_mlx_model = None
_mlx_tokenizer = None
_mlx_model_name = None


def _get_mlx():
    """Lazy load mlx_lm module."""
    try:
        from mlx_lm import generate, load
        from mlx_lm.sample_utils import make_sampler
        return generate, load, make_sampler
    except ImportError:
        logger.error("mlx_lm not installed. Run: pip install mlx-lm")
        raise ImportError("mlx_lm is required for local MLX inference")


def load_mlx_model(model_name: str = "mlx-community/granite-3.3-2b-instruct-4bit"):
    """
    Load an MLX model into memory.

    Args:
        model_name: HuggingFace model ID or local path

    Returns:
        Tuple of (model, tokenizer)
    """
    global _mlx_model, _mlx_tokenizer, _mlx_model_name

    # Return cached model if same model requested
    if _mlx_model is not None and _mlx_model_name == model_name:
        logger.info(f"Using cached MLX model: {model_name}")
        return _mlx_model, _mlx_tokenizer

    logger.info(f"Loading MLX model: {model_name}")
    _, load, _ = _get_mlx()

    _mlx_model, _mlx_tokenizer = load(model_name)
    _mlx_model_name = model_name

    logger.info(f"MLX model loaded: {model_name}")
    return _mlx_model, _mlx_tokenizer


def format_chat_messages(messages: List[Dict[str, Any]], tokenizer) -> str:
    """
    Format chat messages into a prompt string.

    Granite models use IBM's chat template which the tokenizer handles.
    """
    # Try using the tokenizer's chat template if available
    try:
        if hasattr(tokenizer, 'apply_chat_template'):
            prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            return prompt
    except Exception as e:
        logger.warning(f"Chat template failed, using fallback: {e}")

    # Fallback: simple text format
    prompt_parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Handle tool messages
        if role == "tool":
            tool_name = msg.get("name", "tool")
            prompt_parts.append(f"<|tool_result|>{tool_name}: {content}<|end|>")
        elif role == "system":
            prompt_parts.append(f"<|system|>{content}<|end|>")
        elif role == "user":
            prompt_parts.append(f"<|user|>{content}<|end|>")
        elif role == "assistant":
            # Check for tool calls in assistant message
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                for tc in tool_calls:
                    func = tc.get("function", {})
                    prompt_parts.append(
                        f"<|assistant|><|tool_call|>{func.get('name', 'unknown')}: "
                        f"{func.get('arguments', '{}')}<|end|>"
                    )
            elif content:
                prompt_parts.append(f"<|assistant|>{content}<|end|>")

    prompt_parts.append("<|assistant|>")
    return "\n".join(prompt_parts)


class MLXLLMClient:
    """
    Local LLM client using Apple MLX framework.

    Provides OpenAI-compatible interface for local Granite models.
    """

    # Available local models
    MODELS = {
        "granite-3.3-2b": "mlx-community/granite-3.3-2b-instruct-4bit",
        "granite-3.3-8b": "mlx-community/granite-3.3-8b-instruct-4bit",
        "granite-4.0-micro": "mlx-community/granite-4.0-h-micro-4bit",
    }

    DEFAULT_MODEL = "granite-3.3-2b"

    def __init__(self, model_name: str = None):
        """
        Initialize MLX client.

        Args:
            model_name: Model alias (granite-3.3-2b, granite-3.3-8b) or full HF path
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self._model = None
        self._tokenizer = None

    def _ensure_model_loaded(self):
        """Ensure model is loaded before inference."""
        if self._model is None:
            model_path = self.MODELS.get(self.model_name, self.model_name)
            self._model, self._tokenizer = load_mlx_model(model_path)

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create chat completion using local MLX model.

        Returns OpenAI-compatible response format.
        """
        # Run in thread pool since MLX is sync
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._sync_chat_completion(messages, model, temperature, max_tokens)
        )

    def _sync_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Dict[str, Any]:
        """Synchronous chat completion."""
        self._ensure_model_loaded()
        generate, _, make_sampler = _get_mlx()

        # Format messages into prompt
        prompt = format_chat_messages(messages, self._tokenizer)

        logger.info(f"MLX generating with {self.model_name}, max_tokens={max_tokens}, temp={temperature}")

        # Create sampler with temperature
        sampler = make_sampler(temp=temperature)

        # Generate response
        response_text = generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            sampler=sampler,
            verbose=False,
        )

        # Parse for tool calls (Granite uses XML-like tags)
        tool_calls = self._parse_tool_calls(response_text)

        # Build OpenAI-compatible response
        message = {
            "role": "assistant",
            "content": response_text if not tool_calls else None,
        }

        if tool_calls:
            message["tool_calls"] = tool_calls
            message["content"] = None  # Content is null when tool calls present

        return {
            "id": f"mlx-{id(response_text)}",
            "object": "chat.completion",
            "model": self.model_name,
            "choices": [{
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if tool_calls else "stop",
            }],
            "usage": {
                "prompt_tokens": len(prompt.split()),  # Rough estimate
                "completion_tokens": len(response_text.split()),
                "total_tokens": len(prompt.split()) + len(response_text.split()),
            }
        }

    def _parse_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse tool calls from Granite's response.

        Granite may output tool calls in various formats:
        - JSON: {"name": "tool", "arguments": {...}}
        - Function syntax: tool_name(arg1, arg2)
        - XML-like: <tool_call>...</tool_call>
        """
        tool_calls = []

        # Try JSON format first
        try:
            # Look for JSON objects that look like tool calls
            import re
            json_pattern = r'\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\}'
            matches = re.findall(json_pattern, text)

            for i, match in enumerate(matches):
                try:
                    parsed = json.loads(match)
                    if "name" in parsed and "arguments" in parsed:
                        tool_calls.append({
                            "id": f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": parsed["name"],
                                "arguments": json.dumps(parsed["arguments"]),
                            }
                        })
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.debug(f"JSON tool call parsing failed: {e}")

        # Try function call syntax: calculator(expression="2+2")
        if not tool_calls:
            import re
            func_pattern = r'(\w+)\s*\(\s*([^)]*)\s*\)'
            matches = re.findall(func_pattern, text)

            known_tools = {"web_search", "calculator", "datetime", "http_request", "json", "shell", "memory"}

            for i, (name, args_str) in enumerate(matches):
                if name.lower() in known_tools:
                    # Parse arguments
                    args = {}
                    if args_str:
                        # Try to parse as keyword arguments
                        for arg in args_str.split(","):
                            if "=" in arg:
                                key, value = arg.split("=", 1)
                                key = key.strip()
                                value = value.strip().strip('"\'')
                                args[key] = value
                            else:
                                # Positional argument
                                args["query" if name == "web_search" else "expression"] = arg.strip().strip('"\'')

                    tool_calls.append({
                        "id": f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": name.lower(),
                            "arguments": json.dumps(args),
                        }
                    })

        return tool_calls

    async def chat_completion_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Any],  # List of ToolDefinition
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tool_choice: str = "auto",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Chat completion with function calling support.

        Injects tool descriptions into the system prompt for Granite.
        """
        # Build tool descriptions for the prompt
        tool_descriptions = []
        for tool in tools:
            tool_dict = tool.to_openai_format()
            func = tool_dict["function"]
            params_desc = []
            for name, prop in func["parameters"].get("properties", {}).items():
                required = name in func["parameters"].get("required", [])
                params_desc.append(f"  - {name} ({prop.get('type', 'any')}{'*' if required else ''}): {prop.get('description', '')}")

            tool_descriptions.append(
                f"- {func['name']}: {func['description']}\n"
                f"  Parameters:\n" + "\n".join(params_desc)
            )

        tools_text = "\n".join(tool_descriptions)

        # Inject tools into system message
        augmented_messages = list(messages)
        system_found = False

        for i, msg in enumerate(augmented_messages):
            if msg.get("role") == "system":
                augmented_messages[i] = {
                    **msg,
                    "content": msg["content"] + f"\n\nAvailable Tools:\n{tools_text}\n\nTo use a tool, respond with JSON: {{\"name\": \"tool_name\", \"arguments\": {{...}}}}"
                }
                system_found = True
                break

        if not system_found:
            augmented_messages.insert(0, {
                "role": "system",
                "content": f"You are a helpful assistant with access to tools.\n\nAvailable Tools:\n{tools_text}\n\nTo use a tool, respond with JSON: {{\"name\": \"tool_name\", \"arguments\": {{...}}}}"
            })

        return await self.chat_completion(
            messages=augmented_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def parse_tool_calls(self, response: Dict[str, Any]) -> List:
        """Parse tool calls from response (compatible with OpsCenterLLMClient)."""
        from app.llm.ops_center_client import ToolCall

        tool_calls = []
        choices = response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
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

        return tool_calls

    def has_tool_calls(self, response: Dict[str, Any]) -> bool:
        """Check if response contains tool calls."""
        choices = response.get("choices", [])
        if not choices:
            return False
        message = choices[0].get("message", {})
        return bool(message.get("tool_calls"))

    def get_response_content(self, response: Dict[str, Any]) -> str:
        """Extract text content from response."""
        choices = response.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return message.get("content", "") or ""

    async def execute_tool_loop(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Any],  # List of ToolDefinition
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        max_iterations: int = 10,
        on_tool_call: Optional[Callable] = None,
        on_tool_result: Optional[Callable] = None,
        user_id: Optional[str] = None,  # caller identity for needs_caller_context tools
        tool_guard=None,  # BR-6.4: per-caller ToolPermissionGuard; None = no gating
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a complete tool use loop locally.

        This handles the back-and-forth between the LLM and tools:
        1. Send message to LLM
        2. If tool calls, execute them
        3. Send results back to LLM
        4. Repeat until LLM responds without tool calls
        """
        from app.llm.ops_center_client import ToolResult

        tool_registry = {tool.name: tool for tool in tools}
        current_messages = list(messages)
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            logger.info(f"MLX tool loop iteration {iteration}/{max_iterations}")

            # Get LLM response
            response = await self.chat_completion_with_tools(
                messages=current_messages,
                tools=tools,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Check for tool calls
            if not self.has_tool_calls(response):
                logger.info("No tool calls in response, completing loop")
                return response

            # Parse tool calls
            tool_calls = self.parse_tool_calls(response)
            logger.info(f"Processing {len(tool_calls)} tool calls")

            # Add assistant message with tool calls to history
            assistant_message = response["choices"][0]["message"]
            current_messages.append(assistant_message)

            # Execute each tool call
            for tc in tool_calls:
                if on_tool_call:
                    on_tool_call(tc)

                tool_def = tool_registry.get(tc.name)
                # BR-6.4: per-caller tool permission (see ops_center_client's
                # execute_tool_loop — same contract). Refuse the single call
                # with a model-visible error; the loop continues.
                _denial = tool_guard.check(tc.name) if tool_guard is not None else None
                if _denial:
                    result = ToolResult(
                        tool_call_id=tc.id,
                        name=tc.name,
                        result=None,
                        error=_denial,
                    )
                elif not tool_def or not tool_def.handler:
                    result = ToolResult(
                        tool_call_id=tc.id,
                        name=tc.name,
                        result=None,
                        error=f"Unknown tool or no handler: {tc.name}",
                    )
                else:
                    try:
                        call_args = dict(tc.arguments)
                        if getattr(tool_def, "needs_caller_context", False):
                            # user_id is now a real parameter (it was previously
                            # an undefined name here — any needs_caller_context
                            # tool on the MLX path NameError'd into a tool error).
                            call_args["caller_user_id"] = user_id
                        tool_result = await tool_def.handler(**call_args)
                        result = ToolResult(
                            tool_call_id=tc.id,
                            name=tc.name,
                            result=tool_result,
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

                # Add tool result to messages
                current_messages.append(result.to_message())

        logger.warning(f"Tool loop reached max iterations ({max_iterations})")
        return response

    async def close(self):
        """Cleanup (no-op for MLX)."""
        pass


# Convenience function to get a client
def get_mlx_client(model: str = None) -> MLXLLMClient:
    """Get an MLX LLM client."""
    return MLXLLMClient(model_name=model)
