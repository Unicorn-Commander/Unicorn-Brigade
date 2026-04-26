"""Memory manager backed by Graphiti + FalkorDB."""

from typing import Any, Optional, List, Dict
import asyncio
import logging
import os
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

try:
    from graphiti_core import Graphiti
    from graphiti_core.driver.falkordb_driver import FalkorDriver
    from graphiti_core.llm_client import OpenAIClient, LLMConfig
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
    from graphiti_core.nodes import EpisodeType
    GRAPHITI_AVAILABLE = True
except ImportError as _import_err:
    GRAPHITI_AVAILABLE = False
    logger.error(f"graphiti-core not available: {_import_err}")


FALKORDB_HOST = os.getenv("FALKORDB_HOST", "unicorn-falkordb")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
FALKORDB_DB = os.getenv("FALKORDB_DATABASE", "brigade_memories")

LLM_BASE_URL = os.getenv("MEMORY_LLM_BASE_URL", "http://172.17.0.1:8085/v1")
LLM_MODEL = os.getenv("MEMORY_LLM_MODEL", "Qwen3.6-35B-A3B-UD-Q4_K_XL")
LLM_SMALL_MODEL = os.getenv("MEMORY_LLM_SMALL_MODEL", LLM_MODEL)

EMBED_BASE_URL = os.getenv("MEMORY_EMBED_BASE_URL", "http://192.168.10.68:8086/v1")
EMBED_MODEL = os.getenv("MEMORY_EMBED_MODEL", "BAAI/bge-m3")
EMBED_DIMS = int(os.getenv("MEMORY_EMBED_DIMS", "1024"))



# ---- Patch: llama.cpp does NOT implement /v1/responses, only /v1/chat/completions.
# Override Graphiti's OpenAIClient to use chat.completions.parse for structured
# extraction. This keeps the pydantic schema validation working.
try:
    from openai.types.chat import ChatCompletionMessageParam
    from pydantic import BaseModel as _BaseModel

    class LlamaCppOpenAIClient(OpenAIClient):
        async def _create_structured_completion(
            self,
            model,
            messages,
            temperature,
            max_tokens,
            response_model,
            reasoning=None,
            verbosity=None,
        ):
            # chat.completions.parse works with any OpenAI-compatible server
            # that accepts response_format={type:json_schema,json_schema:{...}}.
            # llama.cpp rejects complex json_schema samplers, use json_object mode
            import json as _json
            schema = response_model.model_json_schema()
            schema_note = (
                "\n\nYou MUST respond with exactly one JSON object matching "
                "this JSON schema. Return ONLY the JSON, no prose, no code fences:\n"
                + _json.dumps(schema)
            )
            patched = list(messages)
            if patched and patched[0].get("role") == "system":
                patched[0] = {"role": "system", "content": patched[0]["content"] + schema_note}
            else:
                patched.insert(0, {"role": "system", "content": schema_note})
            resp = await self.client.chat.completions.create(
                model=model,
                messages=patched,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content or "{}"
            logger.warning(f"[graphiti-llm-raw] model={model} raw_first_500={raw[:500]!r}")
            try:
                parsed_obj = response_model.model_validate_json(raw)
            except Exception:
                import re as _re
                cleaned = _re.sub(r"<think>.*?</think>", "", raw, flags=_re.DOTALL|_re.IGNORECASE).strip()
                fence = chr(96) * 3
                if cleaned.startswith(fence):
                    cleaned = _re.sub(r"^" + fence + r"[a-zA-Z]*\n|\n" + fence + r"$", "", cleaned)
                parsed_obj = response_model.model_validate_json(cleaned)
            resp.choices[0].message.parsed = parsed_obj
            return resp

        def _handle_structured_response(self, response):
            msg = response.choices[0].message
            if getattr(msg, "refusal", None):
                from graphiti_core.llm_client.errors import RefusalError
                raise RefusalError(msg.refusal)
            parsed = msg.parsed
            if parsed is None:
                raise Exception(f"llama.cpp returned no parsed object: {response}")
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
            return parsed.model_dump() if hasattr(parsed, "model_dump") else dict(parsed), input_tokens, output_tokens
    GRAPHITI_LLM_CLIENT = LlamaCppOpenAIClient
except Exception as _patch_err:  # pragma: no cover
    logger.warning(f"Could not install llama.cpp openai patch: {_patch_err}")
    GRAPHITI_LLM_CLIENT = OpenAIClient


def _slug(s):
    return re.sub(r"[^A-Za-z0-9]", "_", s or "anon")


class GraphitiMemoryManager:
    """Temporal graph memory via Graphiti + FalkorDB."""

    def __init__(self):
        self.graphiti = None
        self._init_error = None
        self._indices_ready = False
        self._init_lock = asyncio.Lock()

        if not GRAPHITI_AVAILABLE:
            self._init_error = "graphiti-core not installed"
            return
        try:
            driver = FalkorDriver(host=FALKORDB_HOST, port=FALKORDB_PORT, database=FALKORDB_DB)
            llm = GRAPHITI_LLM_CLIENT(config=LLMConfig(
                api_key="local-dummy",
                model=LLM_MODEL,
                small_model=LLM_SMALL_MODEL,
                base_url=LLM_BASE_URL,
            ))
            embedder = OpenAIEmbedder(config=OpenAIEmbedderConfig(
                api_key="local-dummy",
                embedding_model=EMBED_MODEL,
                embedding_dim=EMBED_DIMS,
                base_url=EMBED_BASE_URL,
            ))
            self.graphiti = Graphiti(graph_driver=driver, llm_client=llm, embedder=embedder)
            logger.info(
                "GraphitiMemoryManager initialized: falkordb=%s:%s/%s, llm=%s@%s, embedder=%s (%sd)",
                FALKORDB_HOST, FALKORDB_PORT, FALKORDB_DB, LLM_MODEL, LLM_BASE_URL, EMBED_MODEL, EMBED_DIMS
            )
        except Exception as e:
            self._init_error = str(e)
            logger.error(f"Failed to initialize Graphiti: {e}")
            self.graphiti = None

    async def _ensure_indices(self):
        if self._indices_ready or not self.graphiti:
            return self._indices_ready
        async with self._init_lock:
            if self._indices_ready:
                return True
            try:
                await asyncio.wait_for(self.graphiti.build_indices_and_constraints(), timeout=30.0)
                self._indices_ready = True
                logger.info("Graphiti indices + constraints built")
            except Exception as e:
                logger.error(f"Failed to build Graphiti indices: {e}")
                return False
        return True

    def _group_id(self, user_id, agent_id, case_id=None):
        """Per-user-per-case-per-agent isolation. case_id is optional for
        callers that aren't case-scoped (existing Brigade consumers like
        LibreChat); when None, the group is {user}__{agent} as before."""
        parts = [_slug(user_id)]
        if case_id:
            parts.append(_slug(case_id))
        if agent_id:
            parts.append(_slug(agent_id))
        return "__".join(parts)

    async def _store_episode_now(self, user_id, agent_id, messages, metadata, case_id=None):
        try:
            lines = []
            for m in messages:
                role = m.get("role", "unknown")
                content = m.get("content", "")
                lines.append(f"{role}: {content}")
            episode_body = "\n".join(lines)
            case_suffix = f" (case {case_id})" if case_id else ""
            source_description = f"Chat exchange between {user_id} and agent {agent_id}{case_suffix}"
            if metadata and metadata.get("agent_name"):
                source_description = f"Chat with {metadata['agent_name']} ({agent_id}) and user {user_id}{case_suffix}"
            name_parts = ["chat", _slug(user_id)]
            if case_id:
                name_parts.append(_slug(case_id))
            name_parts.extend([_slug(agent_id), str(int(datetime.now(timezone.utc).timestamp()))])
            await self.graphiti.add_episode(
                name="-".join(name_parts),
                episode_body=episode_body,
                source=EpisodeType.message,
                source_description=source_description,
                reference_time=datetime.now(timezone.utc),
                group_id=self._group_id(user_id, agent_id, case_id),
            )
            logger.info(f"Graphiti stored episode user={user_id} agent={agent_id} case={case_id}")
        except Exception as e:
            logger.error(f"Background graphiti store failed: {e}")

    async def store(self, user_id, agent_id, messages, metadata=None, case_id=None):
        if not self.graphiti:
            return False
        if not await self._ensure_indices():
            return False
        asyncio.create_task(self._store_episode_now(user_id, agent_id, messages, metadata, case_id))
        return True

    async def retrieve(self, user_id, query, agent_id=None, limit=10, case_id=None):
        if not self.graphiti:
            return []
        if not await self._ensure_indices():
            return []
        try:
            group_id = self._group_id(user_id, agent_id, case_id)
            edges = await asyncio.wait_for(
                self.graphiti.search(query=query, group_ids=[group_id], num_results=limit),
                timeout=15.0,
            )
            memories = []
            for edge in edges or []:
                fact = getattr(edge, "fact", None) or getattr(edge, "name", None)
                if fact:
                    memories.append({"memory": fact, "uuid": getattr(edge, "uuid", None)})
            logger.info(f"Retrieved {len(memories)} graphiti memories user={user_id} agent={agent_id} case={case_id}")
            return memories
        except asyncio.TimeoutError:
            logger.warning("Graphiti retrieve timed out")
            return []
        except Exception as e:
            logger.error(f"Error retrieving graphiti memory: {e}")
            return []

    async def get_all(self, user_id, agent_id=None):
        return await self.retrieve(user_id=user_id, query="*", agent_id=agent_id, limit=100)

    async def delete(self, memory_id):
        return False

    async def update(self, memory_id, data):
        return False

    def get_stats(self):
        if not self.graphiti:
            return {"status": "unavailable", "error": self._init_error}
        return {
            "status": "operational",
            "provider": "graphiti",
            "graph": f"falkordb://{FALKORDB_HOST}:{FALKORDB_PORT}/{FALKORDB_DB}",
            "llm_model": LLM_MODEL,
            "embed_model": EMBED_MODEL,
            "indices_ready": self._indices_ready,
        }
