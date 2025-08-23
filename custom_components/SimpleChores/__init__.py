"""The SimpleChores integration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError, ServiceNotFound
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

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
    """Set up SimpleChores from a config entry."""
    try:
        coordinator = SimpleChoresCoordinator(hass)
        await coordinator.async_init()
    except (asyncio.TimeoutError, ConnectionError, OSError) as ex:
        raise ConfigEntryNotReady(f"Failed to initialize SimpleChores coordinator: {ex}") from ex
    except Exception as ex:
        _LOGGER.exception("Unexpected error setting up SimpleChores")
        raise ConfigEntryNotReady(f"Setup failed: {ex}") from ex
    
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception as ex:
        _LOGGER.exception("Failed to set up platforms")
        raise ConfigEntryNotReady(f"Failed to set up platforms: {ex}") from ex

    # ---- Services ----
    async def _add_points(call: ServiceCall) -> None:
        """Add points service handler."""
        try:
            _LOGGER.debug("SimpleChores: add_points service called")
            data = call.data

            kid = data["kid"]
            amount = int(data["amount"])
            reason = data.get("reason", "Manual adjust")

            _LOGGER.debug("Adding %d points to %s, reason: %s", amount, kid, reason)

            await coordinator.ensure_kid(kid)
            old_points = coordinator.get_points(kid)
            
            await coordinator.add_points(kid, amount, reason, "adjust")
            new_points = coordinator.get_points(kid)
            
            _LOGGER.info("Successfully added %d points to %s (%d -> %d)", 
                        amount, kid, old_points, new_points)

        except KeyError as ex:
            _LOGGER.error("Missing required parameter in add_points service: %s", ex)
            raise HomeAssistantError(f"Missing required parameter: {ex}") from ex
        except (ValueError, TypeError) as ex:
            _LOGGER.error("Invalid parameter value in add_points service: %s", ex)
            raise HomeAssistantError(f"Invalid parameter: {ex}") from ex
        except Exception as ex:
            _LOGGER.exception("Unexpected error in add_points service")
            raise HomeAssistantError(f"Service failed: {ex}") from ex

    async def _remove_points(call: ServiceCall) -> None:
        """Remove points service handler."""
        try:
            data = call.data
            kid = data["kid"]
            amount = int(data["amount"])
            reason = data.get("reason", "Manual adjust")

            await coordinator.ensure_kid(kid)
            old_points = coordinator.get_points(kid)
            
            await coordinator.remove_points(kid, amount, reason, "adjust")
            new_points = coordinator.get_points(kid)
            
            _LOGGER.info("Successfully removed %d points from %s (%d -> %d)", 
                        amount, kid, old_points, new_points)
                        
        except KeyError as ex:
            _LOGGER.error("Missing required parameter in remove_points service: %s", ex)
            raise HomeAssistantError(f"Missing required parameter: {ex}") from ex
        except (ValueError, TypeError) as ex:
            _LOGGER.error("Invalid parameter value in remove_points service: %s", ex)
            raise HomeAssistantError(f"Invalid parameter: {ex}") from ex
        except Exception as ex:
            _LOGGER.exception("Unexpected error in remove_points service")
            raise HomeAssistantError(f"Service failed: {ex}") from ex

    async def _create_adhoc(call: ServiceCall) -> None:
        """Create adhoc chore service handler."""
        try:
            data = call.data
            title = data["title"]
            points = int(data["points"])
            kid = data["kid"]
            chore_type = data.get("chore_type")
            
            await coordinator.ensure_kid(kid)

            # Create pending chore to track points
            todo_uid = await coordinator.create_pending_chore(kid, title, points, chore_type)
            _LOGGER.debug("Created pending chore %s for %s", todo_uid, kid)

            # Try to create todo item if todo entities are available
            title_with_points = f"{title} (+{points})"
            entity_id = f"todo.{kid}_chores"

            # Try to create todo item
            try:
                _LOGGER.debug("Attempting to create todo item '%s' for entity %s", 
                            title_with_points, entity_id)

                # Method 1: Try the standard todo service call
                try:
                    await hass.services.async_call(
                        "todo", "add_item",
                        {
                            "entity_id": entity_id,
                            "item": title_with_points
                        },
                        blocking=True,
                    )
                    _LOGGER.info("Successfully created todo item via service call")
                except ServiceNotFound:
                    _LOGGER.debug("Todo service not available, trying direct entity method")
                    # Method 2: Try to find and call the entity directly via coordinator
                    if hasattr(coordinator, '_todo_entities') and kid in coordinator._todo_entities:
                        todo_entity = coordinator._todo_entities[kid]
                        _LOGGER.debug("Found todo entity for %s, calling direct method", kid)
                        from homeassistant.components.todo import TodoItem, TodoItemStatus
                        new_item = TodoItem(
                            summary=title_with_points,
                            uid=todo_uid,
                            status=TodoItemStatus.NEEDS_ACTION
                        )
                        await todo_entity.async_create_item(new_item)
                        _LOGGER.info("Created todo item via direct entity method")
                    else:
                        _LOGGER.debug("No todo entity found for kid %s", kid)
                except Exception as service_error:
                    _LOGGER.warning("todo.add_item service failed: %s", service_error)
                    # Non-critical error - chore is still tracked via pending_chores

            except Exception as ex:
                _LOGGER.warning("Failed to create todo item: %s", ex)
                # Chore is still tracked via pending_chores, so this is not critical
                
            _LOGGER.info("Successfully created adhoc chore '%s' (%d points) for %s", 
                        title, points, kid)
                        
        except KeyError as ex:
            _LOGGER.error("Missing required parameter in create_adhoc service: %s", ex)
            raise HomeAssistantError(f"Missing required parameter: {ex}") from ex
        except (ValueError, TypeError) as ex:
            _LOGGER.error("Invalid parameter value in create_adhoc service: %s", ex)
            raise HomeAssistantError(f"Invalid parameter: {ex}") from ex
        except Exception as ex:
            _LOGGER.exception("Unexpected error in create_adhoc service")
            raise HomeAssistantError(f"Service failed: {ex}") from ex

    async def _complete_chore(call: ServiceCall) -> None:
        """Complete chore service handler."""
        try:
            data = call.data
            todo_uid = data.get("todo_uid") or data.get("chore_id")  # Support both names

            if todo_uid:
                # Complete chore by UID (preferred method)
                success = await coordinator.complete_chore_by_uid(todo_uid)
                if success:
                    _LOGGER.info("Successfully completed chore by UID: %s", todo_uid)
                else:
                    # Fallback to manual point award
                    if "kid" not in data:
                        _LOGGER.error("Chore UID not found and no fallback kid specified")
                        raise HomeAssistantError("Chore not found and no fallback kid specified")
                        
                    kid = data["kid"]
                    points = int(data.get("points", 0))
                    reason = data.get("reason", "Chore complete")
                    
                    await coordinator.ensure_kid(kid)
                    if points > 0:
                        await coordinator.add_points(kid, points, reason, "earn")
                        _LOGGER.info("Awarded %d points to %s as fallback", points, kid)
                    else:
                        _LOGGER.warning("No points awarded - fallback had 0 points")
            else:
                # Manual point award (legacy)
                if "kid" not in data:
                    raise HomeAssistantError("Either todo_uid/chore_id or kid must be specified")
                    
                kid = data["kid"]
                points = int(data.get("points", 0))
                reason = data.get("reason", "Chore complete")
                
                await coordinator.ensure_kid(kid)
                if points > 0:
                    await coordinator.add_points(kid, points, reason, "earn")
                    _LOGGER.info("Manual point award: %d points to %s", points, kid)
                else:
                    _LOGGER.warning("No points awarded - manual award had 0 points")
                    
        except KeyError as ex:
            _LOGGER.error("Missing required parameter in complete_chore service: %s", ex)
            raise HomeAssistantError(f"Missing required parameter: {ex}") from ex
        except (ValueError, TypeError) as ex:
            _LOGGER.error("Invalid parameter value in complete_chore service: %s", ex)
            raise HomeAssistantError(f"Invalid parameter: {ex}") from ex
        except Exception as ex:
            _LOGGER.exception("Unexpected error in complete_chore service")
            raise HomeAssistantError(f"Service failed: {ex}") from ex

    async def _claim_reward(call: ServiceCall) -> None:
        """Claim reward service handler."""
        try:
            data = call.data
            kid = data["kid"]
            reward_id = data.get("reward_id")

            await coordinator.ensure_kid(kid)

            if reward_id:
                # Use reward system
                reward = coordinator.get_reward(reward_id)
                if not reward:
                    raise HomeAssistantError(f"Reward not found: {reward_id}")

                # Check reward type and handle accordingly
                progress = coordinator.get_reward_progress(kid, reward_id)
                
                if reward.is_point_based():
                    # Traditional point-spending reward
                    if reward.cost is None:
                        raise HomeAssistantError(f"Point-based reward {reward_id} has no cost defined")
                    
                    kid_points = coordinator.get_points(kid)
                    if kid_points < reward.cost:
                        raise HomeAssistantError(f"Insufficient points: {kid} has {kid_points}, need {reward.cost}")

                    await coordinator.remove_points(kid, reward.cost, f"Reward: {reward.title}", "spend")
                    _LOGGER.info("Successfully claimed point reward '%s' for %s (%d points)", 
                               reward.title, kid, reward.cost)

                elif reward.is_completion_based() or reward.is_streak_based():
                    # Progress-based reward
                    if not progress or not progress.completed:
                        # Show current progress
                        if progress:
                            if reward.is_completion_based():
                                progress_msg = f"{progress.current_completions}/{reward.required_completions} completions"
                            else:
                                progress_msg = f"{progress.current_streak}/{reward.required_streak_days} day streak"
                            raise HomeAssistantError(f"Reward not yet achieved. Progress: {progress_msg}")
                        else:
                            raise HomeAssistantError(f"No progress found for reward {reward.title}")
                    
                    # Reward already achieved - trigger celebration
                    _LOGGER.info("Celebrating already achieved reward '%s' for %s", reward.title, kid)
                    
                else:
                    raise HomeAssistantError(f"Reward {reward_id} has no valid requirements defined")

                # Create calendar event if enabled and reward is available/achieved
                if reward.create_calendar_event and (reward.is_point_based() or (progress and progress.completed)):
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
                            blocking=True
                        )
                        _LOGGER.info("Created calendar event for reward: %s", reward.title)
                    except ServiceNotFound:
                        _LOGGER.warning("Calendar service not available - reward processed but no calendar event created")
                    except Exception as ex:
                        _LOGGER.error("Failed to create calendar event for reward: %s", ex)
                        # Don't fail the whole service - points already deducted
            else:
                # Legacy direct cost/title method
                if "cost" not in data:
                    raise HomeAssistantError("Either reward_id or cost must be specified")
                    
                cost = int(data["cost"])
                title = data.get("title", "Reward")
                
                kid_points = coordinator.get_points(kid)
                if kid_points < cost:
                    raise HomeAssistantError(f"Insufficient points: {kid} has {kid_points}, need {cost}")
                
                await coordinator.remove_points(kid, cost, f"Reward: {title}", "spend")
                _LOGGER.info("Successfully claimed legacy reward '%s' for %s (%d points)", 
                           title, kid, cost)
                           
        except KeyError as ex:
            _LOGGER.error("Missing required parameter in claim_reward service: %s", ex)
            raise HomeAssistantError(f"Missing required parameter: {ex}") from ex
        except (ValueError, TypeError) as ex:
            _LOGGER.error("Invalid parameter value in claim_reward service: %s", ex)
            raise HomeAssistantError(f"Invalid parameter: {ex}") from ex
        except Exception as ex:
            _LOGGER.exception("Unexpected error in claim_reward service")
            raise HomeAssistantError(f"Service failed: {ex}") from ex

    async def _log_parent_chore(call: ServiceCall) -> None:
        """Log parent chore service handler."""
        try:
            data = call.data
            parents_calendar = entry.data.get("parents_calendar", "calendar.parents")
            
            if "title" not in data:
                raise HomeAssistantError("Title is required for parent chore")

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
                    blocking=True
                )
                _LOGGER.info("Successfully created parent chore calendar event: %s", data["title"])
                
            except ServiceNotFound:
                _LOGGER.error("Calendar service not found - please ensure calendar integration is set up")
                raise HomeAssistantError("Calendar service not available")
            except Exception as ex:
                _LOGGER.error("Failed to create parent chore calendar event: %s", ex)
                raise HomeAssistantError(f"Calendar event creation failed: {ex}") from ex
                
        except KeyError as ex:
            _LOGGER.error("Missing required parameter in log_parent_chore service: %s", ex)
            raise HomeAssistantError(f"Missing required parameter: {ex}") from ex
        except Exception as ex:
            _LOGGER.exception("Unexpected error in log_parent_chore service")
            raise HomeAssistantError(f"Service failed: {ex}") from ex

    async def _create_recurring_chore(call: ServiceCall) -> None:
        """Create recurring chore service handler."""
        try:
            data = call.data
            kid = data["kid"]
            title = data["title"]
            points = int(data["points"])
            schedule_type = data["schedule_type"]
            day_of_week = data.get("day_of_week")

            if schedule_type not in ["daily", "weekly"]:
                raise HomeAssistantError("schedule_type must be 'daily' or 'weekly'")
                
            if schedule_type == "weekly" and day_of_week is None:
                raise HomeAssistantError("day_of_week is required for weekly chores")

            await coordinator.ensure_kid(kid)
            chore_type = data.get("chore_type")
            chore_id = await coordinator.create_recurring_chore(kid, title, points, schedule_type, day_of_week, chore_type)

            _LOGGER.info("Created recurring chore %s: %s for %s (%s)", 
                        chore_id, title, kid, schedule_type)
                        
        except KeyError as ex:
            _LOGGER.error("Missing required parameter in create_recurring_chore service: %s", ex)
            raise HomeAssistantError(f"Missing required parameter: {ex}") from ex
        except (ValueError, TypeError) as ex:
            _LOGGER.error("Invalid parameter value in create_recurring_chore service: %s", ex)
            raise HomeAssistantError(f"Invalid parameter: {ex}") from ex
        except Exception as ex:
            _LOGGER.exception("Unexpected error in create_recurring_chore service")
            raise HomeAssistantError(f"Service failed: {ex}") from ex

    async def _approve_chore(call: ServiceCall) -> None:
        """Approve chore service handler."""
        try:
            data = call.data
            approval_id = data["approval_id"]

            success = await coordinator.approve_chore(approval_id)
            
            if success:
                _LOGGER.info("Successfully approved chore: %s", approval_id)
            else:
                raise HomeAssistantError(f"Failed to approve chore: {approval_id} not found")
                
        except KeyError as ex:
            _LOGGER.error("Missing required parameter in approve_chore service: %s", ex)
            raise HomeAssistantError(f"Missing required parameter: {ex}") from ex
        except Exception as ex:
            _LOGGER.exception("Unexpected error in approve_chore service")
            raise HomeAssistantError(f"Service failed: {ex}") from ex

    async def _reject_chore(call: ServiceCall) -> None:
        """Reject chore service handler."""
        try:
            data = call.data
            approval_id = data["approval_id"]
            reason = data.get("reason", "Did not meet standards")

            success = await coordinator.reject_chore(approval_id, reason)
            
            if success:
                _LOGGER.info("Successfully rejected chore %s: %s", approval_id, reason)
            else:
                raise HomeAssistantError(f"Failed to reject chore: {approval_id} not found")
                
        except KeyError as ex:
            _LOGGER.error("Missing required parameter in reject_chore service: %s", ex)
            raise HomeAssistantError(f"Missing required parameter: {ex}") from ex
        except Exception as ex:
            _LOGGER.exception("Unexpected error in reject_chore service")
            raise HomeAssistantError(f"Service failed: {ex}") from ex

    async def _generate_recurring_chores(call: ServiceCall) -> None:
        """Generate daily and/or weekly recurring chores service handler."""
        try:
            data = call.data
            schedule_type = data.get("schedule_type", "daily")

            if schedule_type not in ["daily", "weekly"]:
                raise HomeAssistantError("schedule_type must be 'daily' or 'weekly'")

            if schedule_type == "daily":
                await coordinator.generate_daily_chores()
                _LOGGER.info("Successfully generated daily recurring chores")
            elif schedule_type == "weekly":
                from datetime import datetime
                current_day = datetime.now().weekday()  # 0=Monday, 6=Sunday
                target_day = data.get("day_of_week", current_day)
                
                if not isinstance(target_day, int) or target_day < 0 or target_day > 6:
                    raise HomeAssistantError("day_of_week must be an integer 0-6 (Monday-Sunday)")
                    
                await coordinator.generate_weekly_chores(target_day)
                _LOGGER.info("Successfully generated weekly recurring chores for day %d", target_day)
                
        except (ValueError, TypeError) as ex:
            _LOGGER.error("Invalid parameter value in generate_recurring_chores service: %s", ex)
            raise HomeAssistantError(f"Invalid parameter: {ex}") from ex
        except Exception as ex:
            _LOGGER.exception("Unexpected error in generate_recurring_chores service")
            raise HomeAssistantError(f"Service failed: {ex}") from ex

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
        vol.Optional("chore_type"): cv.string,
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
        vol.Optional("chore_type"): cv.string,
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
