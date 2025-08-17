"""Pytest configuration for SimpleChores tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import pytest
import pytest_asyncio

from custom_components.simplechores.const import DOMAIN


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title="SimpleChores",
        data={
            "kids": ["alice", "bob"],
            "parents_calendar": "calendar.parents",
        },
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )


@pytest_asyncio.fixture
async def mock_hass():
    """Return a mock Home Assistant instance."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {}
    hass.config_entries = Mock()
    hass.services = Mock()
    hass.states = Mock()
    hass.loop = Mock()

    # Mock async methods
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.services.async_register = Mock()
    hass.services.async_remove = Mock()
    hass.services.async_call = AsyncMock()

    return hass


@pytest.fixture
def mock_storage_data():
    """Return mock storage data."""
    return {
        "kids": {
            "alice": {"id": "alice", "name": "alice", "points": 50},
            "bob": {"id": "bob", "name": "bob", "points": 30},
        },
        "ledger": [
            {
                "ts": 1234567890.0,
                "kid_id": "alice",
                "delta": 10,
                "reason": "Cleaned room",
                "kind": "earn",
            }
        ],
        "rewards": {
            "movie": {
                "id": "movie",
                "title": "Movie Night",
                "cost": 20,
                "description": "Family movie night",
                "create_calendar_event": True,
                "calendar_duration_hours": 2,
            }
        },
        "pending_chores": {},
        "recurring_chores": {},
        "pending_approvals": {},
    }


@pytest.fixture
def coordinator(mock_hass):
    """Return a mock coordinator."""
    from unittest.mock import patch
    from custom_components.simplechores.coordinator import SimpleChoresCoordinator
    from custom_components.simplechores.models import StorageModel
    
    # Patch the Store to avoid real file operations
    with patch('custom_components.simplechores.coordinator.SimpleChoresStore') as mock_store_class:
        mock_store = AsyncMock()
        mock_store.async_save = AsyncMock()
        mock_store.async_load = AsyncMock(return_value=StorageModel())
        mock_store_class.return_value = mock_store
        
        coord = SimpleChoresCoordinator(mock_hass)
        coord.model = StorageModel()
        coord.store = mock_store
        
    return coord

