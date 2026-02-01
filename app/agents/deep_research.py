"""
Deep Research Agent - Multi-step autonomous research with web search and synthesis.

This agent performs comprehensive research by:
1. Planning multiple search queries to cover different angles
2. Executing web searches using the existing web_search tool
3. Synthesizing findings into a comprehensive report with citations
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from app.agents.base import BaseAgent
from app.llm.ops_center_client import OpsCenterLLMClient, ToolDefinition, ToolParameter
from app.llm.builtin_tools import web_search_handler

logger = logging.getLogger(__name__)


class ResearchDepth(str, Enum):
    """Research depth configuration"""
    QUICK = "quick"       # 2-3 queries, fast synthesis
    MEDIUM = "medium"     # 4-6 queries, balanced depth
    THOROUGH = "thorough" # 8-12 queries, comprehensive analysis


@dataclass
class SearchResult:
    """Individual search result with metadata"""
    query: str
    title: str
    url: str
    snippet: str
    provider: str = "serper"


@dataclass
class ResearchSession:
    """Tracks state of a research session"""
    session_id: str
    topic: str
    depth: ResearchDepth
    status: str = "planning"
    queries_planned: List[str] = field(default_factory=list)
    queries_executed: List[str] = field(default_factory=list)
    search_results: List[SearchResult] = field(default_factory=list)
    synthesis: str = ""
    sources: List[Dict[str, str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


# In-memory session storage (optional Zep integration can be added)
_research_sessions: Dict[str, ResearchSession] = {}


class DeepResearchAgent(BaseAgent):
    """
    Deep Research Agent that performs multi-step autonomous research.

    Features:
    - Plans multiple search queries based on topic
    - Executes searches in parallel for efficiency
    - Synthesizes findings into comprehensive reports
    - Includes proper source citations with URLs
    - Configurable depth (quick/medium/thorough)
    """

    # Query count per depth level
    DEPTH_CONFIG = {
        ResearchDepth.QUICK: {"min_queries": 2, "max_queries": 3, "results_per_query": 3},
        ResearchDepth.MEDIUM: {"min_queries": 4, "max_queries": 6, "results_per_query": 5},
        ResearchDepth.THOROUGH: {"min_queries": 8, "max_queries": 12, "results_per_query": 7},
    }

    def __init__(
        self,
        memory_manager=None,
        llm_client: Optional[OpsCenterLLMClient] = None,
        model: str = "openai/gpt-4o",
    ):
        super().__init__("DeepResearchAgent", memory_manager)
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.model = model

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a deep research task.

        Args:
            task: Dict containing:
                - topic: The research topic/question
                - depth: "quick", "medium", or "thorough"
                - user_id: User ID for billing/tracking

        Returns:
            Research results with report, sources, and queries executed
        """
        topic = task.get("topic", task.get("task", ""))
        depth_str = task.get("depth", "medium")
        user_id = task.get("user_id", "anonymous")

        try:
            depth = ResearchDepth(depth_str.lower())
        except ValueError:
            depth = ResearchDepth.MEDIUM

        logger.info(f"Starting deep research on: '{topic}' with depth: {depth.value}")

        # Create session
        session = ResearchSession(
            session_id=str(uuid.uuid4()),
            topic=topic,
            depth=depth,
        )
        _research_sessions[session.session_id] = session

        try:
            # Phase 1: Plan search queries
            session.status = "planning"
            queries = await self._plan_queries(topic, depth, user_id)
            session.queries_planned = queries
            logger.info(f"Planned {len(queries)} queries for research")

            # Phase 2: Execute searches
            session.status = "searching"
            search_results = await self._execute_searches(queries, depth)
            session.search_results = search_results
            session.queries_executed = queries
            logger.info(f"Collected {len(search_results)} search results")

            # Phase 3: Synthesize findings
            session.status = "synthesizing"
            report, sources = await self._synthesize_findings(topic, search_results, user_id)
            session.synthesis = report
            session.sources = sources

            # Complete session
            session.status = "completed"
            session.completed_at = datetime.utcnow()

            # Store in memory if available
            if self.memory_manager:
                await self.store_memory(
                    f"research_{session.session_id}",
                    {
                        "topic": topic,
                        "report": report[:500],  # Truncate for memory
                        "source_count": len(sources),
                        "user_id": user_id,
                    }
                )

            return {
                "agent": self.name,
                "session_id": session.session_id,
                "status": "completed",
                "topic": topic,
                "depth": depth.value,
                "report": report,
                "sources": sources,
                "queries_executed": session.queries_executed,
                "result_count": len(search_results),
            }

        except Exception as e:
            logger.error(f"Deep research error: {e}")
            session.status = "error"
            session.error = str(e)

            return {
                "agent": self.name,
                "session_id": session.session_id,
                "status": "error",
                "topic": topic,
                "error": str(e),
                "queries_executed": session.queries_executed,
            }

    async def _plan_queries(
        self, topic: str, depth: ResearchDepth, user_id: str
    ) -> List[str]:
        """
        Use LLM to plan diverse search queries covering different angles.
        """
        config = self.DEPTH_CONFIG[depth]
        min_q = config["min_queries"]
        max_q = config["max_queries"]

        system_prompt = """You are a research planning assistant. Your job is to generate effective
search queries that will help gather comprehensive information on a topic.

Generate diverse queries that:
1. Cover different aspects of the topic
2. Include different perspectives (pros/cons, history/future, etc.)
3. Target specific facts, statistics, and expert opinions
4. Use precise search terms for better results

Output ONLY a JSON array of search query strings, nothing else."""

        user_prompt = f"""Generate {min_q}-{max_q} search queries to thoroughly research this topic:

Topic: {topic}

Output format: ["query 1", "query 2", "query 3", ...]"""

        try:
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=self.model,
                temperature=0.7,
                max_tokens=1000,
                user_id=user_id,
            )

            content = self.llm_client.get_response_content(response)

            # Parse JSON array from response
            import json

            # Handle potential markdown code blocks
            if "```" in content:
                # Extract content between code blocks
                start = content.find("[")
                end = content.rfind("]") + 1
                content = content[start:end]

            queries = json.loads(content)

            # Ensure we have the right number of queries
            if len(queries) < min_q:
                # Add the original topic as a fallback
                queries.append(topic)

            return queries[:max_q]

        except Exception as e:
            logger.warning(f"Query planning error, using fallback: {e}")
            # Fallback: generate basic queries
            return [
                topic,
                f"{topic} explained",
                f"{topic} latest news",
                f"{topic} research studies",
            ][:max_q]

    async def _execute_searches(
        self, queries: List[str], depth: ResearchDepth
    ) -> List[SearchResult]:
        """
        Execute all search queries in parallel and collect results.
        """
        config = self.DEPTH_CONFIG[depth]
        results_per_query = config["results_per_query"]

        # Execute searches in parallel
        async def search_one(query: str) -> List[SearchResult]:
            try:
                result = await web_search_handler(
                    query=query,
                    num_results=results_per_query,
                )

                if not result.get("success"):
                    logger.warning(f"Search failed for query '{query}': {result.get('error')}")
                    return []

                search_results = []
                for item in result.get("results", []):
                    search_results.append(SearchResult(
                        query=query,
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("snippet", ""),
                        provider=result.get("provider", "serper"),
                    ))

                return search_results

            except Exception as e:
                logger.error(f"Search error for '{query}': {e}")
                return []

        # Run all searches concurrently
        tasks = [search_one(q) for q in queries]
        results_lists = await asyncio.gather(*tasks)

        # Flatten results
        all_results = []
        for results in results_lists:
            all_results.extend(results)

        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for r in all_results:
            if r.url and r.url not in seen_urls:
                seen_urls.add(r.url)
                unique_results.append(r)

        return unique_results

    async def _synthesize_findings(
        self, topic: str, results: List[SearchResult], user_id: str
    ) -> tuple[str, List[Dict[str, str]]]:
        """
        Use LLM to synthesize search results into a comprehensive report.
        """
        # Build context from search results
        context_parts = []
        sources = []

        for i, result in enumerate(results, 1):
            context_parts.append(f"""
Source [{i}]: {result.title}
URL: {result.url}
Content: {result.snippet}
""")
            sources.append({
                "id": str(i),
                "title": result.title,
                "url": result.url,
                "query": result.query,
            })

        context = "\n".join(context_parts)

        system_prompt = """You are a research synthesis expert. Your task is to analyze multiple
sources and create a comprehensive, well-structured research report.

Guidelines:
1. Synthesize information from multiple sources into a coherent narrative
2. Highlight key findings, trends, and insights
3. Note any conflicting information or debates
4. Include specific facts, statistics, and quotes when available
5. Use proper citations [1], [2], etc. referencing the source numbers
6. Structure the report with clear sections and headings
7. Provide a balanced perspective covering multiple viewpoints
8. End with key takeaways or conclusions

Write in a professional, informative tone."""

        user_prompt = f"""Research Topic: {topic}

Based on the following {len(results)} sources, create a comprehensive research report:

{context}

Create a detailed research report with:
1. Executive Summary (2-3 sentences)
2. Key Findings (main discoveries with citations)
3. Analysis & Discussion (deeper insights)
4. Conclusion & Recommendations

Include citations like [1], [2] when referencing specific sources."""

        try:
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=self.model,
                temperature=0.5,
                max_tokens=3000,
                user_id=user_id,
            )

            report = self.llm_client.get_response_content(response)
            return report, sources

        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            # Return basic report on error
            basic_report = f"""# Research Report: {topic}

## Summary
Research was conducted but synthesis encountered an error.

## Sources Found ({len(results)} results)
"""
            for i, result in enumerate(results[:5], 1):
                basic_report += f"\n{i}. [{result.title}]({result.url})\n   {result.snippet[:200]}...\n"

            return basic_report, sources

    async def research(
        self,
        topic: str,
        depth: str = "medium",
        user_id: str = "anonymous",
    ) -> Dict[str, Any]:
        """
        Convenience method to execute research directly.

        Args:
            topic: Research topic or question
            depth: "quick", "medium", or "thorough"
            user_id: User ID for billing

        Returns:
            Research results
        """
        return await self.execute({
            "topic": topic,
            "depth": depth,
            "user_id": user_id,
        })

    @staticmethod
    def get_session(session_id: str) -> Optional[ResearchSession]:
        """Get a research session by ID"""
        return _research_sessions.get(session_id)

    @staticmethod
    def list_sessions() -> List[Dict[str, Any]]:
        """List all research sessions"""
        return [
            {
                "session_id": s.session_id,
                "topic": s.topic,
                "depth": s.depth.value,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            }
            for s in _research_sessions.values()
        ]


# Create tool definition for agents that want to use deep research as a tool
DEEP_RESEARCH_TOOL = ToolDefinition(
    name="deep_research",
    description="Perform comprehensive multi-step research on a topic. Plans multiple search queries, executes them, and synthesizes findings into a report with citations.",
    parameters=[
        ToolParameter(
            name="topic",
            type="string",
            description="The research topic or question to investigate",
            required=True,
        ),
        ToolParameter(
            name="depth",
            type="string",
            description="Research depth: 'quick' (2-3 queries), 'medium' (4-6 queries), or 'thorough' (8-12 queries)",
            required=False,
            default="medium",
            enum=["quick", "medium", "thorough"],
        ),
    ],
    handler=None,  # Set handler dynamically when needed
)


async def deep_research_handler(
    topic: str,
    depth: str = "medium",
    user_id: str = "anonymous",
) -> Dict[str, Any]:
    """
    Handler function for the deep_research tool.

    Can be used standalone or registered as a tool handler.
    """
    agent = DeepResearchAgent()
    result = await agent.research(topic=topic, depth=depth, user_id=user_id)
    return result


# Set the handler on the tool definition
DEEP_RESEARCH_TOOL.handler = deep_research_handler
