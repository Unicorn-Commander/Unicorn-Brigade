"""
Meta Agent - Dynamic Agent Creation (Clawdbot-style)

Capabilities:
- Create new agents from descriptions
- Generate workflow definitions dynamically
- Self-modifying execution loops
- Agent composition and chaining
"""

from typing import Dict, Any, List, Optional, Callable
from pydantic import BaseModel, Field
from datetime import datetime
import json
import logging
import uuid

from app.engine.models import (
    Task, WorkflowPlan, WorkflowStep, ToolType, WorkerType, RiskLevel
)
from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)


class AgentDefinition(BaseModel):
    """Definition for a dynamically created agent"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    description: str
    capabilities: List[str] = Field(default_factory=list)
    system_prompt: str
    tools: List[str] = Field(default_factory=list)
    model: str = "default"
    temperature: float = 0.7
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "meta_agent"
    parent_agent: Optional[str] = None  # If spawned by another agent


class AgentFactory(BaseModel):
    """Factory for creating agents dynamically"""
    agents: Dict[str, AgentDefinition] = Field(default_factory=dict)
    templates: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


AGENT_CREATION_PROMPT = """You are an AI agent factory. Your task is to design new AI agents.

Given a description of what the agent should do, create a complete agent definition including:
1. Name: A descriptive name
2. Description: What the agent does
3. Capabilities: List of specific capabilities
4. System Prompt: The instructions for the agent
5. Tools: Which tools it needs from built-in tools and MCP servers
6. Recommended model and temperature

## Available Tools

**Built-in Tools (23)**:
- web_search, http_request, calculator, shell, memory, json, datetime
- email, file, code, text, image, database, notify, qrcode, agentic_rag
- browser, code_sandbox, screenshot, pdf_extract, doc_generate, data_analyze, url_preview, knowledge_graph

**MCP Servers (11 real, npx-runnable; tools discovered at runtime)**:
- GitHub, Filesystem, PostgreSQL, Playwright, Slack, Memory,
  Brave Search, Google Drive, Puppeteer, Stripe, Notion
- Monitoring: Sentry
- Search: Brave Search
- Storage: Google Drive, Filesystem
- Automation: Zapier, Make
- Memory: Built-in memory MCP

When selecting tools, consider:
1. Start with built-in tools for common operations (search, email, calculations)
2. Add MCP server tools for specialized integrations (GitHub, Slack, Stripe, etc.)
3. Use the most specific tools for the agent's domain

Output as JSON:
```json
{
    "name": "AgentName",
    "description": "What the agent does",
    "capabilities": ["capability1", "capability2"],
    "system_prompt": "Detailed instructions for the agent. Include information about available MCP tools if relevant to the agent's domain.",
    "tools": ["web_search", "github", "slack"],
    "model": "default",
    "temperature": 0.7
}
```

Be specific and detailed in the system prompt. Include guardrails and constraints. When the agent will use MCP servers, mention the relevant MCP tools in the system prompt so the agent knows how to use them."""


class MetaAgent:
    """
    Meta-agent for dynamic agent creation and workflow generation.

    This enables Clawdbot-style capabilities:
    - Create new agents from natural language descriptions
    - Generate workflows dynamically
    - Spawn sub-agents for complex tasks
    - Self-modifying execution loops
    """

    def __init__(
        self,
        llm_client: Optional[OpsCenterLLMClient] = None,
        max_spawn_depth: int = 3,
    ):
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.max_spawn_depth = max_spawn_depth
        self.factory = AgentFactory()
        self.execution_history: List[Dict[str, Any]] = []

        logger.info("MetaAgent initialized")

    async def create_agent(
        self,
        description: str,
        user_id: str,
        parent_agent: Optional[str] = None,
    ) -> AgentDefinition:
        """
        Create a new agent from a natural language description.

        Args:
            description: What the agent should do
            user_id: Who is creating the agent
            parent_agent: If spawned by another agent

        Returns:
            The created AgentDefinition
        """
        logger.info(f"Creating agent from description: {description[:100]}...")

        try:
            # Call LLM to design the agent
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": AGENT_CREATION_PROMPT},
                    {"role": "user", "content": f"Create an agent that: {description}"},
                ],
                model="default",
                temperature=0.7,
                user_id=user_id,
            )

            content = response["choices"][0]["message"]["content"]

            # Parse JSON from response
            agent_data = self._parse_agent_json(content)

            if not agent_data:
                raise ValueError("Could not parse agent definition from LLM response")

            # Create agent definition
            agent = AgentDefinition(
                name=agent_data.get("name", "CustomAgent"),
                description=agent_data.get("description", description),
                capabilities=agent_data.get("capabilities", []),
                system_prompt=agent_data.get("system_prompt", ""),
                tools=agent_data.get("tools", ["llm"]),
                model=agent_data.get("model", "default"),
                temperature=agent_data.get("temperature", 0.7),
                created_by=user_id,
                parent_agent=parent_agent,
            )

            # Store in factory
            self.factory.agents[agent.id] = agent

            logger.info(f"Created agent: {agent.name} (id={agent.id})")
            return agent

        except Exception as e:
            logger.error(f"Error creating agent: {e}")
            raise

    async def generate_workflow(
        self,
        task: Task,
        user_id: str,
        max_steps: int = 10,
    ) -> WorkflowPlan:
        """
        Dynamically generate a workflow for a task.

        Unlike the static YAML workflows, this creates
        workflows on-the-fly based on the task.
        """
        logger.info(f"Generating workflow for: {task.content[:100]}...")

        workflow_prompt = f"""Design a workflow to accomplish this task:

Task: {task.content}

Create a step-by-step plan with:
- Clear actions for each step
- Required tools (llm, shell, browser, api, filesystem, database)
- Dependencies between steps
- Risk level for each step (low, medium, high)
- Whether approval is needed

Output as JSON:
```json
{{
    "name": "WorkflowName",
    "objective": "What this workflow accomplishes",
    "steps": [
        {{
            "id": 1,
            "action": "What to do",
            "tool": "llm",
            "inputs": ["input1"],
            "outputs": ["output1"],
            "risk": "low",
            "approval_required": false
        }}
    ]
}}
```

Maximum {max_steps} steps. Be specific and actionable."""

        try:
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a workflow designer."},
                    {"role": "user", "content": workflow_prompt},
                ],
                model="default",
                temperature=0.5,
                user_id=user_id,
            )

            content = response["choices"][0]["message"]["content"]
            workflow_data = self._parse_workflow_json(content)

            if not workflow_data:
                # Fallback to simple workflow
                return self._create_simple_workflow(task)

            # Convert to WorkflowPlan
            return self._build_workflow_plan(workflow_data, task.id)

        except Exception as e:
            logger.error(f"Error generating workflow: {e}")
            return self._create_simple_workflow(task)

    async def spawn_sub_agent(
        self,
        parent_task: Task,
        sub_task_description: str,
        parent_agent_id: str,
        depth: int = 1,
    ) -> Optional[AgentDefinition]:
        """
        Spawn a sub-agent for a specific sub-task.

        This enables recursive agent spawning for complex tasks.
        """
        if depth > self.max_spawn_depth:
            logger.warning(f"Max spawn depth ({self.max_spawn_depth}) reached")
            return None

        logger.info(f"Spawning sub-agent (depth={depth}): {sub_task_description[:50]}...")

        return await self.create_agent(
            description=sub_task_description,
            user_id=parent_task.user_id,
            parent_agent=parent_agent_id,
        )

    async def execute_with_reflection(
        self,
        task: Task,
        executor: Callable,
        max_iterations: int = 3,
    ) -> Dict[str, Any]:
        """
        Execute a task with self-reflection and improvement loops.

        This is the Clawdbot-style self-modifying execution:
        1. Execute the task
        2. Reflect on the result
        3. If needed, modify approach and retry
        """
        logger.info(f"Starting reflective execution for: {task.content[:50]}...")

        best_result = None
        best_confidence = 0.0

        for iteration in range(max_iterations):
            logger.info(f"Iteration {iteration + 1}/{max_iterations}")

            # Execute
            result = await executor(task)

            # Reflect
            reflection = await self._reflect_on_result(task, result, iteration)

            # Track best result
            confidence = reflection.get("confidence", 0.5)
            if confidence > best_confidence:
                best_confidence = confidence
                best_result = result

            # Check if satisfied
            if reflection.get("satisfied", False) or confidence > 0.9:
                logger.info(f"Satisfied at iteration {iteration + 1}")
                break

            # Modify task based on reflection
            if reflection.get("modified_task"):
                task = Task(
                    content=reflection["modified_task"],
                    user_id=task.user_id,
                    context={
                        **task.context,
                        "previous_attempt": result,
                        "reflection": reflection,
                    },
                )

            # Record history
            self.execution_history.append({
                "iteration": iteration,
                "task": task.content[:100],
                "confidence": confidence,
                "reflection": reflection,
                "timestamp": datetime.utcnow().isoformat(),
            })

        return best_result or result

    async def _reflect_on_result(
        self,
        task: Task,
        result: Dict[str, Any],
        iteration: int,
    ) -> Dict[str, Any]:
        """
        Reflect on execution result and suggest improvements.
        """
        reflection_prompt = f"""Reflect on this task execution:

Task: {task.content}

Result: {str(result)[:1000]}

Iteration: {iteration + 1}

Evaluate:
1. Did the result accomplish the task? (0-1 confidence)
2. What could be improved?
3. Should we try a different approach?
4. Is the result satisfactory?

Output JSON:
```json
{{
    "confidence": 0.8,
    "satisfied": true,
    "improvements": ["suggestion1"],
    "different_approach": false,
    "modified_task": null
}}
```"""

        try:
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a task execution evaluator."},
                    {"role": "user", "content": reflection_prompt},
                ],
                model="default",
                temperature=0.3,
                user_id=task.user_id,
            )

            content = response["choices"][0]["message"]["content"]
            return self._parse_json(content) or {
                "confidence": 0.5,
                "satisfied": False,
            }

        except Exception as e:
            logger.error(f"Reflection error: {e}")
            return {"confidence": 0.5, "satisfied": True}

    def _parse_agent_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse agent JSON from LLM response"""
        return self._parse_json(content)

    def _parse_workflow_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse workflow JSON from LLM response"""
        return self._parse_json(content)

    def _parse_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from content, handling markdown code blocks and escape issues"""
        import re

        def try_parse(json_str: str) -> Optional[Dict[str, Any]]:
            """Try to parse JSON, with fallback for unescaped newlines"""
            # First try direct parse
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            # Try fixing unescaped newlines in string values
            # This handles LLM output with literal newlines in JSON strings
            try:
                # Replace literal newlines inside strings with \n
                # Match content between quotes and escape newlines
                fixed = re.sub(
                    r'("(?:[^"\\]|\\.)*")',
                    lambda m: m.group(1).replace('\n', '\\n').replace('\t', '\\t'),
                    json_str
                )
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

            # Try more aggressive cleanup - remove nested code blocks
            try:
                # Remove any nested ``` blocks inside the JSON
                cleaned = re.sub(r'```[\w]*\n[\s\S]*?```', '"[code block removed]"', json_str)
                # Replace remaining problematic characters
                cleaned = cleaned.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

            return None

        # Try to find JSON in code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            result = try_parse(json_match.group(1).strip())
            if result:
                return result

        # Try to parse entire content
        result = try_parse(content)
        if result:
            return result

        # Try to find JSON object
        brace_match = re.search(r'\{[\s\S]*\}', content)
        if brace_match:
            result = try_parse(brace_match.group())
            if result:
                return result

        logger.warning(f"Could not parse JSON from response: {content[:200]}")
        return None

    def _create_simple_workflow(self, task: Task) -> WorkflowPlan:
        """Create a simple single-step workflow as fallback"""
        return WorkflowPlan(
            name="simple_task",
            objective=task.content,
            steps=[
                WorkflowStep(
                    id=1,
                    action=task.content,
                    tool=ToolType.LLM,
                    worker=WorkerType.RESEARCH,
                    inputs=[],
                    outputs=["result"],
                    risk=RiskLevel.LOW,
                    approval_required=False,
                )
            ],
            total_risk=RiskLevel.LOW,
        )

    def _build_workflow_plan(
        self,
        data: Dict[str, Any],
        task_id: str,
    ) -> WorkflowPlan:
        """Build WorkflowPlan from parsed JSON"""
        tool_map = {
            "llm": ToolType.LLM,
            "shell": ToolType.SHELL,
            "browser": ToolType.BROWSER,
            "api": ToolType.API,
            "filesystem": ToolType.FILESYSTEM,
            "database": ToolType.DATABASE,
            "python": ToolType.PYTHON,
        }

        risk_map = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL,
        }

        steps = []
        for step_data in data.get("steps", []):
            tool_str = step_data.get("tool", "llm").lower()
            risk_str = step_data.get("risk", "low").lower()

            step = WorkflowStep(
                id=step_data.get("id", len(steps) + 1),
                action=step_data.get("action", "Execute task"),
                tool=tool_map.get(tool_str, ToolType.LLM),
                inputs=step_data.get("inputs", []),
                outputs=step_data.get("outputs", []),
                risk=risk_map.get(risk_str, RiskLevel.LOW),
                approval_required=step_data.get("approval_required", False),
                timeout_seconds=step_data.get("timeout", 60),
            )
            steps.append(step)

        # Calculate total risk
        max_risk = RiskLevel.LOW
        requires_approval = False
        for step in steps:
            if step.risk == RiskLevel.HIGH or step.risk == RiskLevel.CRITICAL:
                max_risk = step.risk
            elif step.risk == RiskLevel.MEDIUM and max_risk == RiskLevel.LOW:
                max_risk = RiskLevel.MEDIUM
            if step.approval_required:
                requires_approval = True

        return WorkflowPlan(
            name=data.get("name", f"workflow_{task_id}"),
            objective=data.get("objective", ""),
            steps=steps,
            total_risk=max_risk,
            requires_approval=requires_approval,
        )

    def get_agent(self, agent_id: str) -> Optional[AgentDefinition]:
        """Get a created agent by ID"""
        return self.factory.agents.get(agent_id)

    def list_agents(self) -> List[AgentDefinition]:
        """List all created agents"""
        return list(self.factory.agents.values())

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Get execution history with reflections"""
        return self.execution_history
