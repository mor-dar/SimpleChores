"""The SimpleChores integration."""
from __future__ import annotations
import voluptuous as vol
from datetime import datetime, timedelta
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

    async def _create_adhoc(call: ServiceCall):
        data = call.data
        title = data["title"]
        points = int(data["points"])
        kid = data["kid"]
        await coordinator.ensure_kid(kid)
        
        # Create pending chore to track points
        todo_uid = await coordinator.create_pending_chore(kid, title, points)
        
        # Create todo item with points in summary for easy identification
        title_with_points = f"{title} (+{points})"
        await hass.services.async_call(
            "todo", "add_item",
            {
                "entity_id": f"todo.{kid}_chores", 
                "item": {
                    "summary": title_with_points,
                    "due_datetime": data.get("due"),
                    "uid": todo_uid
                }
            },
            blocking=False,
        )

    async def _complete_chore(call: ServiceCall):
        data = call.data
        todo_uid = data.get("todo_uid")
        
        if todo_uid:
            # Complete chore by UID (preferred method)
            success = await coordinator.complete_chore_by_uid(todo_uid)
            if not success:
                # Fallback to manual point award
                kid = data["kid"]
                points = int(data.get("points", 0))
                reason = data.get("reason", "Chore complete")
                await coordinator.ensure_kid(kid)
                if points:
                    await coordinator.add_points(kid, points, reason, "earn")
        else:
            # Manual point award (legacy)
            kid = data["kid"]
            points = int(data.get("points", 0))
            reason = data.get("reason", "Chore complete")
            await coordinator.ensure_kid(kid)
            if points:
                await coordinator.add_points(kid, points, reason, "earn")

    async def _claim_reward(call: ServiceCall):
        data = call.data
        kid = data["kid"]
        reward_id = data.get("reward_id")
        
        await coordinator.ensure_kid(kid)
        
        if reward_id:
            # Use reward system
            reward = coordinator.get_reward(reward_id)
            if not reward:
                return
            
            kid_points = coordinator.get_points(kid)
            if kid_points < reward.cost:
                return  # Not enough points
                
            await coordinator.remove_points(kid, reward.cost, f"Reward: {reward.title}", "spend")
            
            # Create calendar event if enabled
            if reward.create_calendar_event:
                parents_calendar = entry.data.get("parents_calendar", "calendar.parents")
                from datetime import datetime, timedelta
                start_time = datetime.now()
                end_time = start_time + timedelta(hours=reward.calendar_duration_hours)
                
                await hass.services.async_call(
                    "calendar", "create_event",
                    {
                        "entity_id": parents_calendar,
                        "summary": f"Family reward — {reward.title} ({kid.capitalize()})",
                        "description": reward.description,
                        "start_date_time": start_time.isoformat(),
                        "end_date_time": end_time.isoformat(),
                    },
                    blocking=False
                )
        else:
            # Legacy direct cost/title method
            cost = int(data.get("cost", 0))
            title = data.get("title", "Reward")
            await coordinator.remove_points(kid, cost, f"Reward: {title}", "spend")

    async def _log_parent_chore(call: ServiceCall):
        data = call.data
        parents_calendar = entry.data.get("parents_calendar", "calendar.parents")
        
        await hass.services.async_call(
            "calendar", "create_event",
            {
                "entity_id": parents_calendar,
                "summary": data["title"],
                "description": data.get("description", ""),
                "start_date_time": data.get("start", datetime.now().isoformat()),
                "end_date_time": data.get("end", (datetime.now() + timedelta(hours=1)).isoformat()),
                "all_day": data.get("all_day", False),
            },
            blocking=False
        )

    # Service schemas
    add_points_schema = vol.Schema({
        vol.Required("kid"): cv.string,
        vol.Required("amount"): cv.positive_int,
        vol.Optional("reason", default="Manual adjust"): cv.string,
    })
    
    create_adhoc_schema = vol.Schema({
        vol.Required("kid"): cv.string,
        vol.Required("title"): cv.string,
        vol.Required("points"): cv.positive_int,
        vol.Optional("due"): cv.datetime,
    })
    
    complete_chore_schema = vol.Schema({
        vol.Optional("todo_uid"): cv.string,
        vol.Optional("kid"): cv.string,
        vol.Optional("points"): cv.positive_int,
        vol.Optional("reason"): cv.string,
    })
    
    claim_reward_schema = vol.Schema({
        vol.Required("kid"): cv.string,
        vol.Optional("reward_id"): cv.string,
        vol.Optional("cost"): cv.positive_int,
        vol.Optional("title"): cv.string,
    })
    
    log_parent_chore_schema = vol.Schema({
        vol.Required("title"): cv.string,
        vol.Optional("description"): cv.string,
        vol.Optional("start"): cv.string,
        vol.Optional("end"): cv.string,
        vol.Optional("all_day", default=False): cv.boolean,
    })
    
    hass.services.async_register(DOMAIN, SERVICE_ADD_POINTS, _add_points, schema=add_points_schema)
    hass.services.async_register(DOMAIN, SERVICE_REMOVE_POINTS, _remove_points, schema=add_points_schema)
    hass.services.async_register(DOMAIN, SERVICE_CREATE_ADHOC, _create_adhoc, schema=create_adhoc_schema)
    hass.services.async_register(DOMAIN, SERVICE_COMPLETE_CHORE, _complete_chore, schema=complete_chore_schema)
    hass.services.async_register(DOMAIN, SERVICE_CLAIM_REWARD, _claim_reward, schema=claim_reward_schema)
    hass.services.async_register(DOMAIN, SERVICE_LOG_PARENT_CHORE, _log_parent_chore, schema=log_parent_chore_schema)

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
