"""
Example Workflows for Unicorn Brigade

Demonstrates the advanced workflow capabilities:
- Control flow (conditionals, loops, parallel)
- Multi-agent collaboration
- Resilience patterns
- Observability integration

These examples serve as templates for building complex workflows.
"""

import asyncio
import json
from typing import Dict, Any

# Example workflow definitions


# ============== Basic Workflow ==============

BASIC_RESEARCH_WORKFLOW = {
    "name": "basic_research",
    "objective": "Research a topic and produce a summary",
    "assumptions": [
        "Topic is provided in context",
        "Web search is available",
    ],
    "steps": [
        {
            "id": 1,
            "action": "Search the web for information about the topic",
            "tool": "api",
            "inputs": ["topic"],
            "outputs": ["search_results"],
            "success_criteria": ["Found at least 3 relevant sources"],
        },
        {
            "id": 2,
            "action": "Analyze and synthesize the search results",
            "tool": "llm",
            "inputs": ["search_results"],
            "outputs": ["analysis"],
            "stdin_from": "$step1.output",
            "success_criteria": ["Analysis covers key points"],
        },
        {
            "id": 3,
            "action": "Write a summary report",
            "tool": "llm",
            "inputs": ["analysis"],
            "outputs": ["report.md"],
            "stdin_from": "$step2.output",
            "success_criteria": ["Report is well-structured"],
        },
    ],
}


# ============== Conditional Workflow ==============

CONDITIONAL_DATA_PROCESSING = {
    "name": "conditional_data_processing",
    "objective": "Process data based on its type",
    "steps": [
        {
            "id": 1,
            "action": "Analyze input data to determine type",
            "tool": "llm",
            "inputs": ["data"],
            "outputs": ["data_type"],
            "success_criteria": ["Data type identified"],
        },
        {
            "id": 2,
            "type": "conditional",
            "condition": {
                "left": "$step1.output",
                "op": "contains",
                "right": "json",
            },
            "then_steps": [
                {
                    "id": 3,
                    "action": "Parse and validate JSON data",
                    "tool": "python",
                    "inputs": ["data"],
                    "outputs": ["parsed_data"],
                },
                {
                    "id": 4,
                    "action": "Transform JSON to normalized format",
                    "tool": "python",
                    "inputs": ["parsed_data"],
                    "outputs": ["normalized_data"],
                },
            ],
            "else_steps": [
                {
                    "id": 3,
                    "action": "Parse CSV data",
                    "tool": "python",
                    "inputs": ["data"],
                    "outputs": ["parsed_data"],
                },
                {
                    "id": 4,
                    "action": "Convert CSV to JSON format",
                    "tool": "python",
                    "inputs": ["parsed_data"],
                    "outputs": ["normalized_data"],
                },
            ],
        },
        {
            "id": 5,
            "action": "Generate data quality report",
            "tool": "llm",
            "inputs": ["normalized_data"],
            "outputs": ["quality_report"],
        },
    ],
}


# ============== Loop Workflow ==============

BATCH_PROCESSING_WORKFLOW = {
    "name": "batch_processing",
    "objective": "Process multiple items in a batch",
    "steps": [
        {
            "id": 1,
            "action": "Load batch items from input",
            "tool": "llm",
            "inputs": ["batch_input"],
            "outputs": ["items"],
        },
        {
            "id": 2,
            "type": "loop",
            "loop_type": "for",
            "items": "$step1.output",
            "item_var": "current_item",
            "index_var": "item_index",
            "max_iterations": 50,
            "body_steps": [
                {
                    "id": 3,
                    "action": "Process individual item: ${current_item}",
                    "tool": "llm",
                    "inputs": ["current_item"],
                    "outputs": ["processed_item"],
                },
                {
                    "id": 4,
                    "action": "Validate processed item",
                    "tool": "llm",
                    "inputs": ["processed_item"],
                    "outputs": ["validation_result"],
                },
            ],
        },
        {
            "id": 5,
            "action": "Aggregate all processed results",
            "tool": "llm",
            "inputs": ["all_processed_items"],
            "outputs": ["batch_result"],
        },
    ],
}


# ============== Parallel Workflow ==============

MULTI_SOURCE_RESEARCH = {
    "name": "multi_source_research",
    "objective": "Research a topic from multiple sources in parallel",
    "steps": [
        {
            "id": 1,
            "action": "Identify research topic and key questions",
            "tool": "llm",
            "inputs": ["topic"],
            "outputs": ["research_plan"],
        },
        {
            "id": 2,
            "type": "parallel",
            "wait_for": "all",
            "branches": [
                # Branch 1: Academic sources
                [
                    {
                        "id": 3,
                        "action": "Search academic papers on the topic",
                        "tool": "api",
                        "inputs": ["research_plan"],
                        "outputs": ["academic_results"],
                    },
                    {
                        "id": 4,
                        "action": "Summarize academic findings",
                        "tool": "llm",
                        "inputs": ["academic_results"],
                        "outputs": ["academic_summary"],
                    },
                ],
                # Branch 2: News sources
                [
                    {
                        "id": 5,
                        "action": "Search recent news articles",
                        "tool": "api",
                        "inputs": ["research_plan"],
                        "outputs": ["news_results"],
                    },
                    {
                        "id": 6,
                        "action": "Summarize news findings",
                        "tool": "llm",
                        "inputs": ["news_results"],
                        "outputs": ["news_summary"],
                    },
                ],
                # Branch 3: Industry reports
                [
                    {
                        "id": 7,
                        "action": "Search industry reports",
                        "tool": "api",
                        "inputs": ["research_plan"],
                        "outputs": ["industry_results"],
                    },
                    {
                        "id": 8,
                        "action": "Summarize industry findings",
                        "tool": "llm",
                        "inputs": ["industry_results"],
                        "outputs": ["industry_summary"],
                    },
                ],
            ],
        },
        {
            "id": 9,
            "action": "Synthesize findings from all sources",
            "tool": "llm",
            "inputs": ["academic_summary", "news_summary", "industry_summary"],
            "outputs": ["comprehensive_report"],
        },
    ],
}


# ============== Branch/Switch Workflow ==============

TASK_ROUTING_WORKFLOW = {
    "name": "task_routing",
    "objective": "Route tasks to appropriate handlers based on type",
    "steps": [
        {
            "id": 1,
            "action": "Classify the incoming task",
            "tool": "llm",
            "inputs": ["task_description"],
            "outputs": ["task_type"],
            "success_criteria": ["Returns: code, research, analysis, or support"],
        },
        {
            "id": 2,
            "type": "branch",
            "value": "$step1.output",
            "cases": {
                "code": [
                    {
                        "id": 3,
                        "action": "Generate code solution",
                        "tool": "llm",
                        "inputs": ["task_description"],
                        "outputs": ["code_solution"],
                    },
                    {
                        "id": 4,
                        "action": "Review and test code",
                        "tool": "python",
                        "inputs": ["code_solution"],
                        "outputs": ["tested_code"],
                    },
                ],
                "research": [
                    {
                        "id": 3,
                        "action": "Conduct research",
                        "tool": "api",
                        "inputs": ["task_description"],
                        "outputs": ["research_results"],
                    },
                    {
                        "id": 4,
                        "action": "Compile research report",
                        "tool": "llm",
                        "inputs": ["research_results"],
                        "outputs": ["research_report"],
                    },
                ],
                "analysis": [
                    {
                        "id": 3,
                        "action": "Analyze data",
                        "tool": "python",
                        "inputs": ["task_description"],
                        "outputs": ["analysis_results"],
                    },
                    {
                        "id": 4,
                        "action": "Generate analysis report",
                        "tool": "llm",
                        "inputs": ["analysis_results"],
                        "outputs": ["analysis_report"],
                    },
                ],
            },
            "default": [
                {
                    "id": 3,
                    "action": "Handle with general assistant",
                    "tool": "llm",
                    "inputs": ["task_description"],
                    "outputs": ["response"],
                },
            ],
        },
    ],
}


# ============== Multi-Agent Collaboration Workflow ==============

CODE_REVIEW_WORKFLOW = {
    "name": "code_review_collaboration",
    "objective": "Comprehensive code review using multiple specialist agents",
    "collaboration_pattern": "supervisor",
    "agents": {
        "supervisor": {
            "name": "Code Review Lead",
            "role": "supervisor",
            "system_prompt": """You are a senior code review lead. Coordinate the review process:
1. Security Reviewer checks for vulnerabilities
2. Performance Reviewer checks for efficiency
3. Style Reviewer checks for code quality
Delegate appropriately and synthesize findings into a final review.""",
        },
        "specialists": [
            {
                "name": "Security Reviewer",
                "role": "specialist",
                "system_prompt": "Review code for security vulnerabilities: injection, XSS, auth issues, etc.",
            },
            {
                "name": "Performance Reviewer",
                "role": "specialist",
                "system_prompt": "Review code for performance: O(n) complexity, memory leaks, inefficient patterns.",
            },
            {
                "name": "Style Reviewer",
                "role": "specialist",
                "system_prompt": "Review code for style: readability, patterns, naming, documentation.",
            },
        ],
    },
    "steps": [
        {
            "id": 1,
            "action": "Supervisor receives code and creates review plan",
            "agent": "supervisor",
            "inputs": ["code_to_review"],
            "outputs": ["review_plan"],
        },
        {
            "id": 2,
            "type": "parallel",
            "branches": [
                [{"id": 3, "action": "Security review", "agent": "Security Reviewer"}],
                [{"id": 4, "action": "Performance review", "agent": "Performance Reviewer"}],
                [{"id": 5, "action": "Style review", "agent": "Style Reviewer"}],
            ],
        },
        {
            "id": 6,
            "action": "Supervisor synthesizes all reviews into final report",
            "agent": "supervisor",
            "outputs": ["final_review_report"],
        },
    ],
}


# ============== Resilient Workflow ==============

RESILIENT_API_WORKFLOW = {
    "name": "resilient_api_calls",
    "objective": "Make API calls with resilience patterns",
    "resilience": {
        "circuit_breaker": {
            "failure_threshold": 3,
            "timeout_seconds": 30,
        },
        "retry": {
            "max_retries": 3,
            "base_delay": 1.0,
            "max_delay": 10.0,
        },
        "bulkhead": {
            "max_concurrent": 5,
        },
    },
    "steps": [
        {
            "id": 1,
            "action": "Fetch data from primary API",
            "tool": "api",
            "inputs": ["api_endpoint"],
            "outputs": ["api_response"],
            "resilience": "enabled",
            "fallback": {
                "action": "Fetch from backup API",
                "tool": "api",
                "inputs": ["backup_endpoint"],
            },
        },
        {
            "id": 2,
            "action": "Process API response",
            "tool": "llm",
            "inputs": ["api_response"],
            "outputs": ["processed_data"],
        },
    ],
}


# ============== While Loop Workflow ==============

ITERATIVE_REFINEMENT_WORKFLOW = {
    "name": "iterative_refinement",
    "objective": "Iteratively refine output until quality threshold met",
    "steps": [
        {
            "id": 1,
            "action": "Generate initial draft",
            "tool": "llm",
            "inputs": ["requirements"],
            "outputs": ["draft"],
        },
        {
            "id": 2,
            "type": "loop",
            "loop_type": "until",
            "condition": {
                "left": "$quality_score",
                "op": "ge",
                "right": 8,
            },
            "max_iterations": 5,
            "body_steps": [
                {
                    "id": 3,
                    "action": "Evaluate current draft quality (1-10)",
                    "tool": "llm",
                    "inputs": ["draft"],
                    "outputs": ["quality_score", "improvement_suggestions"],
                },
                {
                    "id": 4,
                    "type": "conditional",
                    "condition": {
                        "left": "$quality_score",
                        "op": "lt",
                        "right": 8,
                    },
                    "then_steps": [
                        {
                            "id": 5,
                            "action": "Refine draft based on suggestions",
                            "tool": "llm",
                            "inputs": ["draft", "improvement_suggestions"],
                            "outputs": ["draft"],
                        },
                    ],
                    "else_steps": [],
                },
            ],
        },
        {
            "id": 6,
            "action": "Finalize and format output",
            "tool": "llm",
            "inputs": ["draft"],
            "outputs": ["final_output"],
        },
    ],
}


# ============== Helper Functions ==============

def get_all_examples() -> Dict[str, Dict[str, Any]]:
    """Get all example workflows"""
    return {
        "basic_research": BASIC_RESEARCH_WORKFLOW,
        "conditional_data_processing": CONDITIONAL_DATA_PROCESSING,
        "batch_processing": BATCH_PROCESSING_WORKFLOW,
        "multi_source_research": MULTI_SOURCE_RESEARCH,
        "task_routing": TASK_ROUTING_WORKFLOW,
        "code_review_collaboration": CODE_REVIEW_WORKFLOW,
        "resilient_api_calls": RESILIENT_API_WORKFLOW,
        "iterative_refinement": ITERATIVE_REFINEMENT_WORKFLOW,
    }


def get_example(name: str) -> Dict[str, Any]:
    """Get a specific example workflow by name"""
    examples = get_all_examples()
    return examples.get(name, {})


def list_examples() -> list:
    """List all available example names"""
    return list(get_all_examples().keys())


async def run_example(
    name: str,
    context: Dict[str, Any] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Run an example workflow.

    Args:
        name: Name of the example workflow
        context: Initial context/inputs for the workflow
        dry_run: If True, just validate without executing

    Returns:
        Workflow result or validation result
    """
    workflow = get_example(name)
    if not workflow:
        return {"error": f"Unknown example: {name}"}

    if dry_run:
        return {
            "status": "validated",
            "workflow": workflow,
            "steps_count": len(workflow.get("steps", [])),
            "features_used": _detect_features(workflow),
        }

    # For actual execution, would integrate with WorkflowEngine
    # This is a placeholder for demonstration
    return {
        "status": "would_execute",
        "workflow_name": name,
        "context": context or {},
    }


def _detect_features(workflow: Dict[str, Any]) -> list:
    """Detect which features a workflow uses"""
    features = []

    def check_steps(steps):
        for step in steps:
            step_type = step.get("type", "step")
            if step_type == "conditional":
                features.append("conditional")
                check_steps(step.get("then_steps", []))
                check_steps(step.get("else_steps", []))
            elif step_type == "loop":
                features.append(f"loop_{step.get('loop_type', 'for')}")
                check_steps(step.get("body_steps", []))
            elif step_type == "parallel":
                features.append("parallel")
                for branch in step.get("branches", []):
                    check_steps(branch)
            elif step_type == "branch":
                features.append("branch")

    check_steps(workflow.get("steps", []))

    if workflow.get("collaboration_pattern"):
        features.append(f"collaboration_{workflow['collaboration_pattern']}")

    if workflow.get("resilience"):
        features.append("resilience")

    return list(set(features))


# ============== Demo Runner ==============

if __name__ == "__main__":
    print("Unicorn Brigade - Example Workflows")
    print("=" * 50)
    print()

    for name in list_examples():
        workflow = get_example(name)
        features = _detect_features(workflow)
        print(f"  {name}")
        print(f"    Objective: {workflow.get('objective', 'N/A')}")
        print(f"    Features: {', '.join(features) if features else 'basic'}")
        print()
