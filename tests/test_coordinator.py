"""Unit tests for SimpleChores coordinator."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.simplechores.coordinator import SimpleChoresCoordinator
from custom_components.simplechores.models import (
    Kid,
    PendingApproval,
    PendingChore,
    RecurringChore,
    Reward,
    StorageModel,
)


class TestSimpleChoresCoordinator:
    """Test SimpleChoresCoordinator."""

    @pytest.fixture
    def mock_hass(self):
        """Return a mock Home Assistant instance."""
        hass = Mock()
        hass.services = Mock()
        hass.services.async_call = AsyncMock()
        return hass

    @pytest.fixture
    def mock_store(self):
        """Return a mock store."""
        store = Mock()
        store.async_load = AsyncMock()
        store.async_save = AsyncMock()
        return store

    @pytest.fixture
    def coordinator(self, mock_hass, mock_store):
        """Return a coordinator instance."""
        with patch('custom_components.simplechores.coordinator.SimpleChoresStore') as mock_store_class:
            mock_store_class.return_value = mock_store
            coord = SimpleChoresCoordinator(mock_hass)
            coord.model = StorageModel()
            coord.store = mock_store
            return coord

    @pytest.mark.asyncio
    async def test_init(self, mock_hass):
        """Test coordinator initialization."""
        with patch('custom_components.simplechores.coordinator.SimpleChoresStore') as mock_store_class:
            coordinator = SimpleChoresCoordinator(mock_hass)
            assert coordinator.hass == mock_hass
            assert coordinator.model is None
            mock_store_class.assert_called_once_with(mock_hass)

    @pytest.mark.asyncio
    async def test_async_init_empty(self, mock_hass, mock_store):
        """Test async_init with empty storage."""
        with patch('custom_components.simplechores.coordinator.SimpleChoresStore') as mock_store_class:
            mock_store_class.return_value = mock_store
            mock_store.async_load.return_value = StorageModel()

            coordinator = SimpleChoresCoordinator(mock_hass)
            await coordinator.async_init()

            assert coordinator.model is not None
            mock_store.async_load.assert_called_once()
            # Should add default rewards when empty
            mock_store.async_save.assert_called_once()
            assert len(coordinator.model.rewards) > 0

    @pytest.mark.asyncio
    async def test_async_init_with_rewards(self, mock_hass, mock_store):
        """Test async_init with existing rewards."""
        existing_model = StorageModel()
        existing_model.rewards = {"test": Reward(id="test", title="Test", cost=10)}

        with patch('custom_components.simplechores.coordinator.SimpleChoresStore') as mock_store_class:
            mock_store_class.return_value = mock_store
            mock_store.async_load.return_value = existing_model

            coordinator = SimpleChoresCoordinator(mock_hass)
            await coordinator.async_init()

            assert coordinator.model is not None
            # Should not add default rewards when some exist
            assert len(coordinator.model.rewards) == 1

    @pytest.mark.asyncio
    async def test_ensure_kid_new(self, coordinator):
        """Test ensuring a new kid."""
        await coordinator.ensure_kid("alice", "Alice")

        assert "alice" in coordinator.model.kids
        assert coordinator.model.kids["alice"].name == "Alice"
        assert coordinator.model.kids["alice"].points == 0

    @pytest.mark.asyncio
    async def test_ensure_kid_existing(self, coordinator):
        """Test ensuring an existing kid."""
        coordinator.model.kids["bob"] = Kid(id="bob", name="Bob", points=50)

        await coordinator.ensure_kid("bob", "Robert")

        # Should not overwrite existing kid
        assert coordinator.model.kids["bob"].name == "Bob"
        assert coordinator.model.kids["bob"].points == 50

    @pytest.mark.asyncio
    async def test_ensure_kid_no_name(self, coordinator):
        """Test ensuring kid without providing name."""
        await coordinator.ensure_kid("charlie")

        assert "charlie" in coordinator.model.kids
        assert coordinator.model.kids["charlie"].name == "charlie"

    def test_get_points_existing_kid(self, coordinator):
        """Test getting points for existing kid."""
        coordinator.model.kids["alice"] = Kid(id="alice", name="Alice", points=75)

        points = coordinator.get_points("alice")
        assert points == 75

    def test_get_points_nonexistent_kid(self, coordinator):
        """Test getting points for nonexistent kid."""
        points = coordinator.get_points("nonexistent")
        assert points == 0

    def test_get_points_no_model(self):
        """Test getting points when model is None."""
        mock_hass = Mock()
        mock_hass.data = {}
        with patch('custom_components.simplechores.coordinator.SimpleChoresStore'):
            coordinator = SimpleChoresCoordinator(mock_hass)
            coordinator.model = None

            points = coordinator.get_points("alice")
            assert points == 0

    @pytest.mark.asyncio
    async def test_add_points_existing_kid(self, coordinator):
        """Test adding points to existing kid."""
        coordinator.model.kids["alice"] = Kid(id="alice", name="Alice", points=10)
        coordinator._update_entities = AsyncMock()

        await coordinator.add_points("alice", 25, "Cleaned room", "earn")

        assert coordinator.model.kids["alice"].points == 35
        assert len(coordinator.model.ledger) == 1
        entry = coordinator.model.ledger[0]
        assert entry.kid_id == "alice"
        assert entry.delta == 25
        assert entry.reason == "Cleaned room"
        assert entry.kind == "earn"
        coordinator._update_entities.assert_called_once_with("alice")

    @pytest.mark.asyncio
    async def test_add_points_new_kid(self, coordinator):
        """Test adding points to new kid."""
        coordinator._update_entities = AsyncMock()

        await coordinator.add_points("bob", 15, "First points", "earn")

        assert "bob" in coordinator.model.kids
        assert coordinator.model.kids["bob"].points == 15
        assert coordinator.model.kids["bob"].name == "bob"

    @pytest.mark.asyncio
    async def test_remove_points(self, coordinator):
        """Test removing points."""
        coordinator.model.kids["alice"] = Kid(id="alice", name="Alice", points=50)
        coordinator._update_entities = AsyncMock()

        await coordinator.remove_points("alice", 20, "Bought reward", "spend")

        assert coordinator.model.kids["alice"].points == 30
        assert len(coordinator.model.ledger) == 1
        entry = coordinator.model.ledger[0]
        assert entry.delta == -20
        assert entry.kind == "spend"

    def test_get_rewards(self, coordinator):
        """Test getting all rewards."""
        reward1 = Reward(id="movie", title="Movie", cost=20)
        reward2 = Reward(id="ice_cream", title="Ice Cream", cost=15)
        coordinator.model.rewards = {"movie": reward1, "ice_cream": reward2}

        rewards = coordinator.get_rewards()
        assert len(rewards) == 2
        assert reward1 in rewards
        assert reward2 in rewards

    def test_get_reward_existing(self, coordinator):
        """Test getting specific reward that exists."""
        reward = Reward(id="movie", title="Movie", cost=20)
        coordinator.model.rewards = {"movie": reward}

        result = coordinator.get_reward("movie")
        assert result == reward

    def test_get_reward_nonexistent(self, coordinator):
        """Test getting specific reward that doesn't exist."""
        result = coordinator.get_reward("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_add_reward(self, coordinator):
        """Test adding a new reward."""
        reward_id = await coordinator.add_reward("New Reward", 30, "Description", False)

        assert reward_id in coordinator.model.rewards
        reward = coordinator.model.rewards[reward_id]
        assert reward.title == "New Reward"
        assert reward.cost == 30
        assert reward.description == "Description"
        assert reward.create_calendar_event is False

    @pytest.mark.asyncio
    async def test_create_pending_chore(self, coordinator):
        """Test creating a pending chore."""
        todo_uid = await coordinator.create_pending_chore("alice", "Take out trash", 5)

        assert todo_uid in coordinator.model.pending_chores
        chore = coordinator.model.pending_chores[todo_uid]
        assert chore.kid_id == "alice"
        assert chore.title == "Take out trash"
        assert chore.points == 5
        assert chore.status == "pending"

    @pytest.mark.asyncio
    async def test_complete_chore_by_uid_success(self, coordinator):
        """Test completing a chore by UID successfully."""
        # Create a pending chore
        todo_uid = await coordinator.create_pending_chore("bob", "Clean room", 10)
        coordinator._update_entities = AsyncMock()

        success = await coordinator.complete_chore_by_uid(todo_uid)

        assert success is True
        assert todo_uid not in coordinator.model.pending_chores
        # Should have added points
        assert coordinator.model.kids["bob"].points == 10
        assert len(coordinator.model.ledger) == 1

    @pytest.mark.asyncio
    async def test_complete_chore_by_uid_not_found(self, coordinator):
        """Test completing a chore that doesn't exist."""
        success = await coordinator.complete_chore_by_uid("nonexistent-uid")
        assert success is False

    def test_get_pending_chore_existing(self, coordinator):
        """Test getting existing pending chore."""
        chore = PendingChore(
            todo_uid="test-uid",
            kid_id="alice",
            title="Test chore",
            points=5,
            created_ts=datetime.now().timestamp()
        )
        coordinator.model.pending_chores["test-uid"] = chore

        result = coordinator.get_pending_chore("test-uid")
        assert result == chore

    def test_get_pending_chore_nonexistent(self, coordinator):
        """Test getting nonexistent pending chore."""
        result = coordinator.get_pending_chore("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_recurring_chore_daily(self, coordinator):
        """Test creating a daily recurring chore."""
        chore_id = await coordinator.create_recurring_chore("alice", "Feed pets", 3, "daily")

        assert chore_id in coordinator.model.recurring_chores
        chore = coordinator.model.recurring_chores[chore_id]
        assert chore.kid_id == "alice"
        assert chore.title == "Feed pets"
        assert chore.points == 3
        assert chore.schedule_type == "daily"
        assert chore.day_of_week is None
        assert chore.enabled is True

    @pytest.mark.asyncio
    async def test_create_recurring_chore_weekly(self, coordinator):
        """Test creating a weekly recurring chore."""
        chore_id = await coordinator.create_recurring_chore("bob", "Vacuum", 8, "weekly", 5)

        chore = coordinator.model.recurring_chores[chore_id]
        assert chore.schedule_type == "weekly"
        assert chore.day_of_week == 5

    def test_get_recurring_chores_all(self, coordinator):
        """Test getting all recurring chores."""
        chore1 = RecurringChore(id="1", title="Daily", points=3, kid_id="alice", schedule_type="daily")
        chore2 = RecurringChore(id="2", title="Weekly", points=8, kid_id="bob", schedule_type="weekly")
        coordinator.model.recurring_chores = {"1": chore1, "2": chore2}

        chores = coordinator.get_recurring_chores()
        assert len(chores) == 2
        assert chore1 in chores
        assert chore2 in chores

    def test_get_recurring_chores_filtered(self, coordinator):
        """Test getting recurring chores filtered by kid."""
        chore1 = RecurringChore(id="1", title="Daily", points=3, kid_id="alice", schedule_type="daily")
        chore2 = RecurringChore(id="2", title="Weekly", points=8, kid_id="bob", schedule_type="weekly")
        coordinator.model.recurring_chores = {"1": chore1, "2": chore2}

        chores = coordinator.get_recurring_chores("alice")
        assert len(chores) == 1
        assert chore1 in chores
        assert chore2 not in chores

    @pytest.mark.asyncio
    async def test_generate_daily_chores(self, coordinator):
        """Test generating daily chores."""
        chore1 = RecurringChore(id="1", title="Daily1", points=3, kid_id="alice", schedule_type="daily", enabled=True)
        chore2 = RecurringChore(id="2", title="Daily2", points=5, kid_id="bob", schedule_type="daily", enabled=False)
        chore3 = RecurringChore(id="3", title="Weekly", points=8, kid_id="alice", schedule_type="weekly", enabled=True)
        coordinator.model.recurring_chores = {"1": chore1, "2": chore2, "3": chore3}

        await coordinator.generate_daily_chores()

        # Should only create pending chore for enabled daily chore
        pending_chores = list(coordinator.model.pending_chores.values())
        assert len(pending_chores) == 1
        assert pending_chores[0].title == "Daily1"
        assert pending_chores[0].kid_id == "alice"

    @pytest.mark.asyncio
    async def test_generate_weekly_chores(self, coordinator):
        """Test generating weekly chores."""
        chore1 = RecurringChore(
            id="1", title="Weekly1", points=8, kid_id="alice",
            schedule_type="weekly", day_of_week=5, enabled=True
        )
        chore2 = RecurringChore(
            id="2", title="Weekly2", points=10, kid_id="bob",
            schedule_type="weekly", day_of_week=3, enabled=True
        )
        coordinator.model.recurring_chores = {"1": chore1, "2": chore2}

        await coordinator.generate_weekly_chores(5)  # Saturday

        # Should only create pending chore for Saturday chore
        pending_chores = list(coordinator.model.pending_chores.values())
        assert len(pending_chores) == 1
        assert pending_chores[0].title == "Weekly1"

    @pytest.mark.asyncio
    async def test_request_approval(self, coordinator):
        """Test requesting approval for a chore."""
        # Create a pending chore first
        todo_uid = await coordinator.create_pending_chore("alice", "Big project", 20)
        coordinator._update_approval_buttons = AsyncMock()

        approval_id = await coordinator.request_approval(todo_uid)

        assert approval_id is not None
        assert approval_id in coordinator.model.pending_approvals

        approval = coordinator.model.pending_approvals[approval_id]
        assert approval.todo_uid == todo_uid
        assert approval.kid_id == "alice"
        assert approval.title == "Big project"
        assert approval.points == 20
        assert approval.status == "pending_approval"

        # Original chore should be marked as completed
        chore = coordinator.model.pending_chores[todo_uid]
        assert chore.status == "completed"
        assert chore.completed_ts is not None

    @pytest.mark.asyncio
    async def test_request_approval_nonexistent_chore(self, coordinator):
        """Test requesting approval for nonexistent chore."""
        approval_id = await coordinator.request_approval("nonexistent")
        assert approval_id is None

    @pytest.mark.asyncio
    async def test_approve_chore(self, coordinator):
        """Test approving a chore."""
        # Set up approval
        todo_uid = await coordinator.create_pending_chore("bob", "Project", 15)
        approval_id = await coordinator.request_approval(todo_uid)
        coordinator._update_entities = AsyncMock()

        success = await coordinator.approve_chore(approval_id)

        assert success is True
        # Points should be awarded
        assert coordinator.model.kids["bob"].points == 15
        # Approval status updated
        approval = coordinator.model.pending_approvals[approval_id]
        assert approval.status == "approved"
        # Original chore status updated
        chore = coordinator.model.pending_chores[todo_uid]
        assert chore.status == "approved"
        assert chore.approved_ts is not None

    @pytest.mark.asyncio
    async def test_approve_chore_nonexistent(self, coordinator):
        """Test approving nonexistent chore."""
        success = await coordinator.approve_chore("nonexistent")
        assert success is False

    @pytest.mark.asyncio
    async def test_reject_chore(self, coordinator):
        """Test rejecting a chore."""
        # Ensure kid exists
        await coordinator.ensure_kid("alice", "Alice")

        # Set up approval
        todo_uid = await coordinator.create_pending_chore("alice", "Project", 10)
        approval_id = await coordinator.request_approval(todo_uid)
        coordinator._update_approval_buttons = AsyncMock()

        success = await coordinator.reject_chore(approval_id, "Not good enough")

        assert success is True
        # No points should be awarded
        assert coordinator.model.kids["alice"].points == 0
        # Approval status updated
        approval = coordinator.model.pending_approvals[approval_id]
        assert approval.status == "rejected"
        # Original chore status updated
        chore = coordinator.model.pending_chores[todo_uid]
        assert chore.status == "rejected"

    @pytest.mark.asyncio
    async def test_reject_chore_nonexistent(self, coordinator):
        """Test rejecting nonexistent chore."""
        success = await coordinator.reject_chore("nonexistent")
        assert success is False

    def test_get_pending_approvals(self, coordinator):
        """Test getting pending approvals."""
        approval1 = PendingApproval(
            id="1", todo_uid="uid1", kid_id="alice", title="Task1",
            points=10, completed_ts=123456.0, status="pending_approval"
        )
        approval2 = PendingApproval(
            id="2", todo_uid="uid2", kid_id="bob", title="Task2",
            points=15, completed_ts=123457.0, status="approved"
        )
        coordinator.model.pending_approvals = {"1": approval1, "2": approval2}

        pending = coordinator.get_pending_approvals()
        assert len(pending) == 1
        assert approval1 in pending
        assert approval2 not in pending

