"""
Prompt Pack Loader for Unicorn Brigade

Loads and manages prompt templates from the /prompts directory.
Supports variable substitution and template composition.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

# Base directory for prompts
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


@lru_cache(maxsize=20)
def load_prompt(name: str) -> str:
    """
    Load a prompt template by name.

    Args:
        name: Prompt name (e.g., "router", "planner")

    Returns:
        The prompt template content

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    prompt_path = PROMPTS_DIR / f"{name}.md"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {name}")

    with open(prompt_path, 'r') as f:
        content = f.read()

    logger.debug(f"Loaded prompt: {name} ({len(content)} chars)")
    return content


def format_prompt(name: str, **kwargs) -> str:
    """
    Load and format a prompt template with variables.

    Args:
        name: Prompt name
        **kwargs: Variables to substitute in the template

    Returns:
        Formatted prompt string
    """
    template = load_prompt(name)

    # Replace {variable} patterns with values
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        template = template.replace(placeholder, str(value))

    return template


def get_router_prompt(task: str) -> str:
    """Get formatted router prompt for a task"""
    return format_prompt("router", task=task)


def get_planner_prompt(
    task: str,
    intent: str,
    risk: str,
    worker: str,
) -> str:
    """Get formatted planner prompt"""
    return format_prompt(
        "planner",
        task=task,
        intent=intent,
        risk=risk,
        worker=worker,
    )


def get_executor_prompt(
    step_id: str,
    step_name: str,
    step_description: str,
    tool: str,
    timeout: int,
    expected_outputs: list,
    context: str,
) -> str:
    """Get formatted executor prompt for a step"""
    return format_prompt(
        "executor",
        step_id=step_id,
        step_name=step_name,
        step_description=step_description,
        tool=tool,
        timeout=timeout,
        expected_outputs=", ".join(expected_outputs),
        context=context,
    )


def get_verifier_prompt(
    task: str,
    expected_outputs: list,
    result: str,
) -> str:
    """Get formatted verifier prompt"""
    return format_prompt(
        "verifier",
        task=task,
        expected_outputs=", ".join(expected_outputs),
        result=result,
    )


def get_worker_prompt(worker_type: str) -> Optional[str]:
    """
    Get the prompt section for a specific worker type.

    Extracts the relevant section from workers.md
    """
    try:
        workers_content = load_prompt("workers")

        # Find the section for this worker
        section_markers = {
            "research": "## Research Worker",
            "code": "## Code Worker",
            "code_review": "## Code Review Worker",
            "extractor": "## Extractor Worker",
            "report": "## Report Worker",
            "summary": "## Summary Worker",
            "digest": "## Digest Worker",
            "ops": "## Ops Worker",
            "entity": "## Entity Extraction Worker",
            "table": "## Table Extraction Worker",
        }

        marker = section_markers.get(worker_type.lower())
        if not marker:
            return None

        # Find section start
        start_idx = workers_content.find(marker)
        if start_idx == -1:
            return None

        # Find section end (next ## or end of file)
        end_idx = workers_content.find("\n---\n", start_idx + len(marker))
        if end_idx == -1:
            end_idx = len(workers_content)

        section = workers_content[start_idx:end_idx].strip()

        # Remove the header
        lines = section.split('\n')
        if lines and lines[0].startswith('##'):
            lines = lines[1:]

        return '\n'.join(lines).strip()

    except FileNotFoundError:
        return None


def list_prompts() -> list:
    """List all available prompt templates"""
    if not PROMPTS_DIR.exists():
        return []

    prompts = []
    for file in PROMPTS_DIR.glob("*.md"):
        prompts.append({
            "name": file.stem,
            "path": str(file),
            "size": file.stat().st_size,
        })

    return prompts


def reload_prompts():
    """Clear the prompt cache to reload from disk"""
    load_prompt.cache_clear()
    logger.info("Prompt cache cleared")


__all__ = [
    "load_prompt",
    "format_prompt",
    "get_router_prompt",
    "get_planner_prompt",
    "get_executor_prompt",
    "get_verifier_prompt",
    "get_worker_prompt",
    "list_prompts",
    "reload_prompts",
    "PROMPTS_DIR",
]
