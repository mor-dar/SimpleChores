"""Config flow for SimpleChores integration."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol

from .const import CONF_KIDS, CONF_PARENTS_CALENDAR, CONF_USE_TODO, DOMAIN


class SimpleChoresConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        # Check for existing instance
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="SimpleChores", data=user_input)

        data_schema = vol.Schema({
            vol.Required(CONF_KIDS, default="alex,emma"): str,
            vol.Optional(CONF_USE_TODO, default=True): bool,
            vol.Optional(CONF_PARENTS_CALENDAR, default="calendar.parents"): str,
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SimpleChoresOptionsFlow(config_entry)

class SimpleChoresOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema({
            vol.Optional(CONF_USE_TODO, default=self.entry.options.get(CONF_USE_TODO, True)): bool,
            vol.Optional(CONF_PARENTS_CALENDAR, default=self.entry.options.get(CONF_PARENTS_CALENDAR, "calendar.parents")): str,
        })
        return self.async_show_form(step_id="init", data_schema=data_schema)
