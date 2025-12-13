from agent_platform.core.work_items.work_item import WorkItemStatus
from agent_platform.server.work_items.state_machine import WorkItemStateMachine


class TestWorkItemStateMachine:
    """Test cases for WorkItemStateMachine."""

    def test_valid_transitions_from_draft(self):
        """Test valid transitions from PRECREATED state."""
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.DRAFT, WorkItemStatus.PENDING)
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.DRAFT, WorkItemStatus.CANCELLED)

    def test_valid_transitions_from_precreated(self):
        """Test valid transitions from PRECREATED state."""
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.PRECREATED, WorkItemStatus.PENDING)
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.PRECREATED, WorkItemStatus.CANCELLED)

    def test_invalid_transitions_from_draft(self):
        """Test invalid transitions from DRAFT state."""
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.DRAFT, WorkItemStatus.EXECUTING)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.DRAFT, WorkItemStatus.COMPLETED)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.DRAFT, WorkItemStatus.ERROR)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.DRAFT, WorkItemStatus.NEEDS_REVIEW)

    def test_invalid_transitions_from_precreated(self):
        """Test invalid transitions from PRECREATED state."""
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.PRECREATED, WorkItemStatus.EXECUTING)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.PRECREATED, WorkItemStatus.COMPLETED)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.PRECREATED, WorkItemStatus.ERROR)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.PRECREATED, WorkItemStatus.NEEDS_REVIEW)

    def test_valid_transitions_from_pending(self):
        """Test valid transitions from PENDING state."""
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.PENDING, WorkItemStatus.EXECUTING)
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.PENDING, WorkItemStatus.CANCELLED)

    def test_invalid_transitions_from_pending(self):
        """Test invalid transitions from PENDING state."""
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.PENDING, WorkItemStatus.COMPLETED)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.PENDING, WorkItemStatus.ERROR)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.PENDING, WorkItemStatus.NEEDS_REVIEW)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.PENDING, WorkItemStatus.PRECREATED)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.PENDING, WorkItemStatus.DRAFT)

    def test_valid_transitions_from_executing(self):
        """Test valid transitions from EXECUTING state."""
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.EXECUTING, WorkItemStatus.NEEDS_REVIEW)
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.EXECUTING, WorkItemStatus.COMPLETED)
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.EXECUTING, WorkItemStatus.ERROR)
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.EXECUTING, WorkItemStatus.CANCELLED)
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.EXECUTING, WorkItemStatus.INDETERMINATE)

    def test_invalid_transitions_from_executing(self):
        """Test invalid transitions from EXECUTING state."""
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.EXECUTING, WorkItemStatus.PRECREATED)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.EXECUTING, WorkItemStatus.DRAFT)

    def test_valid_transitions_from_needs_review(self):
        """Test valid transitions from NEEDS_REVIEW state."""
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.NEEDS_REVIEW, WorkItemStatus.COMPLETED)
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.NEEDS_REVIEW, WorkItemStatus.PENDING)

    def test_invalid_transitions_from_needs_review(self):
        """Test invalid transitions from NEEDS_REVIEW state."""
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.NEEDS_REVIEW, WorkItemStatus.EXECUTING)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.NEEDS_REVIEW, WorkItemStatus.ERROR)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.NEEDS_REVIEW, WorkItemStatus.CANCELLED)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.NEEDS_REVIEW, WorkItemStatus.PRECREATED)

    def test_valid_transitions_from_indeterminate(self):
        """Test valid transitions from INDETERMINATE state."""
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.INDETERMINATE, WorkItemStatus.PENDING)
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.INDETERMINATE, WorkItemStatus.COMPLETED)

    def test_invalid_transitions_from_indeterminate(self):
        """Test invalid transitions from INDETERMINATE state."""
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.INDETERMINATE, WorkItemStatus.EXECUTING)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.INDETERMINATE, WorkItemStatus.NEEDS_REVIEW)

    def test_valid_transitions_from_error(self):
        """Test valid transitions from ERROR state."""
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.ERROR, WorkItemStatus.PENDING)
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.ERROR, WorkItemStatus.COMPLETED)

    def test_invalid_transitions_from_error(self):
        """Test invalid transitions from ERROR state."""
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.ERROR, WorkItemStatus.EXECUTING)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.ERROR, WorkItemStatus.NEEDS_REVIEW)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.ERROR, WorkItemStatus.CANCELLED)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.ERROR, WorkItemStatus.PRECREATED)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.ERROR, WorkItemStatus.PRECREATED)

    def test_valid_transitions_from_cancelled(self):
        """Test valid transitions from CANCELLED state."""
        # CANCELLED can be restarted back to PENDING
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.CANCELLED, WorkItemStatus.PENDING)
        # CANCELLED can be marked as COMPLETED
        assert WorkItemStateMachine.is_valid_transition(WorkItemStatus.CANCELLED, WorkItemStatus.COMPLETED)

    def test_invalid_transitions_from_cancelled(self):
        """Test invalid transitions from CANCELLED state."""
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.CANCELLED, WorkItemStatus.EXECUTING)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.CANCELLED, WorkItemStatus.ERROR)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.CANCELLED, WorkItemStatus.NEEDS_REVIEW)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.CANCELLED, WorkItemStatus.PRECREATED)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.CANCELLED, WorkItemStatus.DRAFT)

    def test_terminal_states(self):
        """Test that terminal states have limited valid transitions."""
        # COMPLETED can only move back to PENDING
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.COMPLETED, WorkItemStatus.EXECUTING)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.COMPLETED, WorkItemStatus.ERROR)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.COMPLETED, WorkItemStatus.NEEDS_REVIEW)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.COMPLETED, WorkItemStatus.CANCELLED)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.COMPLETED, WorkItemStatus.PRECREATED)
        assert not WorkItemStateMachine.is_valid_transition(WorkItemStatus.COMPLETED, WorkItemStatus.DRAFT)
