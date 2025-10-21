"""Analysis agent using Ops-Center LLM infrastructure"""

from typing import Dict, Any
from app.agents.base import BaseAgent
from app.llm.ops_center_client import OpsCenterLLMClient
import logging

logger = logging.getLogger(__name__)

class AnalysisAgent(BaseAgent):
    """Agent for data analysis and insights"""

    def __init__(self, memory_manager=None, llm_client=None):
        super().__init__("AnalysisAgent", memory_manager)
        self.llm_client = llm_client or OpsCenterLLMClient()

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute analysis task via Ops-Center LLM"""
        logger.info(f"Analysis agent executing task: {task.get('task_id')}")

        try:
            # Get relevant memories
            memories = []
            if self.memory_manager:
                memories = await self.memory_manager.retrieve(
                    user_id=task.get("user_id", "unknown"),
                    query=task.get("task", ""),
                    agent_id="AnalysisAgent"
                )

            # Build prompt with context and memories
            system_prompt = """You are a data analysis expert. Your job is to:
1. Analyze data and extract insights
2. Identify patterns and trends
3. Provide actionable recommendations
4. Create structured reports

Always provide clear, data-driven conclusions."""

            memory_context = "\n".join([
                f"Historical data: {m.get('memory', '')}"
                for m in memories[:3]
            ]) if memories else ""

            # Build prompt with context
            context_section = f'Previous analysis context:\n{memory_context}' if memory_context else ''

            user_prompt = f"""Task: {task.get('task')}

{context_section}

Please provide a detailed analysis with insights and recommendations."""

            # Call Ops-Center LLM (routes through vLLM/OpenRouter/BYOK)
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model="default",  # Ops-Center routes to best model
                temperature=0.5,
                user_id=task.get("user_id")
            )

            result_content = response["choices"][0]["message"]["content"]

            result = {
                "agent": self.name,
                "task_id": task.get("task_id"),
                "status": "completed",
                "result": {
                    "analysis": result_content,
                    "insights": self._extract_insights(result_content),
                    "recommendations": self._extract_recommendations(result_content)
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
                f"analysis_{task.get('task_id')}",
                result
            )

            return result

        except Exception as e:
            logger.error(f"Analysis agent error: {e}")
            return {
                "agent": self.name,
                "task_id": task.get("task_id"),
                "status": "error",
                "error": str(e),
                "tokens": {"input": 0, "output": 0, "total": 0}
            }

    def _extract_insights(self, content: str) -> list:
        """Extract key insights from analysis"""
        insights = []
        lines = content.split('\n')

        for line in lines:
            line = line.strip()
            # Look for insight indicators
            if any(keyword in line.lower() for keyword in ['insight:', 'key finding:', 'observation:', 'notably']):
                insights.append(line)
            elif line.startswith('-') or line.startswith('•') or line.startswith('*'):
                if any(keyword in line.lower() for keyword in ['shows', 'indicates', 'suggests', 'reveals']):
                    insights.append(line[1:].strip())

        return insights[:5]  # Return top 5 insights

    def _extract_recommendations(self, content: str) -> list:
        """Extract recommendations from analysis"""
        recommendations = []
        lines = content.split('\n')

        for line in lines:
            line = line.strip()
            # Look for recommendation indicators
            if any(keyword in line.lower() for keyword in ['recommend:', 'suggestion:', 'should', 'consider']):
                recommendations.append(line)
            elif line.startswith('-') or line.startswith('•') or line.startswith('*'):
                if any(keyword in line.lower() for keyword in ['recommend', 'suggest', 'should', 'could']):
                    recommendations.append(line[1:].strip())

        return recommendations[:5]  # Return top 5 recommendations
