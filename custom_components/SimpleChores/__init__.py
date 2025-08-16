"""The SimpleChores integration."""
from __future__ import annotations
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
import homeassistant.helpers.config_validation as cv
from .const import DOMAIN, PLATFORMS, SERVICE_ADD_POINTS, SERVICE_REMOVE_POINTS, SERVICE_CREATE_ADHOC, SERVICE_COMPLETE_CHORE, SERVICE_CLAIM_REWARD, SERVICE_LOG_PARENT_CHORE
from .coordinator import SimpleChoresCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = SimpleChoresCoordinator(hass)
    await coordinator.async_init()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ---- Services ----
    async def _add_points(call: ServiceCall):
        data = call.data
        await coordinator.ensure_kid(data["kid"])
        await coordinator.add_points(data["kid"], int(data["amount"]), data.get("reason","adjust"), "adjust")

    async def _remove_points(call: ServiceCall):
        data = call.data
        await coordinator.ensure_kid(data["kid"])
        await coordinator.remove_points(data["kid"], int(data["amount"]), data.get("reason","adjust"), "adjust")

    async def _create_adhoc(call):
        # Minimal stub: create a todo item via service if user enabled To-do
        # You can enrich this to directly interact with your own Todo platform.
        data = call.data
        title = data["title"]
        points = int(data["points"])
        kid = data["kid"]
        await coordinator.ensure_kid(kid)
        # Award on completion (handled by UI/automation) – here we just create item.
        hass.async_create_task(
            hass.services.async_call(
                "todo", "add_item",
                {"entity_id": f"todo.{kid}_chores", "item": {"summary": title, "due_datetime": data.get("due")}},
                blocking=False,
            )
        )

    async def _complete_chore(call):
        data = call.data
        # When a chore completes, award points
        kid = data["kid"]
        points = int(data.get("points", 0))
        reason = data.get("reason", "Chore complete")
        await coordinator.ensure_kid(kid)
        if points:
            await coordinator.add_points(kid, points, reason, "earn")

    async def _claim_reward(call):
        data = call.data
        kid = data["kid"]
        cost = int(data["cost"])
        title = data["title"]
        await coordinator.ensure_kid(kid)
        await coordinator.remove_points(kid, cost, f"Reward: {title}", "spend")
        # Optionally create calendar event using google.create_event/local calendar create_event.
        # See HA docs; ensure RW access for Google.  (Wire this via config options.)

    async def _log_parent_chore(call):
        data = call.data
        # Call either local_calendar.create_event or google.create_event
        # For demo, call generic calendar service if provided
        svc = data.get("service", "google.create_event")
        payload = data.get("data", {})
        await hass.services.async_call(*svc.split("."), payload, blocking=False)

    # Service schemas
    add_points_schema = vol.Schema({
        vol.Required("kid"): cv.string,
        vol.Required("amount"): cv.positive_int,
        vol.Optional("reason", default="Manual adjust"): cv.string,
    })
    
    hass.services.async_register(DOMAIN, SERVICE_ADD_POINTS, _add_points, schema=add_points_schema)
    hass.services.async_register(DOMAIN, SERVICE_REMOVE_POINTS, _remove_points, schema=add_points_schema)
    hass.services.async_register(DOMAIN, SERVICE_CREATE_ADHOC, _create_adhoc)
    hass.services.async_register(DOMAIN, SERVICE_COMPLETE_CHORE, _complete_chore)
    hass.services.async_register(DOMAIN, SERVICE_CLAIM_REWARD, _claim_reward)
    hass.services.async_register(DOMAIN, SERVICE_LOG_PARENT_CHORE, _log_parent_chore)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # Unregister services if this is the last instance
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_ADD_POINTS)
            hass.services.async_remove(DOMAIN, SERVICE_REMOVE_POINTS)
            hass.services.async_remove(DOMAIN, SERVICE_CREATE_ADHOC)
            hass.services.async_remove(DOMAIN, SERVICE_COMPLETE_CHORE)
            hass.services.async_remove(DOMAIN, SERVICE_CLAIM_REWARD)
            hass.services.async_remove(DOMAIN, SERVICE_LOG_PARENT_CHORE)
    return unload_ok
