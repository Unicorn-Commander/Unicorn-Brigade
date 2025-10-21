"""Code agent using Ops-Center LLM infrastructure"""

from typing import Dict, Any
from app.agents.base import BaseAgent
from app.llm.ops_center_client import OpsCenterLLMClient
import logging

logger = logging.getLogger(__name__)

class CodeAgent(BaseAgent):
    """Agent for code generation and analysis"""

    def __init__(self, memory_manager=None, llm_client=None):
        super().__init__("CodeAgent", memory_manager)
        self.llm_client = llm_client or OpsCenterLLMClient()

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code task via Ops-Center LLM"""
        logger.info(f"Code agent executing task: {task.get('task_id')}")

        try:
            # Get relevant memories
            memories = []
            if self.memory_manager:
                memories = await self.memory_manager.retrieve(
                    user_id=task.get("user_id", "unknown"),
                    query=task.get("task", ""),
                    agent_id="CodeAgent"
                )

            # Build prompt with context and memories
            system_prompt = """You are a code generation and analysis expert. Your job is to:
1. Generate clean, well-documented code
2. Analyze existing code for improvements
3. Provide best practices and optimizations
4. Consider past context when available

Always provide code with explanations."""

            memory_context = "\n".join([
                f"Past context: {m.get('memory', '')}"
                for m in memories[:3]
            ]) if memories else ""

            # Build prompt with context
            context_section = f'Previous work context:\n{memory_context}' if memory_context else ''

            user_prompt = f"""Task: {task.get('task')}

{context_section}

Please provide a complete solution with code and explanations."""

            # Call Ops-Center LLM (routes through vLLM/OpenRouter/BYOK)
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model="default",  # Ops-Center routes to best model
                temperature=0.3,  # Lower temperature for code generation
                user_id=task.get("user_id")
            )

            result_content = response["choices"][0]["message"]["content"]

            result = {
                "agent": self.name,
                "task_id": task.get("task_id"),
                "status": "completed",
                "result": {
                    "solution": result_content,
                    "code_blocks": self._extract_code_blocks(result_content),
                    "language": self._detect_language(result_content)
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
                f"code_{task.get('task_id')}",
                result
            )

            return result

        except Exception as e:
            logger.error(f"Code agent error: {e}")
            return {
                "agent": self.name,
                "task_id": task.get("task_id"),
                "status": "error",
                "error": str(e),
                "tokens": {"input": 0, "output": 0, "total": 0}
            }

    def _extract_code_blocks(self, content: str) -> list:
        """Extract code blocks from markdown"""
        code_blocks = []
        lines = content.split('\n')
        in_code_block = False
        current_block = []
        current_lang = ""

        for line in lines:
            if line.strip().startswith('```'):
                if in_code_block:
                    # End of code block
                    code_blocks.append({
                        "language": current_lang,
                        "code": '\n'.join(current_block)
                    })
                    current_block = []
                    current_lang = ""
                    in_code_block = False
                else:
                    # Start of code block
                    current_lang = line.strip()[3:].strip()
                    in_code_block = True
            elif in_code_block:
                current_block.append(line)

        return code_blocks

    def _detect_language(self, content: str) -> str:
        """Detect primary programming language"""
        content_lower = content.lower()
        if 'python' in content_lower or 'def ' in content or 'import ' in content:
            return "python"
        elif 'javascript' in content_lower or 'typescript' in content_lower or 'const ' in content or 'let ' in content:
            return "javascript"
        elif 'java' in content_lower and 'public class' in content:
            return "java"
        elif 'rust' in content_lower or 'fn ' in content:
            return "rust"
        elif 'go' in content_lower or 'func ' in content:
            return "go"
        return "unknown"
