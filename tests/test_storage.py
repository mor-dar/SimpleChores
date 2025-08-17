"""Unit tests for SimpleChores storage."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.simplechores.const import STORAGE_KEY, STORAGE_VERSION
from custom_components.simplechores.models import Kid, LedgerEntry, PendingChore, Reward, StorageModel
from custom_components.simplechores.storage import SimpleChoresStore


class TestSimpleChoresStore:
    """Test SimpleChoresStore."""

    @pytest.fixture
    def mock_hass(self):
        """Return a mock Home Assistant instance."""
        return Mock()

    @pytest.fixture
    def mock_store_data(self):
        """Return mock store data."""
        return {
            "kids": {
                "alice": {"id": "alice", "name": "Alice", "points": 50},
                "bob": {"id": "bob", "name": "Bob", "points": 30}
            },
            "ledger": [
                {
                    "ts": 1234567890.0,
                    "kid_id": "alice",
                    "delta": 10,
                    "reason": "Cleaned room",
                    "kind": "earn"
                }
            ],
            "rewards": {
                "movie": {
                    "id": "movie",
                    "title": "Movie Night",
                    "cost": 20,
                    "description": "Family movie night",
                    "create_calendar_event": True,
                    "calendar_duration_hours": 2
                }
            },
            "pending_chores": {
                "uuid-123": {
                    "todo_uid": "uuid-123",
                    "kid_id": "alice",
                    "title": "Take out trash",
                    "points": 5,
                    "created_ts": 1234567890.0,
                    "status": "pending",
                    "completed_ts": None,
                    "approved_ts": None
                }
            }
        }

    def test_init(self, mock_hass):
        """Test SimpleChoresStore initialization."""
        with patch('custom_components.simplechores.storage.Store') as mock_store_class:
            store = SimpleChoresStore(mock_hass)
            mock_store_class.assert_called_once_with(mock_hass, STORAGE_VERSION, STORAGE_KEY)
            assert store._store == mock_store_class.return_value

    @pytest.mark.asyncio
    async def test_async_load_with_data(self, mock_hass, mock_store_data):
        """Test loading data from store."""
        with patch('custom_components.simplechores.storage.Store') as mock_store_class:
            mock_store = mock_store_class.return_value
            mock_store.async_load = AsyncMock(return_value=mock_store_data)

            store = SimpleChoresStore(mock_hass)
            model = await store.async_load()

            # Check kids
            assert len(model.kids) == 2
            assert "alice" in model.kids
            assert "bob" in model.kids
            assert model.kids["alice"].name == "Alice"
            assert model.kids["alice"].points == 50
            assert model.kids["bob"].name == "Bob"
            assert model.kids["bob"].points == 30

            # Check ledger
            assert len(model.ledger) == 1
            entry = model.ledger[0]
            assert entry.kid_id == "alice"
            assert entry.delta == 10
            assert entry.reason == "Cleaned room"
            assert entry.kind == "earn"

            # Check rewards
            assert len(model.rewards) == 1
            assert "movie" in model.rewards
            reward = model.rewards["movie"]
            assert reward.title == "Movie Night"
            assert reward.cost == 20
            assert reward.create_calendar_event is True

            # Check pending chores
            assert len(model.pending_chores) == 1
            assert "uuid-123" in model.pending_chores
            chore = model.pending_chores["uuid-123"]
            assert chore.kid_id == "alice"
            assert chore.title == "Take out trash"
            assert chore.points == 5
            assert chore.status == "pending"

    @pytest.mark.asyncio
    async def test_async_load_empty(self, mock_hass):
        """Test loading with no existing data."""
        with patch('custom_components.simplechores.storage.Store') as mock_store_class:
            mock_store = mock_store_class.return_value
            mock_store.async_load = AsyncMock(return_value=None)

            store = SimpleChoresStore(mock_hass)
            model = await store.async_load()

            assert len(model.kids) == 0
            assert len(model.ledger) == 0
            assert len(model.rewards) == 0
            assert len(model.pending_chores) == 0

    @pytest.mark.asyncio
    async def test_async_load_partial_data(self, mock_hass):
        """Test loading with partial data."""
        partial_data = {
            "kids": {"charlie": {"id": "charlie", "name": "Charlie", "points": 25}}
        }

        with patch('custom_components.simplechores.storage.Store') as mock_store_class:
            mock_store = mock_store_class.return_value
            mock_store.async_load = AsyncMock(return_value=partial_data)

            store = SimpleChoresStore(mock_hass)
            model = await store.async_load()

            assert len(model.kids) == 1
            assert "charlie" in model.kids
            assert len(model.ledger) == 0
            assert len(model.rewards) == 0
            assert len(model.pending_chores) == 0

    @pytest.mark.asyncio
    async def test_async_save(self, mock_hass):
        """Test saving data to store."""
        with patch('custom_components.simplechores.storage.Store') as mock_store_class:
            mock_store = mock_store_class.return_value
            mock_store.async_save = AsyncMock()

            store = SimpleChoresStore(mock_hass)

            # Create test model
            kid = Kid(id="test", name="Test", points=100)
            entry = LedgerEntry(
                ts=1234567890.0,
                kid_id="test",
                delta=50,
                reason="Test entry",
                kind="earn"
            )
            reward = Reward(id="test_reward", title="Test Reward", cost=25)
            chore = PendingChore(
                todo_uid="test-uuid",
                kid_id="test",
                title="Test chore",
                points=10,
                created_ts=1234567890.0
            )

            model = StorageModel(
                kids={"test": kid},
                ledger=[entry],
                rewards={"test_reward": reward},
                pending_chores={"test-uuid": chore}
            )

            await store.async_save(model)

            # Verify the data structure passed to async_save
            mock_store.async_save.assert_called_once()
            saved_data = mock_store.async_save.call_args[0][0]

            # Check kids data
            assert "kids" in saved_data
            assert "test" in saved_data["kids"]
            assert saved_data["kids"]["test"]["name"] == "Test"
            assert saved_data["kids"]["test"]["points"] == 100

            # Check ledger data
            assert "ledger" in saved_data
            assert len(saved_data["ledger"]) == 1
            assert saved_data["ledger"][0]["kid_id"] == "test"
            assert saved_data["ledger"][0]["delta"] == 50

            # Check rewards data
            assert "rewards" in saved_data
            assert "test_reward" in saved_data["rewards"]
            assert saved_data["rewards"]["test_reward"]["title"] == "Test Reward"

            # Check pending chores data
            assert "pending_chores" in saved_data
            assert "test-uuid" in saved_data["pending_chores"]
            assert saved_data["pending_chores"]["test-uuid"]["title"] == "Test chore"

    @pytest.mark.asyncio
    async def test_async_save_empty_model(self, mock_hass):
        """Test saving empty model."""
        with patch('custom_components.simplechores.storage.Store') as mock_store_class:
            mock_store = mock_store_class.return_value
            mock_store.async_save = AsyncMock()

            store = SimpleChoresStore(mock_hass)
            model = StorageModel()

            await store.async_save(model)

            mock_store.async_save.assert_called_once()
            saved_data = mock_store.async_save.call_args[0][0]

            assert saved_data["kids"] == {}
            assert saved_data["ledger"] == []
            assert saved_data["rewards"] == {}
            assert saved_data["pending_chores"] == {}

