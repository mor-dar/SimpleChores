"""Comprehensive tests for service layer error handling and edge cases."""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceNotFound, HomeAssistantError
from homeassistant.components.todo import TodoItem, TodoItemStatus

from custom_components.simplechores import async_setup_entry, async_unload_entry
from custom_components.simplechores.coordinator import SimpleChoresCoordinator
from custom_components.simplechores.models import StorageModel, PendingChore, Reward


class TestServiceErrorHandling:
    """Test error handling in all service calls."""
    
    @pytest.mark.asyncio
    async def test_add_points_service_coordinator_error(self, mock_hass, coordinator):
        """Test add_points service when coordinator fails."""
        # Setup entry
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"kids": "alice,bob"}
        mock_hass.data = {"simplechores": {entry.entry_id: coordinator}}
        
        await async_setup_entry(mock_hass, entry)
        
        # Mock coordinator to raise exception
        coordinator.ensure_kid = AsyncMock(side_effect=Exception("Database error"))
        
        # Get the registered service
        service_call = ServiceCall(
            hass=mock_hass,
            domain="simplechores",
            service="add_points",
            data={"kid": "alice", "amount": 10, "reason": "test"}
        )
        
        # Find and call the service
        add_points_handler = None
        for call in mock_hass.services.async_register.call_args_list:
            if call[0][1] == "add_points":
                add_points_handler = call[0][2]
                break
        
        assert add_points_handler is not None
        
        with pytest.raises(Exception, match="Database error"):
            await add_points_handler(service_call)
    
    @pytest.mark.asyncio
    async def test_create_adhoc_service_todo_entity_missing(self, mock_hass, coordinator):
        """Test create_adhoc service when todo entity is missing."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"kids": "alice"}
        mock_hass.data = {"simplechores": {entry.entry_id: coordinator}}
        
        await async_setup_entry(mock_hass, entry)
        
        # Mock todo service to fail and no todo entities available
        mock_hass.services.async_call = AsyncMock(side_effect=ServiceNotFound("todo.add_item not found"))
        coordinator._todo_entities = {}  # No todo entities
        
        service_call = ServiceCall(
            hass=mock_hass,
            domain="simplechores", 
            service="create_adhoc_chore",
            data={"kid": "alice", "title": "Test chore", "points": 5}
        )
        
        # Find and call the service
        create_adhoc_handler = None
        for call in mock_hass.services.async_register.call_args_list:
            if call[0][1] == "create_adhoc_chore":
                create_adhoc_handler = call[0][2]
                break
        
        with patch('custom_components.simplechores._LOGGER') as mock_logger:
            await create_adhoc_handler(service_call)
            
            # Should log warnings about failed todo creation
            mock_logger.warning.assert_called()
    
    @pytest.mark.asyncio
    async def test_create_adhoc_service_direct_entity_error(self, mock_hass, coordinator):
        """Test create_adhoc service when direct entity method fails."""
        entry = Mock()
        entry.entry_id = "test_entry" 
        entry.data = {"kids": "alice"}
        mock_hass.data = {"simplechores": {entry.entry_id: coordinator}}
        
        await async_setup_entry(mock_hass, entry)
        
        # Mock todo service to fail
        mock_hass.services.async_call = AsyncMock(side_effect=ServiceNotFound("todo.add_item not found"))
        
        # Mock todo entity that also fails
        mock_todo_entity = Mock()
        mock_todo_entity.async_create_item = AsyncMock(side_effect=Exception("Entity error"))
        coordinator._todo_entities = {"alice": mock_todo_entity}
        
        service_call = ServiceCall(
            hass=mock_hass,
            domain="simplechores",
            service="create_adhoc_chore", 
            data={"kid": "alice", "title": "Test chore", "points": 5}
        )
        
        # Find and call the service
        create_adhoc_handler = None
        for call in mock_hass.services.async_register.call_args_list:
            if call[0][1] == "create_adhoc_chore":
                create_adhoc_handler = call[0][2]
                break
        
        with patch('custom_components.simplechores._LOGGER') as mock_logger:
            await create_adhoc_handler(service_call)
            
            # Should log warnings about both failures
            assert mock_logger.warning.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_complete_chore_service_fallback_path(self, mock_hass, coordinator):
        """Test complete_chore service fallback when chore_id not found."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"kids": "alice"}
        mock_hass.data = {"simplechores": {entry.entry_id: coordinator}}
        
        await async_setup_entry(mock_hass, entry)
        
        # Mock coordinator to return False for chore completion (not found)
        coordinator.complete_chore_by_uid = AsyncMock(return_value=False)
        coordinator.ensure_kid = AsyncMock()
        coordinator.add_points = AsyncMock()
        
        service_call = ServiceCall(
            hass=mock_hass,
            domain="simplechores",
            service="complete_chore",
            data={"todo_uid": "nonexistent", "kid": "alice", "points": 5, "reason": "Manual"}
        )
        
        # Find and call the service
        complete_chore_handler = None
        for call in mock_hass.services.async_register.call_args_list:
            if call[0][1] == "complete_chore":
                complete_chore_handler = call[0][2]
                break
        
        await complete_chore_handler(service_call)
        
        # Should fall back to manual point award
        coordinator.ensure_kid.assert_called_once_with("alice")
        coordinator.add_points.assert_called_once_with("alice", 5, "Manual", "earn")
    
    @pytest.mark.asyncio
    async def test_claim_reward_service_insufficient_points(self, mock_hass, coordinator):
        """Test claim_reward service when kid has insufficient points."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"kids": "alice"}
        mock_hass.data = {"simplechores": {entry.entry_id: coordinator}}
        
        await async_setup_entry(mock_hass, entry)
        
        # Mock coordinator methods
        coordinator.ensure_kid = AsyncMock()
        coordinator.get_reward = Mock(return_value=Reward(
            id="movie", title="Movie Night", cost=50, description="Family movie"
        ))
        coordinator.get_points = Mock(return_value=20)  # Less than reward cost
        coordinator.remove_points = AsyncMock()
        
        service_call = ServiceCall(
            hass=mock_hass,
            domain="simplechores",
            service="claim_reward",
            data={"kid": "alice", "reward_id": "movie"}
        )
        
        # Find and call the service
        claim_reward_handler = None
        for call in mock_hass.services.async_register.call_args_list:
            if call[0][1] == "claim_reward":
                claim_reward_handler = call[0][2]
                break
        
        await claim_reward_handler(service_call)
        
        # Should not remove points or call calendar service
        coordinator.remove_points.assert_not_called()
        mock_hass.services.async_call.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_claim_reward_service_nonexistent_reward(self, mock_hass, coordinator):
        """Test claim_reward service with nonexistent reward."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"kids": "alice"}
        mock_hass.data = {"simplechores": {entry.entry_id: coordinator}}
        
        await async_setup_entry(mock_hass, entry)
        
        # Mock coordinator methods
        coordinator.ensure_kid = AsyncMock()
        coordinator.get_reward = Mock(return_value=None)  # Reward not found
        coordinator.remove_points = AsyncMock()
        
        service_call = ServiceCall(
            hass=mock_hass,
            domain="simplechores",
            service="claim_reward",
            data={"kid": "alice", "reward_id": "nonexistent"}
        )
        
        # Find and call the service
        claim_reward_handler = None
        for call in mock_hass.services.async_register.call_args_list:
            if call[0][1] == "claim_reward":
                claim_reward_handler = call[0][2]
                break
        
        await claim_reward_handler(service_call)
        
        # Should not remove points
        coordinator.remove_points.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_claim_reward_calendar_service_error(self, mock_hass, coordinator):
        """Test claim_reward when calendar service fails."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"kids": "alice", "parents_calendar": "calendar.family"}
        mock_hass.data = {"simplechores": {entry.entry_id: coordinator}}
        
        await async_setup_entry(mock_hass, entry)
        
        # Mock coordinator methods
        coordinator.ensure_kid = AsyncMock()
        coordinator.get_reward = Mock(return_value=Reward(
            id="movie", title="Movie Night", cost=20, description="Family movie",
            create_calendar_event=True, calendar_duration_hours=2
        ))
        coordinator.get_points = Mock(return_value=30)  # Sufficient points
        coordinator.remove_points = AsyncMock()
        
        # Mock calendar service to fail
        mock_hass.services.async_call = AsyncMock(side_effect=ServiceNotFound("calendar.create_event not found"))
        
        service_call = ServiceCall(
            hass=mock_hass,
            domain="simplechores",
            service="claim_reward",
            data={"kid": "alice", "reward_id": "movie"}
        )
        
        # Find and call the service
        claim_reward_handler = None
        for call in mock_hass.services.async_register.call_args_list:
            if call[0][1] == "claim_reward":
                claim_reward_handler = call[0][2]
                break
        
        with patch('custom_components.simplechores._LOGGER') as mock_logger:
            await claim_reward_handler(service_call)
            
            # Should still remove points even if calendar fails
            coordinator.remove_points.assert_called_once()
            
            # Should log the calendar error
            mock_logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_log_parent_chore_calendar_error(self, mock_hass, coordinator):
        """Test log_parent_chore service when calendar fails."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"parents_calendar": "calendar.family"}
        mock_hass.data = {"simplechores": {entry.entry_id: coordinator}}
        
        await async_setup_entry(mock_hass, entry)
        
        # Mock calendar service to fail
        mock_hass.services.async_call = AsyncMock(side_effect=Exception("Calendar service error"))
        
        service_call = ServiceCall(
            hass=mock_hass,
            domain="simplechores",
            service="log_parent_chore",
            data={"title": "Grocery shopping", "description": "Weekly groceries"}
        )
        
        # Find and call the service
        log_parent_handler = None
        for call in mock_hass.services.async_register.call_args_list:
            if call[0][1] == "log_parent_chore":
                log_parent_handler = call[0][2]
                break
        
        with patch('custom_components.simplechores._LOGGER') as mock_logger:
            await log_parent_handler(service_call)
            
            # Should log the calendar error
            mock_logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_approve_chore_service_failure(self, mock_hass, coordinator):
        """Test approve_chore service when coordinator fails."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"kids": "alice"}
        mock_hass.data = {"simplechores": {entry.entry_id: coordinator}}
        
        await async_setup_entry(mock_hass, entry)
        
        # Mock coordinator to return False (approval failed)
        coordinator.approve_chore = AsyncMock(return_value=False)
        
        service_call = ServiceCall(
            hass=mock_hass,
            domain="simplechores",
            service="approve_chore",
            data={"approval_id": "test123"}
        )
        
        # Find and call the service
        approve_handler = None
        for call in mock_hass.services.async_register.call_args_list:
            if call[0][1] == "approve_chore":
                approve_handler = call[0][2]
                break
        
        with patch('custom_components.simplechores._LOGGER') as mock_logger:
            await approve_handler(service_call)
            
            # Should log warning about failed approval
            mock_logger.warning.assert_called_with(
                "SimpleChores: Failed to approve chore test123"
            )
    
    @pytest.mark.asyncio
    async def test_reject_chore_service_failure(self, mock_hass, coordinator):
        """Test reject_chore service when coordinator fails."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"kids": "alice"}
        mock_hass.data = {"simplechores": {entry.entry_id: coordinator}}
        
        await async_setup_entry(mock_hass, entry)
        
        # Mock coordinator to return False (rejection failed)
        coordinator.reject_chore = AsyncMock(return_value=False)
        
        service_call = ServiceCall(
            hass=mock_hass,
            domain="simplechores",
            service="reject_chore",
            data={"approval_id": "test123", "reason": "Not good enough"}
        )
        
        # Find and call the service
        reject_handler = None
        for call in mock_hass.services.async_register.call_args_list:
            if call[0][1] == "reject_chore":
                reject_handler = call[0][2]
                break
        
        with patch('custom_components.simplechores._LOGGER') as mock_logger:
            await reject_handler(service_call)
            
            # Should log warning about failed rejection
            mock_logger.warning.assert_called_with(
                "SimpleChores: Failed to reject chore test123"
            )


class TestServiceSetupAndTeardown:
    """Test service registration and unregistration."""
    
    @pytest.mark.asyncio
    async def test_service_registration_complete(self, mock_hass, coordinator):
        """Test that all services are registered properly."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"kids": "alice,bob"}
        mock_hass.data = {"simplechores": {entry.entry_id: coordinator}}
        
        await async_setup_entry(mock_hass, entry)
        
        # Check all expected services were registered
        registered_services = [call[0][1] for call in mock_hass.services.async_register.call_args_list]
        
        expected_services = [
            "add_points",
            "remove_points", 
            "create_adhoc_chore",
            "complete_chore",
            "claim_reward",
            "log_parent_chore",
            "create_recurring_chore",
            "approve_chore",
            "reject_chore",
            "generate_recurring_chores"
        ]
        
        for service in expected_services:
            assert service in registered_services
    
    @pytest.mark.asyncio
    async def test_service_unregistration(self, mock_hass, coordinator):
        """Test that services are unregistered on entry unload."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"kids": "alice"}
        mock_hass.data = {"simplechores": {entry.entry_id: coordinator}}
        
        # Setup first
        await async_setup_entry(mock_hass, entry)
        
        # Mock unregister method
        mock_hass.services.async_remove = Mock()
        
        # Now unload
        result = await async_unload_entry(mock_hass, entry)
        
        assert result is True
        
        # Check services were unregistered
        unregister_calls = [call[0] for call in mock_hass.services.async_remove.call_args_list]
        
        expected_services = [
            ("simplechores", "add_points"),
            ("simplechores", "remove_points"),
            ("simplechores", "create_adhoc_chore"),
            ("simplechores", "complete_chore"),
            ("simplechores", "claim_reward"),
            ("simplechores", "log_parent_chore"),
            ("simplechores", "create_recurring_chore"),
            ("simplechores", "approve_chore"),
            ("simplechores", "reject_chore"),
            ("simplechores", "generate_recurring_chores")
        ]
        
        for service_call in expected_services:
            assert service_call in unregister_calls


class TestCalendarIntegrationEdgeCases:
    """Test calendar integration error scenarios."""
    
    @pytest.mark.asyncio
    async def test_calendar_event_with_missing_calendar_entity(self, mock_hass, coordinator):
        """Test calendar event creation when calendar entity doesn't exist."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"kids": "alice", "parents_calendar": "calendar.nonexistent"}
        mock_hass.data = {"simplechores": {entry.entry_id: coordinator}}
        
        await async_setup_entry(mock_hass, entry)
        
        # Mock coordinator methods
        coordinator.ensure_kid = AsyncMock()
        coordinator.get_reward = Mock(return_value=Reward(
            id="park", title="Park Trip", cost=15, description="Fun outing",
            create_calendar_event=True, calendar_duration_hours=3
        ))
        coordinator.get_points = Mock(return_value=20)
        coordinator.remove_points = AsyncMock()
        
        # Mock calendar service to fail with entity not found
        mock_hass.services.async_call = AsyncMock(
            side_effect=HomeAssistantError("Entity calendar.nonexistent not found")
        )
        
        service_call = ServiceCall(
            hass=mock_hass,
            domain="simplechores",
            service="claim_reward",
            data={"kid": "alice", "reward_id": "park"}
        )
        
        # Find and call the service
        claim_reward_handler = None
        for call in mock_hass.services.async_register.call_args_list:
            if call[0][1] == "claim_reward":
                claim_reward_handler = call[0][2]
                break
        
        with patch('custom_components.simplechores._LOGGER') as mock_logger:
            await claim_reward_handler(service_call)
            
            # Should still deduct points
            coordinator.remove_points.assert_called_once()
            
            # Should log calendar error
            mock_logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_calendar_event_datetime_formatting(self, mock_hass, coordinator):
        """Test calendar event with proper datetime formatting."""
        entry = Mock()
        entry.entry_id = "test_entry"
        entry.data = {"kids": "alice", "parents_calendar": "calendar.family"}
        mock_hass.data = {"simplechores": {entry.entry_id: coordinator}}
        
        await async_setup_entry(mock_hass, entry)
        
        # Mock coordinator methods
        coordinator.ensure_kid = AsyncMock()
        coordinator.get_reward = Mock(return_value=Reward(
            id="ice_cream", title="Ice Cream Trip", cost=10, description="Sweet treat",
            create_calendar_event=True, calendar_duration_hours=1
        ))
        coordinator.get_points = Mock(return_value=15)
        coordinator.remove_points = AsyncMock()
        
        # Mock successful calendar service
        mock_hass.services.async_call = AsyncMock()
        
        service_call = ServiceCall(
            hass=mock_hass,
            domain="simplechores",
            service="claim_reward",
            data={"kid": "alice", "reward_id": "ice_cream"}
        )
        
        # Find and call the service
        claim_reward_handler = None
        for call in mock_hass.services.async_register.call_args_list:
            if call[0][1] == "claim_reward":
                claim_reward_handler = call[0][2]
                break
        
        await claim_reward_handler(service_call)
        
        # Verify calendar service was called with proper datetime format
        calendar_call = mock_hass.services.async_call.call_args
        assert calendar_call[0] == ("calendar", "create_event")
        
        event_data = calendar_call[1]
        assert "start_date_time" in event_data
        assert "end_date_time" in event_data
        
        # Verify datetime strings are ISO formatted
        start_time = event_data["start_date_time"]
        end_time = event_data["end_date_time"]
        
        # Should be valid ISO format (will raise ValueError if not)
        datetime.fromisoformat(start_time.replace('Z', '+00:00') if start_time.endswith('Z') else start_time)
        datetime.fromisoformat(end_time.replace('Z', '+00:00') if end_time.endswith('Z') else end_time)