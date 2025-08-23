"""Integration tests for SimpleChores services and component setup."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
import pytest
import pytest_asyncio

from custom_components.simplechores import async_setup_entry, async_unload_entry
from custom_components.simplechores.const import (
    DOMAIN,
    SERVICE_ADD_POINTS,
    SERVICE_CLAIM_REWARD,
    SERVICE_COMPLETE_CHORE,
    SERVICE_CREATE_ADHOC,
    SERVICE_REMOVE_POINTS,
)
from custom_components.simplechores.coordinator import SimpleChoresCoordinator
from custom_components.simplechores.models import Reward, StorageModel


class TestSimpleChoresIntegration:
    """Test SimpleChores integration setup and services."""

    @pytest_asyncio.fixture
    async def mock_hass(self):
        """Return a mock Home Assistant instance."""
        hass = Mock(spec=HomeAssistant)
        hass.data = {}
        hass.config_entries = Mock()
        hass.services = Mock()
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.services.async_register = Mock()
        hass.services.async_remove = Mock()
        hass.services.async_call = AsyncMock()
        return hass

    @pytest.fixture
    def mock_config_entry(self):
        """Return a mock config entry."""
        entry = Mock(spec=ConfigEntry)
        entry.entry_id = "test_entry"
        entry.data = {
            "kids": "alice,bob",
            "parents_calendar": "calendar.parents"
        }
        return entry

    @pytest.fixture
    def mock_coordinator(self):
        """Return a mock coordinator."""
        coordinator = Mock(spec=SimpleChoresCoordinator)
        coordinator.async_init = AsyncMock()
        coordinator.model = StorageModel()
        coordinator.ensure_kid = AsyncMock()
        coordinator.add_points = AsyncMock()
        coordinator.remove_points = AsyncMock()
        coordinator.get_points = Mock(return_value=50)
        coordinator.create_pending_chore = AsyncMock(return_value="test-uuid")
        coordinator.complete_chore_by_uid = AsyncMock(return_value=True)
        coordinator.get_reward = Mock(return_value=Reward(
            id="movie", title="Movie Night", cost=20,
            description="Family movie", create_calendar_event=True, calendar_duration_hours=2
        ))
        return coordinator

    @pytest.mark.asyncio
    async def test_async_setup_entry(self, mock_hass, mock_config_entry):
        """Test setting up the integration."""
        with patch('custom_components.simplechores.SimpleChoresCoordinator') as mock_coordinator_class:
            mock_coordinator = Mock()
            mock_coordinator.async_init = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            result = await async_setup_entry(mock_hass, mock_config_entry)

            assert result is True
            # Should store coordinator in hass data
            assert DOMAIN in mock_hass.data
            assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]

            # Should forward setup to platforms
            mock_hass.config_entries.async_forward_entry_setups.assert_called_once()

            # Should register services
            assert mock_hass.services.async_register.call_count >= 5  # At least 5 services

    @pytest.mark.asyncio
    async def test_async_unload_entry(self, mock_hass, mock_config_entry):
        """Test unloading the integration."""
        # Set up hass data
        mock_hass.data = {DOMAIN: {mock_config_entry.entry_id: Mock()}}

        result = await async_unload_entry(mock_hass, mock_config_entry)

        assert result is True
        mock_hass.config_entries.async_unload_platforms.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_points_service(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test add_points service."""
        # Set up the integration first
        mock_hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

        with patch('custom_components.simplechores.SimpleChoresCoordinator', return_value=mock_coordinator):
            await async_setup_entry(mock_hass, mock_config_entry)

            # Get the registered service handler
            service_calls = mock_hass.services.async_register.call_args_list
            add_points_call = None
            for call in service_calls:
                if call[0][1] == SERVICE_ADD_POINTS:
                    add_points_call = call
                    break

            assert add_points_call is not None
            service_handler = add_points_call[0][2]  # The handler function

            # Test the service call
            call_data = ServiceCall(
                hass=mock_hass,
                domain=DOMAIN,
                service=SERVICE_ADD_POINTS,
                data={"kid": "alice", "amount": 25, "reason": "Good behavior"}
            )

            await service_handler(call_data)

            mock_coordinator.ensure_kid.assert_called_with("alice")
            mock_coordinator.add_points.assert_called_with("alice", 25, "Good behavior", "adjust")

    @pytest.mark.asyncio
    async def test_remove_points_service(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test remove_points service."""
        mock_hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

        with patch('custom_components.simplechores.SimpleChoresCoordinator', return_value=mock_coordinator):
            await async_setup_entry(mock_hass, mock_config_entry)

            # Get the registered service handler
            service_calls = mock_hass.services.async_register.call_args_list
            remove_points_call = None
            for call in service_calls:
                if call[0][1] == SERVICE_REMOVE_POINTS:
                    remove_points_call = call
                    break

            service_handler = remove_points_call[0][2]

            call_data = ServiceCall(
                hass=mock_hass,
                domain=DOMAIN,
                service=SERVICE_REMOVE_POINTS,
                data={"kid": "bob", "amount": 15, "reason": "Broke rule"}
            )

            await service_handler(call_data)

            mock_coordinator.ensure_kid.assert_called_with("bob")
            mock_coordinator.remove_points.assert_called_with("bob", 15, "Broke rule", "adjust")

    @pytest.mark.asyncio
    async def test_create_adhoc_chore_service(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test create_adhoc_chore service."""
        mock_hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

        with patch('custom_components.simplechores.SimpleChoresCoordinator', return_value=mock_coordinator):
            await async_setup_entry(mock_hass, mock_config_entry)

            # Get the service handler
            service_calls = mock_hass.services.async_register.call_args_list
            create_adhoc_call = None
            for call in service_calls:
                if call[0][1] == SERVICE_CREATE_ADHOC:
                    create_adhoc_call = call
                    break

            service_handler = create_adhoc_call[0][2]

            call_data = ServiceCall(
                hass=mock_hass,
                domain=DOMAIN,
                service=SERVICE_CREATE_ADHOC,
                data={"kid": "alice", "title": "Clean garage", "points": 20}
            )

            await service_handler(call_data)

            mock_coordinator.ensure_kid.assert_called_with("alice")
            mock_coordinator.create_pending_chore.assert_called_with("alice", "Clean garage", 20, None)
            # Should also try to call todo service
            mock_hass.services.async_call.assert_called()

    @pytest.mark.asyncio
    async def test_complete_chore_service(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test complete_chore service."""
        mock_hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

        with patch('custom_components.simplechores.SimpleChoresCoordinator', return_value=mock_coordinator):
            await async_setup_entry(mock_hass, mock_config_entry)

            # Get the service handler
            service_calls = mock_hass.services.async_register.call_args_list
            complete_chore_call = None
            for call in service_calls:
                if call[0][1] == SERVICE_COMPLETE_CHORE:
                    complete_chore_call = call
                    break

            service_handler = complete_chore_call[0][2]

            call_data = ServiceCall(
                hass=mock_hass,
                domain=DOMAIN,
                service=SERVICE_COMPLETE_CHORE,
                data={"todo_uid": "test-uuid"}
            )

            await service_handler(call_data)

            mock_coordinator.complete_chore_by_uid.assert_called_with("test-uuid")

    @pytest.mark.asyncio
    async def test_claim_reward_service(self, mock_hass, mock_config_entry, mock_coordinator):
        """Test claim_reward service with calendar event creation."""
        mock_hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

        with patch('custom_components.simplechores.SimpleChoresCoordinator', return_value=mock_coordinator):
            await async_setup_entry(mock_hass, mock_config_entry)

            # Get the service handler
            service_calls = mock_hass.services.async_register.call_args_list
            claim_reward_call = None
            for call in service_calls:
                if call[0][1] == SERVICE_CLAIM_REWARD:
                    claim_reward_call = call
                    break

            service_handler = claim_reward_call[0][2]

            call_data = ServiceCall(
                hass=mock_hass,
                domain=DOMAIN,
                service=SERVICE_CLAIM_REWARD,
                data={"kid": "alice", "reward_id": "movie"}
            )

            await service_handler(call_data)

            mock_coordinator.ensure_kid.assert_called_with("alice")
            mock_coordinator.get_reward.assert_called_with("movie")
            mock_coordinator.remove_points.assert_called_with("alice", 20, "Reward: Movie Night", "spend")
            # Should create calendar event
            calendar_call = None
            for call in mock_hass.services.async_call.call_args_list:
                if call[0][0] == "calendar" and call[0][1] == "create_event":
                    calendar_call = call
                    break
            assert calendar_call is not None

    @pytest.mark.asyncio
    async def test_service_unregistration_on_unload(self, mock_hass, mock_config_entry):
        """Test services are unregistered when integration is unloaded."""
        # Set up with one entry
        mock_hass.data = {DOMAIN: {mock_config_entry.entry_id: Mock()}}

        # Unload should remove services when no entries left
        await async_unload_entry(mock_hass, mock_config_entry)

        # Should remove all services
        expected_services = [
            SERVICE_ADD_POINTS, SERVICE_REMOVE_POINTS, SERVICE_CREATE_ADHOC,
            SERVICE_COMPLETE_CHORE, SERVICE_CLAIM_REWARD
        ]

        remove_calls = mock_hass.services.async_remove.call_args_list
        removed_services = [call[0][1] for call in remove_calls if call[0][0] == DOMAIN]

        for service in expected_services:
            assert service in removed_services

