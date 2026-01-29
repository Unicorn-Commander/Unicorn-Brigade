"""
Tests for ApprovalGate component
"""

import pytest
from datetime import datetime, timedelta
from app.engine.models import WorkflowStep, WorkerType, ToolType, ResumeToken
from app.engine.approval import ApprovalGate


class TestApprovalGate:
    """Tests for ApprovalGate"""

    @pytest.fixture
    def gate(self, tmp_path):
        """Create approval gate with temp storage"""
        return ApprovalGate(storage_path=str(tmp_path / "approvals"))

    @pytest.fixture
    def sample_step(self):
        """Create sample workflow step"""
        return WorkflowStep(
            id="step_1",
            name="Deploy to production",
            description="Deploy the application",
            worker_type=WorkerType.OPS,
            tool=ToolType.SHELL,
            requires_approval=True,
        )

    def test_create_checkpoint(self, gate, sample_step):
        """Test creating approval checkpoint"""
        token = gate.create_checkpoint(
            workflow_id="wf_123",
            step=sample_step,
            context={"version": "1.0.0"},
        )

        assert token is not None
        assert token.workflow_id == "wf_123"
        assert token.step_id == "step_1"
        assert token.approved is False
        assert token.is_valid() is True

    def test_approve_token(self, gate, sample_step):
        """Test approving a token"""
        token = gate.create_checkpoint(
            workflow_id="wf_123",
            step=sample_step,
            context={},
        )

        success = gate.approve(token.id, approved_by="admin")

        assert success is True

        # Verify token is updated
        updated = gate.get_pending(token.id)
        assert updated.approved is True
        assert updated.approved_by == "admin"

    def test_reject_token(self, gate, sample_step):
        """Test rejecting a token"""
        token = gate.create_checkpoint(
            workflow_id="wf_123",
            step=sample_step,
            context={},
        )

        success = gate.reject(
            token.id,
            rejected_by="admin",
            reason="Not approved for deployment",
        )

        assert success is True

        # Verify token is updated
        updated = gate.get_pending(token.id)
        assert updated is None  # Rejected tokens may be removed

    def test_list_pending(self, gate, sample_step):
        """Test listing pending approvals"""
        # Create multiple checkpoints
        token1 = gate.create_checkpoint(
            workflow_id="wf_1",
            step=sample_step,
            context={},
        )
        token2 = gate.create_checkpoint(
            workflow_id="wf_2",
            step=sample_step,
            context={},
        )

        pending = gate.list_pending()

        assert len(pending) >= 2
        assert any(t.id == token1.id for t in pending)
        assert any(t.id == token2.id for t in pending)

    def test_get_pending_nonexistent(self, gate):
        """Test getting nonexistent token"""
        result = gate.get_pending("nonexistent_id")
        assert result is None

    def test_token_expiration(self, gate, sample_step):
        """Test token expiration"""
        # Create token with short expiration
        token = gate.create_checkpoint(
            workflow_id="wf_123",
            step=sample_step,
            context={},
        )

        # Manually expire it
        token.expires_at = datetime.utcnow() - timedelta(hours=1)

        assert token.is_valid() is False

    def test_approve_expired_token(self, gate, sample_step):
        """Test approving an expired token"""
        token = gate.create_checkpoint(
            workflow_id="wf_123",
            step=sample_step,
            context={},
        )

        # Manually expire it
        gate._pending[token.id].expires_at = datetime.utcnow() - timedelta(hours=1)

        success = gate.approve(token.id)

        # Should fail for expired token
        assert success is False

    def test_approve_already_used_token(self, gate, sample_step):
        """Test approving an already used token"""
        token = gate.create_checkpoint(
            workflow_id="wf_123",
            step=sample_step,
            context={},
        )

        # First approval
        gate.approve(token.id)

        # Second approval should fail
        success = gate.approve(token.id)
        assert success is False

    def test_clear_expired(self, gate, sample_step):
        """Test clearing expired tokens"""
        # Create tokens with different expirations
        valid_token = gate.create_checkpoint(
            workflow_id="wf_1",
            step=sample_step,
            context={},
        )

        expired_token = gate.create_checkpoint(
            workflow_id="wf_2",
            step=sample_step,
            context={},
        )
        gate._pending[expired_token.id].expires_at = datetime.utcnow() - timedelta(hours=1)

        # Clear expired
        cleared = gate.clear_expired()

        assert cleared >= 1

        # Valid token should remain
        assert gate.get_pending(valid_token.id) is not None

    @pytest.mark.asyncio
    async def test_request_approval(self, gate, sample_step):
        """Test async approval request"""
        token = await gate.request_approval(
            step=sample_step,
            context={"version": "1.0.0"},
            workflow_id="wf_123",
        )

        assert token is not None
        assert token.workflow_id == "wf_123"

    def test_persistence(self, tmp_path, sample_step):
        """Test token persistence to disk"""
        storage_path = str(tmp_path / "approvals")

        # Create gate and add token
        gate1 = ApprovalGate(storage_path=storage_path)
        token = gate1.create_checkpoint(
            workflow_id="wf_123",
            step=sample_step,
            context={"important": "data"},
        )

        # Create new gate instance (simulates restart)
        gate2 = ApprovalGate(storage_path=storage_path)

        # Token should be loaded
        loaded = gate2.get_pending(token.id)
        assert loaded is not None
        assert loaded.workflow_id == "wf_123"
        assert loaded.context["important"] == "data"

    def test_multiple_steps_same_workflow(self, gate):
        """Test multiple approval points in same workflow"""
        step1 = WorkflowStep(
            id="step_1",
            name="Build",
            description="Build application",
            worker_type=WorkerType.OPS,
            tool=ToolType.SHELL,
            requires_approval=True,
        )

        step2 = WorkflowStep(
            id="step_2",
            name="Deploy",
            description="Deploy application",
            worker_type=WorkerType.OPS,
            tool=ToolType.SHELL,
            requires_approval=True,
        )

        token1 = gate.create_checkpoint(
            workflow_id="wf_123",
            step=step1,
            context={"phase": "build"},
        )

        token2 = gate.create_checkpoint(
            workflow_id="wf_123",
            step=step2,
            context={"phase": "deploy"},
        )

        assert token1.id != token2.id
        assert token1.step_id == "step_1"
        assert token2.step_id == "step_2"

        # Approve first step
        gate.approve(token1.id)

        # Second step should still be pending
        pending = gate.list_pending()
        assert any(t.id == token2.id for t in pending)
