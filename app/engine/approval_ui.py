"""
A2UI Integration for Approval Gates

Generates rich UI for approval requests using the A2UI protocol.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from app.protocols.a2ui import (
    A2UIBuilder, A2UIResponse, A2UIComponent, A2UIComponentType,
    task_progress_ui, approval_request_ui,
)
from app.engine.models import WorkflowStep, ResumeToken, WorkflowPlan, RiskLevel


class ApprovalUIGenerator:
    """
    Generates A2UI responses for approval gates.

    This provides rich, native UI for approval requests
    that can be rendered in desktop/mobile apps.
    """

    def __init__(self, agent_id: str = "workflow_engine"):
        self.agent_id = agent_id

    def generate_approval_ui(
        self,
        token: ResumeToken,
        step: WorkflowStep,
        context: Dict[str, Any],
        plan: Optional[WorkflowPlan] = None,
    ) -> A2UIResponse:
        """
        Generate comprehensive approval UI.

        Includes:
        - Step description and risk level
        - Context and artifacts
        - Approve/Reject buttons
        - Progress indicator
        """
        builder = A2UIBuilder(agent_id=self.agent_id)

        # Header
        heading = builder.heading("⚠️ Approval Required", level=1)

        # Risk alert
        risk_str = step.risk.value if hasattr(step.risk, 'value') else str(step.risk)
        risk_severity = self._risk_to_severity(risk_str)
        risk_alert = builder.alert(
            f"Risk Level: {risk_str.upper()}",
            severity=risk_severity,
        )

        # Step details card
        step_title = builder.heading(f"Step: {step.action}", level=2)
        step_id_text = builder.text(f"Step ID: {step.id}")

        tool_text = builder.text(
            f"Tool: {step.tool.value if hasattr(step.tool, 'value') else step.tool}"
        )

        timeout_text = builder.text(f"Timeout: {step.timeout_seconds}s")

        step_card = builder.card(
            title="Step Details",
            children=[step_title, step_id_text, tool_text, timeout_text],
        )

        # Context card
        context_items = []
        if context:
            for key, value in list(context.items())[:5]:
                ctx_text = builder.text(f"{key}: {str(value)[:100]}")
                context_items.append(ctx_text)

        context_card = builder.card(
            title="Execution Context",
            children=context_items if context_items else [builder.text("No additional context")],
        )

        # Progress indicator (if plan available)
        progress_items = []
        if plan:
            current_step_idx = next(
                (i for i, s in enumerate(plan.steps) if s.id == step.id),
                0
            )
            progress_value = current_step_idx / len(plan.steps) if plan.steps else 0

            progress = builder.progress(progress_value, f"Step {current_step_idx + 1} of {len(plan.steps)}")
            progress_items.append(progress)

        # Artifacts preview (if any in context)
        artifacts = context.get("pending_artifacts", [])
        if artifacts:
            artifacts_text = builder.text(f"Pending artifacts: {', '.join(str(a) for a in artifacts[:5])}")
            progress_items.append(artifacts_text)

        # Token info
        token_text = builder.text(f"Token ID: {token.id[:16]}...")
        expires_text = builder.text(
            f"Expires: {token.expires_at.isoformat() if token.expires_at else 'Never'}"
        )

        # Action buttons
        approve_btn = builder.button(
            "✓ Approve",
            action_type="submit",
            payload={
                "token_id": token.id,
                "approved": True,
                "action": "approve",
            },
            variant="primary",
        )

        reject_btn = builder.button(
            "✗ Reject",
            action_type="submit",
            payload={
                "token_id": token.id,
                "approved": False,
                "action": "reject",
            },
            variant="danger",
        )

        modify_btn = builder.button(
            "✎ Modify & Approve",
            action_type="navigate",
            payload={
                "token_id": token.id,
                "action": "modify",
                "url": f"/workflow/modify/{token.id}",
            },
            variant="secondary",
        )

        button_row = builder.row([approve_btn, reject_btn, modify_btn])

        # Compose main layout
        main_children = [
            heading,
            risk_alert,
            step_card,
            context_card,
        ]

        if progress_items:
            progress_card = builder.card(title="Progress", children=progress_items)
            main_children.append(progress_card)

        main_children.extend([token_text, expires_text, button_row])

        root = builder.column(main_children, gap=16)

        # Set data model
        builder.set_data("token_id", token.id)
        builder.set_data("step_id", step.id)
        builder.set_data("workflow_id", token.workflow_id)

        return builder.build(root)

    def generate_progress_ui(
        self,
        plan: WorkflowPlan,
        current_step_idx: int,
        status: str,
    ) -> A2UIResponse:
        """Generate workflow progress UI"""
        builder = A2UIBuilder(agent_id=self.agent_id)

        # Header
        heading = builder.heading(f"Workflow: {plan.name}", level=1)

        # Status
        status_colors = {
            "running": "info",
            "completed": "success",
            "failed": "error",
            "pending_approval": "warning",
        }
        status_alert = builder.alert(
            f"Status: {status.upper()}",
            severity=status_colors.get(status, "info"),
        )

        # Progress
        progress_value = (current_step_idx + 1) / len(plan.steps) if plan.steps else 0
        progress = builder.progress(
            progress_value,
            f"Step {current_step_idx + 1} of {len(plan.steps)}",
        )

        # Steps list
        step_items = []
        for i, step in enumerate(plan.steps):
            if i < current_step_idx:
                icon = "✓"
                status_text = "completed"
            elif i == current_step_idx:
                icon = "→"
                status_text = "current"
            else:
                icon = "○"
                status_text = "pending"

            step_text = builder.text(f"{icon} {step.action} [{status_text}]")
            step_items.append(step_text)

        steps_card = builder.card(title="Steps", children=step_items)

        # Compose
        root = builder.column([heading, status_alert, progress, steps_card], gap=12)

        return builder.build(root)

    def generate_completion_ui(
        self,
        plan: WorkflowPlan,
        result: Dict[str, Any],
        artifacts: List[Dict[str, Any]],
    ) -> A2UIResponse:
        """Generate workflow completion UI"""
        builder = A2UIBuilder(agent_id=self.agent_id)

        # Header
        heading = builder.heading("✓ Workflow Complete", level=1)

        # Summary
        success_alert = builder.alert(
            f"Completed: {plan.name}",
            severity="success",
        )

        # Result summary
        output = result.get("output", "")[:500]
        output_text = builder.text(output)

        result_card = builder.card(
            title="Result",
            children=[output_text],
        )

        # Artifacts
        artifact_items = []
        for artifact in artifacts[:5]:
            name = artifact.get("name", "unnamed")
            atype = artifact.get("type", "unknown")
            artifact_text = builder.text(f"• {name} ({atype})")
            artifact_items.append(artifact_text)

        if artifact_items:
            artifacts_card = builder.card(
                title="Artifacts",
                children=artifact_items,
            )
        else:
            artifacts_card = None

        # Metrics
        tokens = result.get("tokens_used", {})
        duration = result.get("duration_seconds", 0)

        metrics_text = builder.text(
            f"Tokens: {tokens.get('total', 0)} | Duration: {duration:.1f}s"
        )

        # Compose
        children = [heading, success_alert, result_card]
        if artifacts_card:
            children.append(artifacts_card)
        children.append(metrics_text)

        root = builder.column(children, gap=12)

        return builder.build(root)

    def _risk_to_severity(self, risk: str) -> str:
        """Convert risk level to alert severity"""
        risk_lower = risk.lower()
        if risk_lower == "critical":
            return "error"
        elif risk_lower == "high":
            return "error"
        elif risk_lower == "medium":
            return "warning"
        else:
            return "info"


# Convenience functions

def create_approval_ui(
    token: ResumeToken,
    step: WorkflowStep,
    context: Dict[str, Any],
    plan: Optional[WorkflowPlan] = None,
) -> A2UIResponse:
    """Quick function to create approval UI"""
    generator = ApprovalUIGenerator()
    return generator.generate_approval_ui(token, step, context, plan)


def create_progress_ui(
    plan: WorkflowPlan,
    current_step: int,
    status: str,
) -> A2UIResponse:
    """Quick function to create progress UI"""
    generator = ApprovalUIGenerator()
    return generator.generate_progress_ui(plan, current_step, status)
