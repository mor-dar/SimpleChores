"""Unit tests for SimpleChores platform entities."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.simplechores.button import SimpleChoresCreateChoreButton, async_setup_entry as button_setup
from custom_components.simplechores.const import DOMAIN
from custom_components.simplechores.coordinator import SimpleChoresCoordinator
from custom_components.simplechores.models import LedgerEntry, Reward, StorageModel
from custom_components.simplechores.number import SimpleChoresNumber, async_setup_entry as number_setup
from custom_components.simplechores.sensor import (
    SimpleChoresWeekSensor,
)
from custom_components.simplechores.text import (
    SimpleChoresChoreTitle,
    async_setup_entry as text_setup,
)


class TestSimpleChoresNumber:
    """Test SimpleChores number entity."""

    @pytest.fixture
    def mock_coordinator(self):
        """Return a mock coordinator."""
        coordinator = Mock(spec=SimpleChoresCoordinator)
        coordinator.model = StorageModel()
        coordinator.get_points = Mock(return_value=50)
        coordinator.add_points = AsyncMock()
        coordinator.remove_points = AsyncMock()
        coordinator.ensure_kid = AsyncMock()
        return coordinator

    def test_init(self, mock_coordinator):
        """Test number entity initialization."""
        entity = SimpleChoresNumber(mock_coordinator, "alice")

        assert entity._coord == mock_coordinator
        assert entity._kid_id == "alice"
        assert entity._attr_unique_id == f"{DOMAIN}_alice_points"
        assert entity._attr_name == "Alice Points"
        assert entity._attr_native_min_value == 0
        assert entity._attr_native_max_value == 99999
        assert entity._attr_native_step == 1

        # Should register itself with coordinator
        assert hasattr(mock_coordinator, '_entities')
        assert mock_coordinator._entities["alice"] == entity

    def test_native_value(self, mock_coordinator):
        """Test getting native value."""
        mock_coordinator.get_points.return_value = 75
        entity = SimpleChoresNumber(mock_coordinator, "alice")

        value = entity.native_value
        assert value == 75.0
        mock_coordinator.get_points.assert_called_once_with("alice")

    @pytest.mark.asyncio
    async def test_async_set_native_value_increase(self, mock_coordinator):
        """Test setting value to increase points."""
        mock_coordinator.get_points.return_value = 50
        entity = SimpleChoresNumber(mock_coordinator, "alice")

        # Mock the hass instance to avoid state writing issues
        entity.hass = Mock()
        entity.async_write_ha_state = Mock()

        await entity.async_set_native_value(75.0)

        mock_coordinator.add_points.assert_called_once_with("alice", 25, "Manual adjust", "adjust")
        mock_coordinator.remove_points.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_set_native_value_decrease(self, mock_coordinator):
        """Test setting value to decrease points."""
        mock_coordinator.get_points.return_value = 50
        entity = SimpleChoresNumber(mock_coordinator, "alice")

        # Mock the hass instance to avoid state writing issues
        entity.hass = Mock()
        entity.async_write_ha_state = Mock()

        await entity.async_set_native_value(30.0)

        mock_coordinator.remove_points.assert_called_once_with("alice", 20, "Manual adjust", "adjust")
        mock_coordinator.add_points.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_set_native_value_no_change(self, mock_coordinator):
        """Test setting value with no change."""
        mock_coordinator.get_points.return_value = 50
        entity = SimpleChoresNumber(mock_coordinator, "alice")

        # Mock the hass instance to avoid state writing issues
        entity.hass = Mock()
        entity.async_write_ha_state = Mock()

        await entity.async_set_native_value(50.0)

        mock_coordinator.add_points.assert_not_called()
        mock_coordinator.remove_points.assert_not_called()

    @pytest.mark.asyncio
    async def test_number_setup_entry(self):
        """Test number platform setup."""
        mock_hass = Mock()
        mock_entry = Mock()
        mock_entry.entry_id = "test_entry"
        mock_entry.data = {"kids": "alice,bob,charlie"}
        add_entities = Mock()

        mock_coordinator = Mock(spec=SimpleChoresCoordinator)
        mock_coordinator.ensure_kid = AsyncMock()
        mock_hass.data = {DOMAIN: {"test_entry": mock_coordinator}}

        await number_setup(mock_hass, mock_entry, add_entities)

        # Should create entities for each kid
        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        assert len(entities) == 3
        assert all(isinstance(e, SimpleChoresNumber) for e in entities)

        # Should ensure all kids exist
        assert mock_coordinator.ensure_kid.call_count == 3


class TestSimpleChoresWeekSensor:
    """Test SimpleChores week sensor."""

    @pytest.fixture
    def mock_coordinator_with_ledger(self):
        """Return a mock coordinator with ledger data."""
        coordinator = Mock(spec=SimpleChoresCoordinator)
        model = StorageModel()

        # Create ledger entries for different times
        now = datetime.now()
        this_week_start = (now - timedelta(days=now.weekday())).timestamp()
        last_week = this_week_start - 7 * 24 * 3600

        model.ledger = [
            LedgerEntry(ts=this_week_start + 1000, kid_id="alice", delta=10, reason="This week", kind="earn"),
            LedgerEntry(ts=this_week_start + 2000, kid_id="alice", delta=5, reason="This week 2", kind="earn"),
            LedgerEntry(ts=last_week, kid_id="alice", delta=15, reason="Last week", kind="earn"),
            LedgerEntry(ts=this_week_start + 1500, kid_id="bob", delta=8, reason="Bob this week", kind="earn"),
        ]

        coordinator.model = model
        return coordinator

    def test_week_sensor_init(self, mock_coordinator_with_ledger):
        """Test week sensor initialization."""
        sensor = SimpleChoresWeekSensor(mock_coordinator_with_ledger, "alice")

        assert sensor._coord == mock_coordinator_with_ledger
        assert sensor._kid_id == "alice"
        assert sensor._attr_unique_id == f"{DOMAIN}_alice_points_week"
        assert sensor._attr_name == "SimpleChores Alice Points (This Week)"

    def test_week_sensor_native_value(self, mock_coordinator_with_ledger):
        """Test week sensor native value calculation."""
        sensor = SimpleChoresWeekSensor(mock_coordinator_with_ledger, "alice")

        # Should sum only this week's entries for alice
        value = sensor.native_value
        assert value == 15  # 10 + 5 from this week

    def test_week_sensor_empty_ledger(self):
        """Test week sensor with empty ledger."""
        coordinator = Mock(spec=SimpleChoresCoordinator)
        coordinator.model = StorageModel()
        sensor = SimpleChoresWeekSensor(coordinator, "alice")

        value = sensor.native_value
        assert value == 0

    def test_week_sensor_no_model(self):
        """Test week sensor with no model."""
        coordinator = Mock(spec=SimpleChoresCoordinator)
        coordinator.model = None
        sensor = SimpleChoresWeekSensor(coordinator, "alice")

        value = sensor.native_value
        assert value == 0
        assert sensor.available is False

    def test_week_sensor_available(self, mock_coordinator_with_ledger):
        """Test week sensor availability."""
        sensor = SimpleChoresWeekSensor(mock_coordinator_with_ledger, "alice")
        assert sensor.available is True


class TestSimpleChoresText:
    """Test SimpleChores text entities."""

    @pytest.fixture
    def mock_coordinator(self):
        """Return a mock coordinator."""
        coordinator = Mock(spec=SimpleChoresCoordinator)
        coordinator.get_rewards = Mock(return_value=[])
        return coordinator

    def test_chore_title_init(self, mock_coordinator):
        """Test chore title entity initialization."""
        entity = SimpleChoresChoreTitle(mock_coordinator)

        assert entity._coord == mock_coordinator
        assert entity._attr_unique_id == f"{DOMAIN}_chore_title_input"
        assert entity._attr_name == "SimpleChores Chore Title"
        assert entity._attr_native_value == ""
        assert entity._attr_icon == "mdi:text"
        assert entity._attr_native_min == 1
        assert entity._attr_native_max == 100
        assert entity._attr_mode == "text"

    def test_chore_title_native_value(self, mock_coordinator):
        """Test chore title native value."""
        entity = SimpleChoresChoreTitle(mock_coordinator)
        assert entity.native_value == ""

    @pytest.mark.asyncio
    async def test_chore_title_set_value(self, mock_coordinator):
        """Test setting chore title value."""
        entity = SimpleChoresChoreTitle(mock_coordinator)
        entity.async_write_ha_state = Mock()

        await entity.async_set_value("Clean room")

        assert entity._attr_native_value == "Clean room"
        entity.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_text_setup_entry(self):
        """Test text platform setup."""
        mock_hass = Mock()
        mock_entry = Mock()
        mock_entry.entry_id = "test_entry"
        mock_entry.data = {"kids": "alice,bob"}
        add_entities = Mock()

        mock_coordinator = Mock(spec=SimpleChoresCoordinator)
        mock_hass.data = {DOMAIN: {"test_entry": mock_coordinator}}

        await text_setup(mock_hass, mock_entry, add_entities)

        # Should create multiple text input entities
        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        assert len(entities) == 8  # Various input helpers


class TestSimpleChoresButton:
    """Test SimpleChores button entities."""

    @pytest.fixture
    def mock_coordinator(self):
        """Return a mock coordinator."""
        coordinator = Mock(spec=SimpleChoresCoordinator)
        coordinator.get_rewards = Mock(return_value=[
            Reward(id="movie", title="Movie Night", cost=20)
        ])
        return coordinator

    def test_create_chore_button_init(self, mock_coordinator):
        """Test create chore button initialization."""
        mock_hass = Mock()
        button = SimpleChoresCreateChoreButton(mock_coordinator, mock_hass)

        assert button._coord == mock_coordinator
        assert button._hass == mock_hass
        assert button._attr_unique_id == f"{DOMAIN}_create_chore_button"
        assert button._attr_name == "SimpleChores Create Chore"
        assert button._attr_icon == "mdi:plus-circle"

    @pytest.mark.asyncio
    async def test_button_setup_entry(self):
        """Test button platform setup."""
        mock_hass = Mock()
        mock_entry = Mock()
        mock_entry.entry_id = "test_entry"
        mock_entry.data = {"kids": "alice,bob"}
        add_entities = Mock()

        mock_coordinator = Mock(spec=SimpleChoresCoordinator)
        mock_coordinator.get_rewards = Mock(return_value=[
            Reward(id="movie", title="Movie Night", cost=20),
            Reward(id="ice_cream", title="Ice Cream", cost=15)
        ])
        mock_coordinator.get_pending_approvals = Mock(return_value=[])
        mock_hass.data = {DOMAIN: {"test_entry": mock_coordinator}}

        await button_setup(mock_hass, mock_entry, add_entities)

        # Should create buttons for various functions plus reward buttons
        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        # Should include: create chore, create recurring, generate daily, approval status,
        # reset rejected, plus 2 rewards × 2 kids = 4 reward buttons = 9 total
        assert len(entities) == 9

