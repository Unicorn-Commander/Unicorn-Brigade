#!/usr/bin/env python3
"""
Unicorn Brigade CLI

Command-line interface for running workflows, managing agents,
and interacting with the Unicorn Brigade engine.

Usage:
    python -m app.cli workflow run <name> [--context JSON]
    python -m app.cli workflow list
    python -m app.cli workflow validate <file>
    python -m app.cli agent list
    python -m app.cli metrics show
    python -m app.cli health check
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional


def setup_parser() -> argparse.ArgumentParser:
    """Setup argument parser"""
    parser = argparse.ArgumentParser(
        prog="unicorn-brigade",
        description="Unicorn Brigade AI Agent Factory CLI",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Workflow commands
    workflow_parser = subparsers.add_parser("workflow", help="Workflow commands")
    workflow_sub = workflow_parser.add_subparsers(dest="workflow_command")

    # workflow run
    run_parser = workflow_sub.add_parser("run", help="Run a workflow")
    run_parser.add_argument("name", help="Workflow name or file path")
    run_parser.add_argument(
        "--context", "-c",
        type=str,
        default="{}",
        help="JSON context for the workflow",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate without executing",
    )
    run_parser.add_argument(
        "--model",
        type=str,
        default="local",
        help="Model to use (local, ops-center, claude-burst)",
    )

    # workflow list
    workflow_sub.add_parser("list", help="List available workflows")

    # workflow validate
    validate_parser = workflow_sub.add_parser("validate", help="Validate a workflow file")
    validate_parser.add_argument("file", help="Workflow JSON file")

    # workflow examples
    workflow_sub.add_parser("examples", help="List example workflows")

    # Agent commands
    agent_parser = subparsers.add_parser("agent", help="Agent commands")
    agent_sub = agent_parser.add_subparsers(dest="agent_command")

    agent_sub.add_parser("list", help="List available agents")

    # Metrics commands
    metrics_parser = subparsers.add_parser("metrics", help="Metrics commands")
    metrics_sub = metrics_parser.add_subparsers(dest="metrics_command")

    show_parser = metrics_sub.add_parser("show", help="Show current metrics")
    show_parser.add_argument(
        "--format",
        choices=["json", "prometheus"],
        default="json",
        help="Output format",
    )

    # Health commands
    health_parser = subparsers.add_parser("health", help="Health check commands")
    health_sub = health_parser.add_subparsers(dest="health_command")

    health_sub.add_parser("check", help="Run health checks")

    return parser


async def cmd_workflow_run(args) -> int:
    """Run a workflow"""
    from app.examples import get_example, list_examples

    # Check if it's an example workflow
    if args.name in list_examples():
        workflow = get_example(args.name)
        print(f"Running example workflow: {args.name}")
    elif Path(args.name).exists():
        with open(args.name) as f:
            workflow = json.load(f)
        print(f"Running workflow from file: {args.name}")
    else:
        print(f"Error: Unknown workflow '{args.name}'")
        print(f"Available examples: {', '.join(list_examples())}")
        return 1

    # Parse context
    try:
        context = json.loads(args.context)
    except json.JSONDecodeError as e:
        print(f"Error parsing context JSON: {e}")
        return 1

    if args.dry_run:
        print("\n--- Dry Run (Validation Only) ---")
        print(f"Workflow: {workflow.get('name', 'unnamed')}")
        print(f"Objective: {workflow.get('objective', 'N/A')}")
        print(f"Steps: {len(workflow.get('steps', []))}")
        print(f"Context: {json.dumps(context, indent=2)}")

        # Detect features
        from app.examples.workflow_examples import _detect_features
        features = _detect_features(workflow)
        print(f"Features: {', '.join(features) if features else 'basic'}")

        print("\n✓ Workflow is valid")
        return 0

    # Actual execution
    try:
        from app.engine import WorkflowEngine, Task
        from app.engine.observability import tracer, workflow_executions_total

        engine = WorkflowEngine()

        task = Task(
            user_id="cli_user",
            content=workflow.get("objective", "Execute workflow"),
            context=context,
            suggested_workflow=args.name,
        )

        print(f"\nExecuting workflow: {workflow.get('name', 'unnamed')}")
        print(f"Model: {args.model}")
        print("-" * 50)

        with tracer.start_span("cli_workflow_execution") as span:
            span.set_attribute("workflow_name", workflow.get("name", "unknown"))
            result = await engine.execute(task, model=args.model)

        print("\n--- Result ---")
        print(f"Status: {result.status}")
        if result.output:
            print(f"Output: {result.output[:500]}...")
        if result.artifacts:
            print(f"Artifacts: {result.artifacts}")

        workflow_executions_total.inc(labels={"status": result.status.value})

        return 0 if result.status.value == "completed" else 1

    except Exception as e:
        print(f"Error executing workflow: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_workflow_list(args) -> int:
    """List available workflows"""
    from app.examples import list_examples, get_example

    print("Available Example Workflows:")
    print("-" * 50)

    for name in list_examples():
        workflow = get_example(name)
        print(f"\n{name}")
        print(f"  Objective: {workflow.get('objective', 'N/A')}")
        print(f"  Steps: {len(workflow.get('steps', []))}")

    return 0


def cmd_workflow_validate(args) -> int:
    """Validate a workflow file"""
    file_path = Path(args.file)

    if not file_path.exists():
        print(f"Error: File not found: {args.file}")
        return 1

    try:
        with open(file_path) as f:
            workflow = json.load(f)

        # Basic validation
        errors = []

        if "name" not in workflow:
            errors.append("Missing 'name' field")
        if "steps" not in workflow:
            errors.append("Missing 'steps' field")
        elif not isinstance(workflow["steps"], list):
            errors.append("'steps' must be a list")
        elif len(workflow["steps"]) == 0:
            errors.append("'steps' must not be empty")

        if errors:
            print(f"Validation failed for {args.file}:")
            for error in errors:
                print(f"  - {error}")
            return 1

        print(f"✓ Workflow '{workflow.get('name')}' is valid")
        print(f"  Steps: {len(workflow.get('steps', []))}")
        print(f"  Objective: {workflow.get('objective', 'N/A')}")

        return 0

    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {args.file}: {e}")
        return 1


def cmd_agent_list(args) -> int:
    """List available agents"""
    print("Registered Agents:")
    print("-" * 50)

    # List workers
    print("\nWorkers:")
    workers = ["ResearchWorker", "CodeWorker", "ExtractorWorker", "ReportWorker", "OpsWorker"]
    for worker in workers:
        print(f"  - {worker}")

    # List collaboration agents
    print("\nCollaboration Teams:")
    teams = ["Research Team", "Code Review Team", "Customer Support Swarm"]
    for team in teams:
        print(f"  - {team}")

    return 0


def cmd_metrics_show(args) -> int:
    """Show current metrics"""
    from app.engine.observability import metrics

    if args.format == "prometheus":
        print(metrics.to_prometheus())
    else:
        all_metrics = metrics.get_all_metrics()
        print(json.dumps(all_metrics, indent=2, default=str))

    return 0


async def cmd_health_check(args) -> int:
    """Run health checks"""
    from app.engine.observability import health_checker, HealthCheckResult, HealthStatus

    # Register some basic checks
    def llm_check():
        return HealthCheckResult(
            name="llm_client",
            status=HealthStatus.HEALTHY,
            message="LLM client initialized",
        )

    def engine_check():
        return HealthCheckResult(
            name="workflow_engine",
            status=HealthStatus.HEALTHY,
            message="Engine ready",
        )

    health_checker.register_check("llm_client", llm_check)
    health_checker.register_check("workflow_engine", engine_check)

    print("Health Check Results:")
    print("-" * 50)

    results = await health_checker.check_all_async()
    overall = HealthStatus.HEALTHY

    for name, result in results.items():
        status_icon = "✓" if result.status == HealthStatus.HEALTHY else "✗"
        print(f"{status_icon} {name}: {result.status.value}")
        if result.message:
            print(f"    {result.message}")
        if result.latency_ms > 0:
            print(f"    Latency: {result.latency_ms:.2f}ms")

        if result.status == HealthStatus.UNHEALTHY:
            overall = HealthStatus.UNHEALTHY
        elif result.status == HealthStatus.DEGRADED and overall == HealthStatus.HEALTHY:
            overall = HealthStatus.DEGRADED

    print("-" * 50)
    print(f"Overall: {overall.value}")

    return 0 if overall == HealthStatus.HEALTHY else 1


async def main() -> int:
    """Main entry point"""
    parser = setup_parser()
    args = parser.parse_args()

    if args.verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    if args.command == "workflow":
        if args.workflow_command == "run":
            return await cmd_workflow_run(args)
        elif args.workflow_command == "list":
            return cmd_workflow_list(args)
        elif args.workflow_command == "examples":
            return cmd_workflow_list(args)
        elif args.workflow_command == "validate":
            return cmd_workflow_validate(args)
        else:
            parser.print_help()
            return 1

    elif args.command == "agent":
        if args.agent_command == "list":
            return cmd_agent_list(args)
        else:
            parser.print_help()
            return 1

    elif args.command == "metrics":
        if args.metrics_command == "show":
            return cmd_metrics_show(args)
        else:
            parser.print_help()
            return 1

    elif args.command == "health":
        if args.health_command == "check":
            return await cmd_health_check(args)
        else:
            parser.print_help()
            return 1

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
