"""
Approval Gate - Human-in-the-Loop with Resume Tokens

The Approval Gate handles:
- Pausing workflows for human approval
- Generating resume tokens for state persistence
- Resuming workflows after approval/rejection
"""

import json
import logging
import uuid
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from pathlib import Path

from app.engine.models import (
    WorkflowStep,
    WorkflowPlan,
    ExecutionResult,
    ResumeToken,
    ApprovalState,
    RiskLevel,
    ExecutionStatus,
)

logger = logging.getLogger(__name__)


class ApprovalGate:
    """Manages approval gates and resume tokens for workflows"""

    def __init__(
        self,
        state_dir: Optional[Path] = None,
        token_expiry_hours: int = 24,
        on_approval_request: Optional[Callable] = None,
    ):
        """
        Initialize ApprovalGate.

        Args:
            state_dir: Directory to store resume tokens
            token_expiry_hours: How long tokens remain valid
            on_approval_request: Callback when approval is requested
        """
        self.state_dir = state_dir or Path("./state/approvals")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.token_expiry_hours = token_expiry_hours
        self.on_approval_request = on_approval_request

        # In-memory cache of pending approvals
        self._pending: Dict[str, ResumeToken] = {}

    def create_checkpoint(
        self,
        workflow_id: str,
        step: WorkflowStep,
        context: Dict[str, Any],
    ) -> ResumeToken:
        """
        Create a checkpoint before a step requiring approval.

        Args:
            workflow_id: The workflow ID
            step: The step requiring approval
            context: Current execution context

        Returns:
            ResumeToken that can be used to resume the workflow
        """
        token = ResumeToken(
            token_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            step_id=step.id,
            state=context,
            approval_state=ApprovalState.PENDING,
            step_description=step.action,
            risk_level=step.risk,
            artifacts_pending=step.outputs,
            expires_at=datetime.utcnow() + timedelta(hours=self.token_expiry_hours),
        )

        # Save to disk
        self._save_token(token)

        # Cache
        self._pending[token.token_id] = token

        logger.info(
            f"Created approval checkpoint for workflow {workflow_id}, "
            f"step {step.id}: {token.token_id}"
        )

        return token

    def _save_token(self, token: ResumeToken):
        """Save token to disk"""
        token_path = self.state_dir / f"{token.token_id}.json"
        token_path.write_text(token.model_dump_json(indent=2))

    def _load_token(self, token_id: str) -> Optional[ResumeToken]:
        """Load token from disk"""
        token_path = self.state_dir / f"{token_id}.json"
        if token_path.exists():
            data = json.loads(token_path.read_text())
            return ResumeToken(**data)
        return None

    def _delete_token(self, token_id: str):
        """Delete token from disk"""
        token_path = self.state_dir / f"{token_id}.json"
        if token_path.exists():
            token_path.unlink()
        if token_id in self._pending:
            del self._pending[token_id]

    async def request_approval(
        self,
        step: WorkflowStep,
        context: Dict[str, Any],
        workflow_id: str,
    ) -> ResumeToken:
        """
        Request approval for a step.

        Creates checkpoint, emits approval request, and returns token.
        """
        token = self.create_checkpoint(workflow_id, step, context)

        # Emit approval request if callback is set
        if self.on_approval_request:
            await self.on_approval_request(token)

        return token

    def get_pending_approvals(self) -> list[ResumeToken]:
        """Get all pending approval requests"""
        # Load from disk and filter expired
        pending = []
        now = datetime.utcnow()

        for token_file in self.state_dir.glob("*.json"):
            try:
                token = self._load_token(token_file.stem)
                if token and token.approval_state == ApprovalState.PENDING:
                    if token.expires_at and token.expires_at < now:
                        # Expired - mark as rejected
                        token.approval_state = ApprovalState.REJECTED
                        self._save_token(token)
                    else:
                        pending.append(token)
            except Exception as e:
                logger.error(f"Error loading token {token_file}: {e}")

        return pending

    def get_token(self, token_id: str) -> Optional[ResumeToken]:
        """Get a specific resume token"""
        # Check cache first
        if token_id in self._pending:
            return self._pending[token_id]

        # Load from disk
        return self._load_token(token_id)

    def approve(self, token_id: str, approved_by: str = "user") -> bool:
        """
        Approve a pending step.

        Args:
            token_id: The resume token ID
            approved_by: Who approved (for audit)

        Returns:
            True if approved successfully
        """
        token = self.get_token(token_id)
        if not token:
            logger.warning(f"Token not found: {token_id}")
            return False

        if token.approval_state != ApprovalState.PENDING:
            logger.warning(f"Token {token_id} is not pending: {token.approval_state}")
            return False

        # Check expiry
        if token.expires_at and token.expires_at < datetime.utcnow():
            logger.warning(f"Token {token_id} has expired")
            token.approval_state = ApprovalState.REJECTED
            self._save_token(token)
            return False

        # Approve
        token.approval_state = ApprovalState.APPROVED
        token.state["approved_by"] = approved_by
        token.state["approved_at"] = datetime.utcnow().isoformat()
        self._save_token(token)

        logger.info(f"Approved token {token_id} by {approved_by}")
        return True

    def reject(
        self,
        token_id: str,
        rejected_by: str = "user",
        reason: str = "",
    ) -> bool:
        """
        Reject a pending step.

        Args:
            token_id: The resume token ID
            rejected_by: Who rejected (for audit)
            reason: Reason for rejection

        Returns:
            True if rejected successfully
        """
        token = self.get_token(token_id)
        if not token:
            logger.warning(f"Token not found: {token_id}")
            return False

        if token.approval_state != ApprovalState.PENDING:
            logger.warning(f"Token {token_id} is not pending: {token.approval_state}")
            return False

        # Reject
        token.approval_state = ApprovalState.REJECTED
        token.state["rejected_by"] = rejected_by
        token.state["rejected_at"] = datetime.utcnow().isoformat()
        token.state["rejection_reason"] = reason
        self._save_token(token)

        logger.info(f"Rejected token {token_id} by {rejected_by}: {reason}")
        return True

    def can_resume(self, token_id: str) -> tuple[bool, str]:
        """
        Check if a workflow can be resumed.

        Returns:
            Tuple of (can_resume, reason)
        """
        token = self.get_token(token_id)
        if not token:
            return False, "Token not found"

        if token.approval_state == ApprovalState.PENDING:
            return False, "Approval still pending"

        if token.approval_state == ApprovalState.REJECTED:
            return False, f"Approval was rejected: {token.state.get('rejection_reason', '')}"

        if token.expires_at and token.expires_at < datetime.utcnow():
            return False, "Token has expired"

        if token.approval_state == ApprovalState.APPROVED:
            return True, "Approved and ready to resume"

        return False, f"Unknown state: {token.approval_state}"

    def get_resume_context(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the saved context for resuming a workflow.

        Returns:
            The saved execution context, or None if not resumable
        """
        can_resume, reason = self.can_resume(token_id)
        if not can_resume:
            logger.warning(f"Cannot resume token {token_id}: {reason}")
            return None

        token = self.get_token(token_id)
        return token.state if token else None

    def cleanup_expired(self) -> int:
        """
        Clean up expired tokens.

        Returns:
            Number of tokens cleaned up
        """
        cleaned = 0
        now = datetime.utcnow()

        for token_file in self.state_dir.glob("*.json"):
            try:
                token = self._load_token(token_file.stem)
                if token and token.expires_at and token.expires_at < now:
                    self._delete_token(token.token_id)
                    cleaned += 1
            except Exception as e:
                logger.error(f"Error cleaning up token {token_file}: {e}")

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired approval tokens")

        return cleaned

    def format_approval_request(self, token: ResumeToken) -> Dict[str, Any]:
        """
        Format an approval request for display (UI/chat/etc.)

        Returns:
            Formatted approval request data
        """
        return {
            "token_id": token.token_id,
            "workflow_id": token.workflow_id,
            "step_id": token.step_id,
            "description": token.step_description,
            "risk_level": token.risk_level.value,
            "artifacts_pending": token.artifacts_pending,
            "created_at": token.created_at.isoformat(),
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
            "approval_url": f"/api/v1/approvals/{token.token_id}",
            "actions": {
                "approve": f"/api/v1/approvals/{token.token_id}/approve",
                "reject": f"/api/v1/approvals/{token.token_id}/reject",
            }
        }
