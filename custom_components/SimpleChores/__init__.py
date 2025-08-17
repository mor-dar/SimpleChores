"""The SimpleChores integration."""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .const import (
    DOMAIN,
    PLATFORMS,
    SERVICE_ADD_POINTS,
    SERVICE_APPROVE_CHORE,
    SERVICE_CLAIM_REWARD,
    SERVICE_COMPLETE_CHORE,
    SERVICE_CREATE_ADHOC,
    SERVICE_CREATE_RECURRING,
    SERVICE_GENERATE_RECURRING,
    SERVICE_LOG_PARENT_CHORE,
    SERVICE_REJECT_CHORE,
    SERVICE_REMOVE_POINTS,
)
from .coordinator import SimpleChoresCoordinator


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SimpleChores component."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = SimpleChoresCoordinator(hass)
    await coordinator.async_init()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ---- Services ----
    async def _add_points(call: ServiceCall):
        import logging
        _LOGGER = logging.getLogger(__name__)

        try:
            _LOGGER.debug("SimpleChores: add_points service called")
            data = call.data
            _LOGGER.debug(f"SimpleChores: service data = {data}")

            kid = data["kid"]
            amount = int(data["amount"])
            reason = data.get("reason", "adjust")

            _LOGGER.debug(f"SimpleChores: Adding {amount} points to {kid}, reason: {reason}")
            _LOGGER.debug(f"SimpleChores: coordinator = {coordinator}")
            _LOGGER.debug(f"SimpleChores: coordinator.model = {coordinator.model}")

            await coordinator.ensure_kid(kid)
            _LOGGER.debug("SimpleChores: ensure_kid completed")

            old_points = coordinator.get_points(kid)
            _LOGGER.debug(f"SimpleChores: old_points = {old_points}")

            await coordinator.add_points(kid, amount, reason, "adjust")
            _LOGGER.debug("SimpleChores: add_points completed")

            new_points = coordinator.get_points(kid)
            _LOGGER.debug(f"SimpleChores: new_points = {new_points}")

        except Exception as e:
            _LOGGER.error(f"SimpleChores: add_points service error: {e}")
            _LOGGER.error(f"SimpleChores: error type: {type(e)}")
            import traceback
            _LOGGER.error(f"SimpleChores: traceback: {traceback.format_exc()}")
            raise

    async def _remove_points(call: ServiceCall):
        data = call.data
        await coordinator.ensure_kid(data["kid"])
        await coordinator.remove_points(data["kid"], int(data["amount"]), data.get("reason","adjust"), "adjust")

    async def _create_adhoc(call: ServiceCall):
        import logging
        _LOGGER = logging.getLogger(__name__)

        data = call.data
        title = data["title"]
        points = int(data["points"])
        kid = data["kid"]
        await coordinator.ensure_kid(kid)

        # Create pending chore to track points
        todo_uid = await coordinator.create_pending_chore(kid, title, points)
        _LOGGER.debug(f"SimpleChores: Created pending chore {todo_uid} for {kid}")

        # Try to create todo item if todo entities are available
        title_with_points = f"{title} (+{points})"
        entity_id = f"todo.{kid}_chores"

        # Try to create todo item
        try:
            _LOGGER.debug(f"SimpleChores: Attempting to create todo item '{title_with_points}' for entity {entity_id}")

            # Method 1: Try the standard todo service call
            try:
                await hass.services.async_call(
                    "todo", "add_item",
                    {
                        "entity_id": entity_id,
                        "item": title_with_points
                    },
                    blocking=False,
                )
                _LOGGER.info("SimpleChores: Successfully created todo item via service call")
            except Exception as service_error:
                _LOGGER.warning(f"SimpleChores: todo.add_item service failed: {service_error}")

                # Method 2: Try to find and call the entity directly via coordinator
                if hasattr(coordinator, '_todo_entities') and kid in coordinator._todo_entities:
                    todo_entity = coordinator._todo_entities[kid]
                    _LOGGER.debug(f"SimpleChores: Found todo entity for {kid}, calling direct method")
                    from homeassistant.components.todo import TodoItem, TodoItemStatus
                    new_item = TodoItem(
                        summary=title_with_points,
                        uid=todo_uid,
                        status=TodoItemStatus.NEEDS_ACTION
                    )
                    await todo_entity.async_create_item(new_item)
                    _LOGGER.info("SimpleChores: Created todo item via direct entity method")
                else:
                    _LOGGER.warning(f"SimpleChores: No todo entity found for kid {kid}")

        except Exception as e:
            _LOGGER.warning(f"SimpleChores: Failed to create todo item: {e}")
            # Chore is still tracked via pending_chores, so this is not critical

    async def _complete_chore(call: ServiceCall):
        data = call.data
        todo_uid = data.get("todo_uid") or data.get("chore_id")  # Support both names

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
                start_time = datetime.now()
                end_time = start_time + timedelta(hours=reward.calendar_duration_hours)

                try:
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
                except Exception:
                    # Calendar service failed, but still deduct points
                    pass
        else:
            # Legacy direct cost/title method
            cost = int(data.get("cost", 0))
            title = data.get("title", "Reward")
            await coordinator.remove_points(kid, cost, f"Reward: {title}", "spend")

    async def _log_parent_chore(call: ServiceCall):
        data = call.data
        parents_calendar = entry.data.get("parents_calendar", "calendar.parents")

        try:
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
        except Exception:
            # Calendar service failed - log error but don't fail
            pass

    async def _create_recurring_chore(call: ServiceCall):
        data = call.data
        kid = data["kid"]
        title = data["title"]
        points = int(data["points"])
        schedule_type = data["schedule_type"]
        day_of_week = data.get("day_of_week")

        await coordinator.ensure_kid(kid)
        chore_id = await coordinator.create_recurring_chore(kid, title, points, schedule_type, day_of_week)

        import logging
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.info(f"SimpleChores: Created recurring chore {chore_id}: {title} for {kid}")

    async def _approve_chore(call: ServiceCall):
        data = call.data
        approval_id = data["approval_id"]

        success = await coordinator.approve_chore(approval_id)

        import logging
        _LOGGER = logging.getLogger(__name__)
        if success:
            _LOGGER.info(f"SimpleChores: Approved chore {approval_id}")
        else:
            _LOGGER.warning(f"SimpleChores: Failed to approve chore {approval_id}")

    async def _reject_chore(call: ServiceCall):
        data = call.data
        approval_id = data["approval_id"]
        reason = data.get("reason", "Did not meet standards")

        success = await coordinator.reject_chore(approval_id, reason)

        import logging
        _LOGGER = logging.getLogger(__name__)
        if success:
            _LOGGER.info(f"SimpleChores: Rejected chore {approval_id}: {reason}")
        else:
            _LOGGER.warning(f"SimpleChores: Failed to reject chore {approval_id}")

    async def _generate_recurring_chores(call: ServiceCall):
        """Generate daily and/or weekly recurring chores"""
        data = call.data
        schedule_type = data.get("schedule_type", "daily")

        if schedule_type == "daily":
            await coordinator.generate_daily_chores()
        elif schedule_type == "weekly":
            from datetime import datetime
            current_day = datetime.now().weekday()  # 0=Monday, 6=Sunday
            target_day = data.get("day_of_week", current_day)
            await coordinator.generate_weekly_chores(target_day)

        import logging
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.info(f"SimpleChores: Generated {schedule_type} recurring chores")

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
        vol.Optional("chore_id"): cv.string,  # Alias for todo_uid
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

    create_recurring_schema = vol.Schema({
        vol.Required("kid"): cv.string,
        vol.Required("title"): cv.string,
        vol.Required("points"): cv.positive_int,
        vol.Required("schedule_type"): vol.In(["daily", "weekly"]),
        vol.Optional("day_of_week"): vol.In([0, 1, 2, 3, 4, 5, 6]),  # 0=Monday, 6=Sunday
    })

    approve_chore_schema = vol.Schema({
        vol.Required("approval_id"): cv.string,
    })

    reject_chore_schema = vol.Schema({
        vol.Required("approval_id"): cv.string,
        vol.Optional("reason", default="Did not meet standards"): cv.string,
    })

    generate_recurring_schema = vol.Schema({
        vol.Optional("schedule_type", default="daily"): vol.In(["daily", "weekly"]),
        vol.Optional("day_of_week"): vol.In([0, 1, 2, 3, 4, 5, 6]),
    })

    hass.services.async_register(DOMAIN, SERVICE_ADD_POINTS, _add_points, schema=add_points_schema)
    hass.services.async_register(DOMAIN, SERVICE_REMOVE_POINTS, _remove_points, schema=add_points_schema)
    hass.services.async_register(DOMAIN, SERVICE_CREATE_ADHOC, _create_adhoc, schema=create_adhoc_schema)
    hass.services.async_register(DOMAIN, SERVICE_COMPLETE_CHORE, _complete_chore, schema=complete_chore_schema)
    hass.services.async_register(DOMAIN, SERVICE_CLAIM_REWARD, _claim_reward, schema=claim_reward_schema)
    hass.services.async_register(DOMAIN, SERVICE_LOG_PARENT_CHORE, _log_parent_chore, schema=log_parent_chore_schema)
    hass.services.async_register(DOMAIN, SERVICE_CREATE_RECURRING, _create_recurring_chore, schema=create_recurring_schema)
    hass.services.async_register(DOMAIN, SERVICE_APPROVE_CHORE, _approve_chore, schema=approve_chore_schema)
    hass.services.async_register(DOMAIN, SERVICE_REJECT_CHORE, _reject_chore, schema=reject_chore_schema)
    hass.services.async_register(DOMAIN, SERVICE_GENERATE_RECURRING, _generate_recurring_chores, schema=generate_recurring_schema)

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
            hass.services.async_remove(DOMAIN, SERVICE_CREATE_RECURRING)
            hass.services.async_remove(DOMAIN, SERVICE_APPROVE_CHORE)
            hass.services.async_remove(DOMAIN, SERVICE_REJECT_CHORE)
            hass.services.async_remove(DOMAIN, SERVICE_GENERATE_RECURRING)
    return unload_ok
