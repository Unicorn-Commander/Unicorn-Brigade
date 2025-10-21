"""Ops-Center LLM Client - Routes through UC-Cloud's inference infrastructure"""

import httpx
import logging
import os
from typing import Dict, Any, List, Optional, AsyncGenerator
import json

logger = logging.getLogger(__name__)

class OpsCenterLLMClient:
    """Client for Ops-Center LLM inference (vLLM, OpenRouter, etc.)"""

    def __init__(self, ops_center_url: str = None):
        self.ops_center_url = ops_center_url or os.getenv(
            "OPS_CENTER_URL",
            "http://ops-center-direct:8084"
        )
        self.client = httpx.AsyncClient(timeout=120.0)
        logger.info(f"OpsCenterLLMClient initialized: {self.ops_center_url}")

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
            # Build request to Ops-Center's LLM endpoint
            payload = {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream
            }

            headers = {}
            if user_id:
                headers["X-User-ID"] = user_id

            logger.info(f"Sending chat completion request to Ops-Center: {model}")

            # Call Ops-Center's inference API
            response = await self.client.post(
                f"{self.ops_center_url}/api/v1/llm/chat/completions",
                json=payload,
                headers=headers
            )

            response.raise_for_status()
            result = response.json()

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
            payload = {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True
            }

            headers = {}
            if user_id:
                headers["X-User-ID"] = user_id

            logger.info(f"Starting streaming request to Ops-Center: {model}")

            async with self.client.stream(
                "POST",
                f"{self.ops_center_url}/api/v1/llm/chat/completions",
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
            return response.json().get("models", [])
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
