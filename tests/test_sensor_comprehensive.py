"""Comprehensive tests for sensor platform functionality."""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.simplechores.sensor import (
    SimpleChoresWeekSensor,
    SimpleChoresTotalSensor, 
    SimpleChoresPendingApprovalsSensor,
    async_setup_entry
)
from custom_components.simplechores.coordinator import SimpleChoresCoordinator
from custom_components.simplechores.models import StorageModel, LedgerEntry, PendingApproval


class TestSimpleChoresWeekSensor:
    """Test weekly points sensor functionality."""
    
    @pytest.fixture
    def week_sensor(self, coordinator):
        return SimpleChoresWeekSensor(coordinator, "alice")
    
    @pytest.fixture
    def coordinator_with_ledger(self, coordinator):
        """Coordinator with sample ledger entries."""
        now = datetime.now()
        monday_this_week = now - timedelta(days=now.weekday())
        last_week = monday_this_week - timedelta(days=7)
        
        coordinator.model.ledger = [
            # This week entries
            LedgerEntry(
                kid_id="alice", 
                delta=5, 
                reason="Chore completed",
                ts=monday_this_week.timestamp(),
                kind="earn"
            ),
            LedgerEntry(
                kid_id="alice",
                delta=3,
                reason="Bonus points", 
                ts=(monday_this_week + timedelta(days=2)).timestamp(),
                kind="earn"
            ),
            LedgerEntry(
                kid_id="bob",
                delta=4,
                reason="Bob's chore",
                ts=(monday_this_week + timedelta(days=1)).timestamp(),
                kind="earn"
            ),
            # Last week entries (should not count)
            LedgerEntry(
                kid_id="alice",
                delta=10,
                reason="Last week chore",
                ts=last_week.timestamp(),
                kind="earn"
            ),
            # Negative entry (spending)
            LedgerEntry(
                kid_id="alice",
                delta=-2,
                reason="Reward claimed",
                ts=(monday_this_week + timedelta(days=3)).timestamp(),
                kind="spend"
            )
        ]
        return coordinator
    
    def test_sensor_properties(self, week_sensor):
        """Test basic sensor properties."""
        assert week_sensor._attr_unique_id == "simplechores_alice_points_week"
        assert week_sensor._attr_name == "Alice Points (This Week)"
        assert week_sensor._kid_id == "alice"
    
    def test_native_value_with_data(self, coordinator_with_ledger):
        """Test native value calculation with ledger data."""
        sensor = SimpleChoresWeekSensor(coordinator_with_ledger, "alice")
        
        # Should sum only Alice's entries from this week: 5 + 3 + (-2) = 6
        assert sensor.native_value == 6
    
    def test_native_value_different_kid(self, coordinator_with_ledger):
        """Test native value for different kid."""
        sensor = SimpleChoresWeekSensor(coordinator_with_ledger, "bob")
        
        # Should sum only Bob's entries from this week: 4
        assert sensor.native_value == 4
    
    def test_native_value_nonexistent_kid(self, coordinator_with_ledger):
        """Test native value for kid with no entries."""
        sensor = SimpleChoresWeekSensor(coordinator_with_ledger, "charlie")
        
        # Should return 0 for kid with no entries
        assert sensor.native_value == 0
    
    def test_native_value_empty_ledger(self, coordinator):
        """Test native value with empty ledger."""
        sensor = SimpleChoresWeekSensor(coordinator, "alice")
        coordinator.model.ledger = []
        
        assert sensor.native_value == 0
    
    def test_native_value_no_model(self, coordinator):
        """Test native value when model is None."""
        sensor = SimpleChoresWeekSensor(coordinator, "alice")
        coordinator.model = None
        
        assert sensor.native_value == 0
    
    def test_available_with_model(self, coordinator):
        """Test availability when model exists."""
        sensor = SimpleChoresWeekSensor(coordinator, "alice")
        
        assert sensor.available is True
    
    def test_available_no_model(self, coordinator):
        """Test availability when model is None.""" 
        sensor = SimpleChoresWeekSensor(coordinator, "alice")
        coordinator.model = None
        
        assert sensor.available is False
    
    def test_week_boundary_calculation(self, coordinator):
        """Test that week calculation respects Monday start."""
        sensor = SimpleChoresWeekSensor(coordinator, "alice")
        
        # Create entries for different days of the week
        now = datetime.now()
        
        # Find last Monday
        days_since_monday = now.weekday()
        last_monday = now - timedelta(days=days_since_monday)
        
        coordinator.model.ledger = [
            # Sunday before this week (should not count)
            LedgerEntry(
                kid_id="alice",
                delta=10,
                reason="Sunday before",
                ts=(last_monday - timedelta(days=1)).timestamp()
            ),
            # Monday this week (should count)
            LedgerEntry(
                kid_id="alice", 
                delta=5,
                reason="Monday this week",
                ts=last_monday.timestamp()
            ),
            # Sunday this week (should count)
            LedgerEntry(
                kid_id="alice",
                delta=3,
                reason="Sunday this week", 
                ts=(last_monday + timedelta(days=6)).timestamp()
            )
        ]
        
        # Should only count entries from Monday onwards: 5 + 3 = 8
        assert sensor.native_value == 8


class TestSimpleChoresTotalSensor:
    """Test total points sensor functionality."""
    
    @pytest.fixture
    def total_sensor(self, coordinator):
        return SimpleChoresTotalSensor(coordinator, "alice")
    
    @pytest.fixture
    def coordinator_with_mixed_ledger(self, coordinator):
        """Coordinator with mixed positive and negative ledger entries."""
        coordinator.model.ledger = [
            # Positive entries (earnings)
            LedgerEntry(kid_id="alice", delta=10, reason="Chore 1", ts=datetime.now().timestamp(), kind="earn"),
            LedgerEntry(kid_id="alice", delta=5, reason="Chore 2", ts=datetime.now().timestamp(), kind="earn"),
            LedgerEntry(kid_id="alice", delta=8, reason="Bonus", ts=datetime.now().timestamp(), kind="earn"),
            
            # Negative entries (spending - should not count in total earned)
            LedgerEntry(kid_id="alice", delta=-3, reason="Reward", ts=datetime.now().timestamp(), kind="spend"),
            LedgerEntry(kid_id="alice", delta=-5, reason="Another reward", ts=datetime.now().timestamp(), kind="spend"),
            
            # Other kid's entries (should not count)
            LedgerEntry(kid_id="bob", delta=15, reason="Bob's chore", ts=datetime.now().timestamp(), kind="earn"),
            
            # Zero entry (should not count)
            LedgerEntry(kid_id="alice", delta=0, reason="Adjustment", ts=datetime.now().timestamp(), kind="adjust")
        ]
        return coordinator
    
    def test_sensor_properties(self, total_sensor):
        """Test basic sensor properties."""
        assert total_sensor._attr_unique_id == "simplechores_alice_points_total"
        assert total_sensor._attr_name == "Alice Points (Total Earned)"
        assert total_sensor._attr_icon == "mdi:star-circle-outline"
        assert total_sensor._kid_id == "alice"
    
    def test_native_value_only_positive_deltas(self, coordinator_with_mixed_ledger):
        """Test that only positive deltas are counted."""
        sensor = SimpleChoresTotalSensor(coordinator_with_mixed_ledger, "alice")
        
        # Should sum only positive entries for alice: 10 + 5 + 8 = 23
        assert sensor.native_value == 23
    
    def test_native_value_different_kid(self, coordinator_with_mixed_ledger):
        """Test total for different kid."""
        sensor = SimpleChoresTotalSensor(coordinator_with_mixed_ledger, "bob")
        
        # Should sum only Bob's positive entries: 15
        assert sensor.native_value == 15
    
    def test_native_value_only_negative_entries(self, coordinator):
        """Test total when kid only has negative entries."""
        coordinator.model.ledger = [
            LedgerEntry(kid_id="alice", delta=-5, reason="Reward 1", ts=datetime.now().timestamp(), kind="spend"),
            LedgerEntry(kid_id="alice", delta=-3, reason="Reward 2", ts=datetime.now().timestamp(), kind="spend")
        ]
        
        sensor = SimpleChoresTotalSensor(coordinator, "alice")
        
        # Should return 0 when no positive entries
        assert sensor.native_value == 0
    
    def test_native_value_empty_ledger(self, coordinator):
        """Test total with empty ledger."""
        sensor = SimpleChoresTotalSensor(coordinator, "alice")
        coordinator.model.ledger = []
        
        assert sensor.native_value == 0
    
    def test_native_value_no_model(self, coordinator):
        """Test total when model is None."""
        sensor = SimpleChoresTotalSensor(coordinator, "alice")
        coordinator.model = None
        
        assert sensor.native_value == 0
    
    def test_available_with_model(self, coordinator):
        """Test availability when model exists."""
        sensor = SimpleChoresTotalSensor(coordinator, "alice")
        
        assert sensor.available is True
    
    def test_available_no_model(self, coordinator):
        """Test availability when model is None."""
        sensor = SimpleChoresTotalSensor(coordinator, "alice")
        coordinator.model = None
        
        assert sensor.available is False


class TestSimpleChoresPendingApprovalsSensor:
    """Test pending approvals sensor functionality."""
    
    @pytest.fixture
    def approval_sensor(self, coordinator):
        return SimpleChoresPendingApprovalsSensor(coordinator)
    
    @pytest.fixture
    def coordinator_with_approvals(self, coordinator):
        """Coordinator with sample pending approvals."""
        coordinator.model.pending_approvals = {
            "approval1": PendingApproval(
                id="approval1",
                todo_uid="uid1", 
                kid_id="alice",
                title="Clean room",
                points=5,
                completed_ts=datetime.now().timestamp(),
                status="pending_approval"
            ),
            "approval2": PendingApproval(
                id="approval2",
                todo_uid="uid2",
                kid_id="bob", 
                title="Do homework",
                points=3,
                completed_ts=datetime.now().timestamp(),
                status="pending_approval"
            ),
            "approval3": PendingApproval(
                id="approval3",
                todo_uid="uid3",
                kid_id="alice",
                title="Brush teeth", 
                points=2,
                completed_ts=datetime.now().timestamp(),
                status="rejected"  # Should not count in pending
            )
        }
        
        # Mock get_pending_approvals to return only pending ones
        coordinator.get_pending_approvals = Mock(return_value=[
            coordinator.model.pending_approvals["approval1"],
            coordinator.model.pending_approvals["approval2"]
        ])
        
        return coordinator
    
    def test_sensor_properties(self, approval_sensor):
        """Test basic sensor properties."""
        assert approval_sensor._attr_unique_id == "simplechores_pending_approvals"
        assert approval_sensor._attr_name == "Pending Chore Approvals"
        assert approval_sensor._attr_icon == "mdi:clipboard-check-multiple"
    
    def test_coordinator_registration(self, coordinator):
        """Test that sensor registers with coordinator."""
        sensor = SimpleChoresPendingApprovalsSensor(coordinator)
        
        assert hasattr(coordinator, "_approval_sensors")
        assert sensor in coordinator._approval_sensors
    
    def test_native_value_with_pending_approvals(self, coordinator_with_approvals):
        """Test native value with pending approvals."""
        sensor = SimpleChoresPendingApprovalsSensor(coordinator_with_approvals)
        
        # Should return count of pending approvals (2)
        assert sensor.native_value == 2
    
    def test_native_value_no_pending_approvals(self, coordinator):
        """Test native value with no pending approvals."""
        sensor = SimpleChoresPendingApprovalsSensor(coordinator)
        coordinator.get_pending_approvals = Mock(return_value=[])
        
        assert sensor.native_value == 0
    
    def test_native_value_no_model(self, coordinator):
        """Test native value when model is None."""
        sensor = SimpleChoresPendingApprovalsSensor(coordinator)
        coordinator.model = None
        
        assert sensor.native_value == 0
    
    def test_extra_state_attributes_with_approvals(self, coordinator_with_approvals):
        """Test extra state attributes with pending approvals."""
        sensor = SimpleChoresPendingApprovalsSensor(coordinator_with_approvals)
        
        attributes = sensor.extra_state_attributes
        
        assert "count" in attributes
        assert attributes["count"] == 2
        
        assert "approvals" in attributes
        approvals = attributes["approvals"]
        assert len(approvals) == 2
        
        # Check first approval
        approval1 = approvals[0]
        assert approval1["id"] == "approval1"
        assert approval1["kid"] == "alice"
        assert approval1["title"] == "Clean room"
        assert approval1["points"] == 5
        assert "completed_time" in approval1
        assert approval1["approve_service"] == "simplechores.approve_chore"
        assert approval1["approve_data"] == {"approval_id": "approval1"}
        assert approval1["reject_service"] == "simplechores.reject_chore"
        assert approval1["reject_data"] == {"approval_id": "approval1", "reason": "Not done properly"}
    
    def test_extra_state_attributes_no_approvals(self, coordinator):
        """Test extra state attributes with no approvals."""
        sensor = SimpleChoresPendingApprovalsSensor(coordinator)
        coordinator.get_pending_approvals = Mock(return_value=[])
        
        attributes = sensor.extra_state_attributes
        
        assert attributes["count"] == 0
        assert attributes["approvals"] == []
    
    def test_extra_state_attributes_no_model(self, coordinator):
        """Test extra state attributes when model is None."""
        sensor = SimpleChoresPendingApprovalsSensor(coordinator)
        coordinator.model = None
        
        attributes = sensor.extra_state_attributes
        
        assert attributes == {}
    
    def test_available_with_model(self, coordinator):
        """Test availability when model exists."""
        sensor = SimpleChoresPendingApprovalsSensor(coordinator)
        
        assert sensor.available is True
    
    def test_available_no_model(self, coordinator):
        """Test availability when model is None."""
        sensor = SimpleChoresPendingApprovalsSensor(coordinator)
        coordinator.model = None
        
        assert sensor.available is False


class TestSensorSetupEntry:
    """Test sensor platform setup."""
    
    @pytest.mark.asyncio
    async def test_async_setup_entry_basic(self, mock_hass, coordinator):
        """Test basic sensor setup."""
        config_entry = Mock()
        config_entry.data = {"kids": "alice,bob"}
        
        add_entities = Mock()
        
        await async_setup_entry(mock_hass, config_entry, add_entities)
        
        # Should create sensors for all kids plus pending approvals sensor
        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        
        # Should have: 2 kids × 2 sensors + 1 approval sensor = 5 total
        assert len(entities) == 5
        
        sensor_names = [entity._attr_name for entity in entities]
        
        # Week sensors
        assert "Alice Points (This Week)" in sensor_names
        assert "Bob Points (This Week)" in sensor_names
        
        # Total sensors  
        assert "Alice Points (Total Earned)" in sensor_names
        assert "Bob Points (Total Earned)" in sensor_names
        
        # Approval sensor
        assert "Pending Chore Approvals" in sensor_names
    
    @pytest.mark.asyncio
    async def test_async_setup_entry_single_kid(self, mock_hass, coordinator):
        """Test setup with single kid."""
        config_entry = Mock()
        config_entry.data = {"kids": "charlie"}
        
        add_entities = Mock()
        
        await async_setup_entry(mock_hass, config_entry, add_entities)
        
        entities = add_entities.call_args[0][0]
        
        # Should have: 1 kid × 2 sensors + 1 approval sensor = 3 total
        assert len(entities) == 3
        
        sensor_names = [entity._attr_name for entity in entities]
        assert "Charlie Points (This Week)" in sensor_names
        assert "Charlie Points (Total Earned)" in sensor_names
        assert "Pending Chore Approvals" in sensor_names
    
    @pytest.mark.asyncio
    async def test_async_setup_entry_default_kids(self, mock_hass, coordinator):
        """Test setup with default kids."""
        config_entry = Mock()
        config_entry.data = {}  # No kids specified
        
        add_entities = Mock()
        
        await async_setup_entry(mock_hass, config_entry, add_entities)
        
        entities = add_entities.call_args[0][0]
        
        # Should use default kids (alex,emma): 2 kids × 2 sensors + 1 approval = 5 total
        assert len(entities) == 5
        
        sensor_names = [entity._attr_name for entity in entities]
        assert "Alex Points (This Week)" in sensor_names  
        assert "Emma Points (This Week)" in sensor_names
        assert "Alex Points (Total Earned)" in sensor_names
        assert "Emma Points (Total Earned)" in sensor_names
        assert "Pending Chore Approvals" in sensor_names
    
    @pytest.mark.asyncio
    async def test_async_setup_entry_empty_kids(self, mock_hass, coordinator):
        """Test setup with empty kids list."""
        config_entry = Mock()
        config_entry.data = {"kids": "  ,  "}  # Empty after stripping
        
        add_entities = Mock()
        
        await async_setup_entry(mock_hass, config_entry, add_entities)
        
        entities = add_entities.call_args[0][0]
        
        # Should only have approval sensor (no kid sensors)
        assert len(entities) == 1
        assert entities[0]._attr_name == "Pending Chore Approvals"
    
    @pytest.mark.asyncio
    async def test_async_setup_entry_whitespace_handling(self, mock_hass, coordinator):
        """Test setup with whitespace in kids list."""
        config_entry = Mock()
        config_entry.data = {"kids": " alice , bob , charlie "}
        
        add_entities = Mock()
        
        await async_setup_entry(mock_hass, config_entry, add_entities)
        
        entities = add_entities.call_args[0][0]
        
        # Should handle whitespace and create sensors for 3 kids + approval
        assert len(entities) == 7  # 3 × 2 + 1
        
        sensor_names = [entity._attr_name for entity in entities]
        assert "Alice Points (This Week)" in sensor_names
        assert "Bob Points (This Week)" in sensor_names
        assert "Charlie Points (This Week)" in sensor_names


class TestSensorEntityTypes:
    """Test that sensors are of correct entity types."""
    
    def test_week_sensor_type(self, coordinator):
        """Test week sensor is a SensorEntity."""
        from homeassistant.components.sensor import SensorEntity
        
        sensor = SimpleChoresWeekSensor(coordinator, "alice")
        assert isinstance(sensor, SensorEntity)
    
    def test_total_sensor_type(self, coordinator):
        """Test total sensor is a SensorEntity."""
        from homeassistant.components.sensor import SensorEntity
        
        sensor = SimpleChoresTotalSensor(coordinator, "alice")
        assert isinstance(sensor, SensorEntity)
    
    def test_approval_sensor_type(self, coordinator):
        """Test approval sensor is a SensorEntity."""
        from homeassistant.components.sensor import SensorEntity
        
        sensor = SimpleChoresPendingApprovalsSensor(coordinator)
        assert isinstance(sensor, SensorEntity)


class TestSensorUniqueIds:
    """Test sensor unique ID generation."""
    
    def test_week_sensor_unique_ids(self, coordinator):
        """Test week sensor unique IDs are unique per kid."""
        sensor1 = SimpleChoresWeekSensor(coordinator, "alice")
        sensor2 = SimpleChoresWeekSensor(coordinator, "bob")
        
        assert sensor1._attr_unique_id != sensor2._attr_unique_id
        assert "alice" in sensor1._attr_unique_id
        assert "bob" in sensor2._attr_unique_id
    
    def test_total_sensor_unique_ids(self, coordinator):
        """Test total sensor unique IDs are unique per kid."""
        sensor1 = SimpleChoresTotalSensor(coordinator, "alice") 
        sensor2 = SimpleChoresTotalSensor(coordinator, "bob")
        
        assert sensor1._attr_unique_id != sensor2._attr_unique_id
        assert "alice" in sensor1._attr_unique_id
        assert "bob" in sensor2._attr_unique_id
    
    def test_approval_sensor_unique_id(self, coordinator):
        """Test approval sensor has unique ID."""
        sensor = SimpleChoresPendingApprovalsSensor(coordinator)
        
        assert sensor._attr_unique_id == "simplechores_pending_approvals"
    
    def test_cross_sensor_unique_ids(self, coordinator):
        """Test different sensor types have different unique IDs."""
        week_sensor = SimpleChoresWeekSensor(coordinator, "alice")
        total_sensor = SimpleChoresTotalSensor(coordinator, "alice")
        approval_sensor = SimpleChoresPendingApprovalsSensor(coordinator)
        
        unique_ids = [
            week_sensor._attr_unique_id,
            total_sensor._attr_unique_id, 
            approval_sensor._attr_unique_id
        ]
        
        # All should be different
        assert len(set(unique_ids)) == 3