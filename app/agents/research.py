"""Research agent using Ops-Center LLM infrastructure"""

from typing import Dict, Any
from app.agents.base import BaseAgent
from app.llm.ops_center_client import OpsCenterLLMClient
import logging

logger = logging.getLogger(__name__)

class ResearchAgent(BaseAgent):
    """Agent for research and information gathering"""

    def __init__(self, memory_manager=None, llm_client=None):
        super().__init__("ResearchAgent", memory_manager)
        self.llm_client = llm_client or OpsCenterLLMClient()

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute research task via Ops-Center LLM"""
        logger.info(f"Research agent executing task: {task.get('task_id')}")

        try:
            # Get relevant memories
            memories = []
            if self.memory_manager:
                memories = await self.memory_manager.retrieve(
                    user_id=task.get("user_id", "unknown"),
                    query=task.get("task", ""),
                    agent_id="ResearchAgent"
                )

            # Build prompt with context and memories
            system_prompt = """You are a research assistant. Your job is to gather information,
analyze it, and provide comprehensive summaries. Use past context when available.
Provide well-structured, detailed responses with key findings."""

            memory_context = "\n".join([
                f"Past memory: {m.get('memory', '')}"
                for m in memories[:3]
            ]) if memories else ""

            # Build prompt with context
            context_section = f'Context from previous interactions:\n{memory_context}' if memory_context else ''

            user_prompt = f"""Task: {task.get('task')}

{context_section}

Please provide a detailed research summary with key findings."""

            # Call Ops-Center LLM (routes through vLLM/OpenRouter/BYOK)
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model="default",  # Ops-Center will route to best available model
                temperature=0.7,
                user_id=task.get("user_id")  # For billing and BYOK lookup
            )

            result_content = response["choices"][0]["message"]["content"]

            result = {
                "agent": self.name,
                "task_id": task.get("task_id"),
                "status": "completed",
                "result": {
                    "summary": result_content,
                    "findings": self._extract_findings(result_content),
                    "recommendations": []
                },
                "tokens": {
                    "input": response["usage"]["prompt_tokens"],
                    "output": response["usage"]["completion_tokens"],
                    "total": response["usage"]["total_tokens"]
                },
                "model": response.get("model", "ops-center/default"),
                "provider": response.get("provider", "ops-center"),
                "llm_route": response.get("route", "ops-center/vllm"),
                "byok_used": response.get("byok_used", False),
                "next_agent": task.get("next_agent", "end")
            }

            # Store in memory
            await self.store_memory(
                f"research_{task.get('task_id')}",
                result
            )

            return result

        except Exception as e:
            logger.error(f"Research agent error: {e}")
            return {
                "agent": self.name,
                "task_id": task.get("task_id"),
                "status": "error",
                "error": str(e),
                "tokens": {"input": 0, "output": 0, "total": 0}
            }

    def _extract_findings(self, content: str) -> list:
        """Extract key findings from response"""
        # Simple extraction - look for bullet points or numbered lists
        findings = []
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                findings.append(line[1:].strip())
            elif len(line) > 0 and line[0].isdigit() and '.' in line[:3]:
                findings.append(line.split('.', 1)[1].strip())
        return findings[:5]  # Return top 5 findings
