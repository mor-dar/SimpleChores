"""Unit tests for SimpleChores models."""
from __future__ import annotations

from datetime import datetime

from custom_components.simplechores.models import (
    Kid,
    LedgerEntry,
    PendingApproval,
    PendingChore,
    RecurringChore,
    Reward,
    StorageModel,
)


class TestKid:
    """Test Kid model."""

    def test_kid_creation(self):
        """Test creating a Kid."""
        kid = Kid(id="alice", name="Alice", points=50)
        assert kid.id == "alice"
        assert kid.name == "Alice"
        assert kid.points == 50

    def test_kid_defaults(self):
        """Test Kid with default values."""
        kid = Kid(id="bob", name="Bob")
        assert kid.id == "bob"
        assert kid.name == "Bob"
        assert kid.points == 0


class TestLedgerEntry:
    """Test LedgerEntry model."""

    def test_ledger_entry_creation(self):
        """Test creating a LedgerEntry."""
        ts = datetime.now().timestamp()
        entry = LedgerEntry(
            ts=ts,
            kid_id="alice",
            delta=10,
            reason="Cleaned room",
            kind="earn"
        )
        assert entry.ts == ts
        assert entry.kid_id == "alice"
        assert entry.delta == 10
        assert entry.reason == "Cleaned room"
        assert entry.kind == "earn"

    def test_ledger_entry_spend(self):
        """Test creating a spend LedgerEntry."""
        ts = datetime.now().timestamp()
        entry = LedgerEntry(
            ts=ts,
            kid_id="bob",
            delta=-20,
            reason="Movie night reward",
            kind="spend"
        )
        assert entry.delta == -20
        assert entry.kind == "spend"


class TestReward:
    """Test Reward model."""

    def test_reward_creation(self):
        """Test creating a Reward."""
        reward = Reward(
            id="movie",
            title="Movie Night",
            cost=20,
            description="Family movie night",
            create_calendar_event=True,
            calendar_duration_hours=2
        )
        assert reward.id == "movie"
        assert reward.title == "Movie Night"
        assert reward.cost == 20
        assert reward.description == "Family movie night"
        assert reward.create_calendar_event is True
        assert reward.calendar_duration_hours == 2

    def test_reward_defaults(self):
        """Test Reward with default values."""
        reward = Reward(id="ice_cream", title="Ice Cream", cost=15)
        assert reward.description == ""
        assert reward.create_calendar_event is True
        assert reward.calendar_duration_hours == 2


class TestPendingChore:
    """Test PendingChore model."""

    def test_pending_chore_creation(self):
        """Test creating a PendingChore."""
        ts = datetime.now().timestamp()
        chore = PendingChore(
            todo_uid="uuid-123",
            kid_id="alice",
            title="Take out trash",
            points=5,
            created_ts=ts
        )
        assert chore.todo_uid == "uuid-123"
        assert chore.kid_id == "alice"
        assert chore.title == "Take out trash"
        assert chore.points == 5
        assert chore.created_ts == ts
        assert chore.status == "pending"
        assert chore.completed_ts is None
        assert chore.approved_ts is None

    def test_pending_chore_completed(self):
        """Test completed PendingChore."""
        ts_created = datetime.now().timestamp()
        ts_completed = ts_created + 3600
        chore = PendingChore(
            todo_uid="uuid-456",
            kid_id="bob",
            title="Clean bedroom",
            points=10,
            created_ts=ts_created,
            status="completed",
            completed_ts=ts_completed
        )
        assert chore.status == "completed"
        assert chore.completed_ts == ts_completed


class TestRecurringChore:
    """Test RecurringChore model."""

    def test_recurring_chore_daily(self):
        """Test creating a daily RecurringChore."""
        chore = RecurringChore(
            id="daily-dishes",
            title="Do dishes",
            points=3,
            kid_id="alice",
            schedule_type="daily"
        )
        assert chore.id == "daily-dishes"
        assert chore.title == "Do dishes"
        assert chore.points == 3
        assert chore.kid_id == "alice"
        assert chore.schedule_type == "daily"
        assert chore.day_of_week is None
        assert chore.enabled is True

    def test_recurring_chore_weekly(self):
        """Test creating a weekly RecurringChore."""
        chore = RecurringChore(
            id="weekly-vacuum",
            title="Vacuum living room",
            points=8,
            kid_id="bob",
            schedule_type="weekly",
            day_of_week=5,  # Saturday
            enabled=False
        )
        assert chore.schedule_type == "weekly"
        assert chore.day_of_week == 5
        assert chore.enabled is False


class TestPendingApproval:
    """Test PendingApproval model."""

    def test_pending_approval_creation(self):
        """Test creating a PendingApproval."""
        ts = datetime.now().timestamp()
        approval = PendingApproval(
            id="approval-123",
            todo_uid="uuid-789",
            kid_id="alice",
            title="Organize closet",
            points=15,
            completed_ts=ts
        )
        assert approval.id == "approval-123"
        assert approval.todo_uid == "uuid-789"
        assert approval.kid_id == "alice"
        assert approval.title == "Organize closet"
        assert approval.points == 15
        assert approval.completed_ts == ts
        assert approval.status == "pending_approval"


class TestStorageModel:
    """Test StorageModel."""

    def test_storage_model_defaults(self):
        """Test StorageModel with default values."""
        model = StorageModel()
        assert model.kids == {}
        assert model.ledger == []
        assert model.rewards == {}
        assert model.pending_chores == {}
        assert model.recurring_chores == {}
        assert model.pending_approvals == {}

    def test_storage_model_with_data(self):
        """Test StorageModel with data."""
        kid = Kid(id="alice", name="Alice", points=50)
        entry = LedgerEntry(
            ts=123456.0,
            kid_id="alice",
            delta=10,
            reason="Test",
            kind="earn"
        )
        reward = Reward(id="test", title="Test Reward", cost=10)

        model = StorageModel(
            kids={"alice": kid},
            ledger=[entry],
            rewards={"test": reward}
        )

        assert len(model.kids) == 1
        assert "alice" in model.kids
        assert len(model.ledger) == 1
        assert len(model.rewards) == 1
        assert "test" in model.rewards

