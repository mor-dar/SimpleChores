"""Integration tests for SimpleChores config flow."""
from __future__ import annotations

from unittest.mock import Mock

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from custom_components.simplechores import config_flow
from custom_components.simplechores.const import CONF_KIDS, CONF_PARENTS_CALENDAR, CONF_USE_TODO


class TestSimpleChoresConfigFlow:
    """Test SimpleChores config flow."""

    @pytest.fixture
    def mock_hass(self):
        """Return a mock Home Assistant instance."""
        from unittest.mock import Mock
        hass = Mock(spec=HomeAssistant)
        hass.config_entries = Mock()
        return hass

    @pytest.mark.asyncio
    async def test_user_form_display(self):
        """Test the user form is displayed correctly."""
        flow = config_flow.SimpleChoresConfigFlow()
        flow.hass = Mock()
        flow._async_current_entries = Mock(return_value=[])

        result = await flow.async_step_user()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        # Check schema has required fields
        schema = result["data_schema"]
        assert CONF_KIDS in schema.schema
        assert CONF_USE_TODO in schema.schema
        assert CONF_PARENTS_CALENDAR in schema.schema

    @pytest.mark.asyncio
    async def test_user_form_submission(self):
        """Test successful form submission."""
        flow = config_flow.SimpleChoresConfigFlow()
        flow.hass = Mock()
        flow._async_current_entries = Mock(return_value=[])

        user_input = {
            CONF_KIDS: "alice,bob,charlie",
            CONF_USE_TODO: True,
            CONF_PARENTS_CALENDAR: "calendar.family"
        }

        result = await flow.async_step_user(user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "SimpleChores"
        assert result["data"] == user_input

    @pytest.mark.asyncio
    async def test_single_instance_restriction(self):
        """Test that only one instance is allowed."""
        flow = config_flow.SimpleChoresConfigFlow()
        flow.hass = Mock()

        # Mock existing entry
        existing_entry = Mock()
        flow._async_current_entries = Mock(return_value=[existing_entry])

        result = await flow.async_step_user()

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "single_instance_allowed"

    def test_options_flow_creation(self):
        """Test options flow is created correctly."""
        mock_entry = Mock()
        options_flow = config_flow.SimpleChoresConfigFlow.async_get_options_flow(mock_entry)

        assert isinstance(options_flow, config_flow.SimpleChoresOptionsFlow)
        assert options_flow.entry == mock_entry


class TestSimpleChoresOptionsFlow:
    """Test SimpleChores options flow."""

    @pytest.fixture
    def mock_entry(self):
        """Return a mock config entry."""
        from unittest.mock import Mock
        entry = Mock()
        entry.options = {
            CONF_USE_TODO: False,
            CONF_PARENTS_CALENDAR: "calendar.test"
        }
        return entry

    @pytest.mark.asyncio
    async def test_options_form_display(self, mock_entry):
        """Test the options form is displayed correctly."""
        flow = config_flow.SimpleChoresOptionsFlow(mock_entry)

        result = await flow.async_step_init()

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

        # Check schema has optional fields with defaults from entry
        schema = result["data_schema"]
        assert CONF_USE_TODO in schema.schema
        assert CONF_PARENTS_CALENDAR in schema.schema

    @pytest.mark.asyncio
    async def test_options_form_submission(self, mock_entry):
        """Test successful options form submission."""
        flow = config_flow.SimpleChoresOptionsFlow(mock_entry)

        user_input = {
            CONF_USE_TODO: True,
            CONF_PARENTS_CALENDAR: "calendar.updated"
        }

        result = await flow.async_step_init(user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == ""
        assert result["data"] == user_input

    @pytest.mark.asyncio
    async def test_options_form_defaults(self):
        """Test options form uses correct defaults."""
        from unittest.mock import Mock
        entry = Mock()
        entry.options = {}  # Empty options

        flow = config_flow.SimpleChoresOptionsFlow(entry)
        result = await flow.async_step_init()

        assert result["type"] == FlowResultType.FORM
        # Should use default values when no options exist

