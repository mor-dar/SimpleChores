"""Button entities for SimpleChores integration."""
from __future__ import annotations
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .coordinator import SimpleChoresCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add_entities: AddEntitiesCallback):
    coordinator: SimpleChoresCoordinator = hass.data[DOMAIN][entry.entry_id]
    kids_csv = entry.data.get("kids", "alex,emma")
    kids = [k.strip() for k in kids_csv.split(",") if k.strip()]
    
    entities = []
    # Create chore button
    entities.append(SimpleChoresCreateChoreButton(coordinator, hass))
    
    # Create recurring chore button
    entities.append(SimpleChoresCreateRecurringButton(coordinator, hass))
    
    # Generate daily chores button
    entities.append(SimpleChoresGenerateDailyButton(coordinator, hass))
    
    # Approval status button
    entities.append(SimpleChoresApprovalStatusButton(coordinator, hass))
    
    # Individual approval buttons will be created dynamically
    
    # Reset rejected chores button
    entities.append(SimpleChoresResetRejectedButton(coordinator, hass))
    
    # Reward buttons - use kids from config since coordinator.model.kids might be empty during setup
    for reward in coordinator.get_rewards():
        for kid_id in kids:
            entities.append(SimpleChoresRewardButton(coordinator, reward.id, kid_id, hass))
    
    add_entities(entities, True)

class SimpleChoresCreateChoreButton(ButtonEntity):
    _attr_icon = "mdi:plus-circle"

    def __init__(self, coord: SimpleChoresCoordinator, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._attr_unique_id = f"{DOMAIN}_create_chore_button"
        self._attr_name = "Create Chore"

    async def async_press(self) -> None:
        import logging
        _LOGGER = logging.getLogger(__name__)
        
        _LOGGER.info("SimpleChores: Create chore button pressed")
        
        # Get values from input helpers - use entity registry for proper entity IDs
        from homeassistant.helpers import entity_registry as er
        
        er_registry = er.async_get(self._hass)
        
        # Find the text input entities
        title_entity_id = None
        points_entity_id = None
        kid_entity_id = None
        
        for entry in er_registry.entities.values():
            if entry.unique_id == f"{DOMAIN}_chore_title_input":
                title_entity_id = entry.entity_id
            elif entry.unique_id == f"{DOMAIN}_chore_points_input":
                points_entity_id = entry.entity_id  
            elif entry.unique_id == f"{DOMAIN}_chore_kid_input":
                kid_entity_id = entry.entity_id
        
        _LOGGER.debug(f"SimpleChores: Found entity IDs - title: {title_entity_id}, points: {points_entity_id}, kid: {kid_entity_id}")
        
        if not all([title_entity_id, points_entity_id, kid_entity_id]):
            _LOGGER.warning("SimpleChores: Could not find all required text input entities")
            return
            
        title_entity = self._hass.states.get(title_entity_id)
        points_entity = self._hass.states.get(points_entity_id)
        kid_entity = self._hass.states.get(kid_entity_id)
        
        if not all([title_entity, points_entity, kid_entity]):
            _LOGGER.warning("SimpleChores: Could not get states for all text input entities")
            return
            
        title = title_entity.state
        try:
            points = int(points_entity.state)
        except (ValueError, TypeError):
            points = 5
        kid = kid_entity.state
        
        _LOGGER.info(f"SimpleChores: Creating chore - title: '{title}', points: {points}, kid: '{kid}'")
        
        if title and kid:
            # Create chore via service
            try:
                await self._hass.services.async_call(
                    DOMAIN, "create_adhoc_chore",
                    {"kid": kid, "title": title, "points": points}
                )
                _LOGGER.info("SimpleChores: Successfully called create_adhoc_chore service")
            except Exception as e:
                _LOGGER.error(f"SimpleChores: Failed to call create_adhoc_chore service: {e}")
        else:
            _LOGGER.warning(f"SimpleChores: Missing title or kid - title: '{title}', kid: '{kid}'")

class SimpleChoresRewardButton(ButtonEntity):
    _attr_icon = "mdi:gift"

    def __init__(self, coord: SimpleChoresCoordinator, reward_id: str, kid_id: str, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._reward_id = reward_id
        self._kid_id = kid_id
        reward = coord.get_reward(reward_id)
        self._attr_unique_id = f"{DOMAIN}_reward_{reward_id}_{kid_id}"
        if reward:
            self._attr_name = f"{reward.title} ({kid_id.capitalize()}) - {reward.cost}pts"
        else:
            self._attr_name = f"Unknown Reward ({kid_id.capitalize()})"

    @property
    def available(self) -> bool:
        """Check if reward button should be available."""
        if self._coord.model is None:
            return False
        reward = self._coord.get_reward(self._reward_id)
        if not reward:
            return False
        kid_points = self._coord.get_points(self._kid_id)
        return kid_points >= reward.cost

    async def async_press(self) -> None:
        reward = self._coord.get_reward(self._reward_id)
        kid_points = self._coord.get_points(self._kid_id)
        
        if reward and kid_points >= reward.cost:
            await self._hass.services.async_call(
                DOMAIN, "claim_reward",
                {"kid": self._kid_id, "reward_id": self._reward_id}
            )

class SimpleChoresCreateRecurringButton(ButtonEntity):
    _attr_icon = "mdi:repeat"

    def __init__(self, coord: SimpleChoresCoordinator, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._attr_unique_id = f"{DOMAIN}_create_recurring_button"
        self._attr_name = "Create Recurring Chore"

    async def async_press(self) -> None:
        import logging
        _LOGGER = logging.getLogger(__name__)
        
        _LOGGER.info("SimpleChores: Create recurring chore button pressed")
        
        # Get values from recurring input helpers
        from homeassistant.helpers import entity_registry as er
        
        er_registry = er.async_get(self._hass)
        
        # Find the recurring input entities
        title_entity_id = None
        points_entity_id = None
        kid_entity_id = None
        schedule_entity_id = None
        day_entity_id = None
        
        for entry in er_registry.entities.values():
            if entry.unique_id == f"{DOMAIN}_recurring_title_input":
                title_entity_id = entry.entity_id
            elif entry.unique_id == f"{DOMAIN}_recurring_points_input":
                points_entity_id = entry.entity_id  
            elif entry.unique_id == f"{DOMAIN}_recurring_kid_input":
                kid_entity_id = entry.entity_id
            elif entry.unique_id == f"{DOMAIN}_recurring_schedule_input":
                schedule_entity_id = entry.entity_id
            elif entry.unique_id == f"{DOMAIN}_recurring_day_input":
                day_entity_id = entry.entity_id
        
        if not all([title_entity_id, points_entity_id, kid_entity_id, schedule_entity_id, day_entity_id]):
            _LOGGER.warning("SimpleChores: Could not find all required recurring chore input entities")
            return
            
        title_entity = self._hass.states.get(title_entity_id)
        points_entity = self._hass.states.get(points_entity_id)
        kid_entity = self._hass.states.get(kid_entity_id)
        schedule_entity = self._hass.states.get(schedule_entity_id)
        day_entity = self._hass.states.get(day_entity_id)
        
        if not all([title_entity, points_entity, kid_entity, schedule_entity, day_entity]):
            _LOGGER.warning("SimpleChores: Could not get states for all recurring chore input entities")
            return
            
        title = title_entity.state
        try:
            points = int(points_entity.state)
        except (ValueError, TypeError):
            points = 2
        kid = kid_entity.state
        schedule_type = schedule_entity.state
        try:
            day_of_week = int(day_entity.state) if schedule_type == "weekly" else None
        except (ValueError, TypeError):
            day_of_week = None
        
        _LOGGER.info(f"SimpleChores: Creating recurring chore - title: '{title}', points: {points}, kid: '{kid}', schedule: '{schedule_type}', day: {day_of_week}")
        
        if title and kid and schedule_type:
            try:
                service_data = {
                    "kid": kid, 
                    "title": title, 
                    "points": points,
                    "schedule_type": schedule_type
                }
                if day_of_week is not None:
                    service_data["day_of_week"] = day_of_week
                    
                await self._hass.services.async_call(
                    DOMAIN, "create_recurring_chore",
                    service_data
                )
                _LOGGER.info("SimpleChores: Successfully called create_recurring_chore service")
            except Exception as e:
                _LOGGER.error(f"SimpleChores: Failed to call create_recurring_chore service: {e}")
        else:
            _LOGGER.warning(f"SimpleChores: Missing required fields - title: '{title}', kid: '{kid}', schedule: '{schedule_type}'")

class SimpleChoresGenerateDailyButton(ButtonEntity):
    _attr_icon = "mdi:calendar-today"

    def __init__(self, coord: SimpleChoresCoordinator, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._attr_unique_id = f"{DOMAIN}_generate_daily_button"
        self._attr_name = "Generate Today's Chores"

    async def async_press(self) -> None:
        import logging
        _LOGGER = logging.getLogger(__name__)
        
        _LOGGER.info("SimpleChores: Generate daily chores button pressed")
        
        try:
            await self._hass.services.async_call(
                DOMAIN, "generate_recurring_chores",
                {"schedule_type": "daily"}
            )
            _LOGGER.info("SimpleChores: Successfully generated daily chores")
        except Exception as e:
            _LOGGER.error(f"SimpleChores: Failed to generate daily chores: {e}")

class SimpleChoresApprovalStatusButton(ButtonEntity):
    _attr_icon = "mdi:clipboard-check"

    def __init__(self, coord: SimpleChoresCoordinator, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._attr_unique_id = f"{DOMAIN}_approval_status_button"
        self._attr_name = "Show Pending Approvals"
        # Store reference in coordinator for updates
        if not hasattr(coord, '_approval_buttons'):
            coord._approval_buttons = []
        coord._approval_buttons.append(self)

    @property
    def name(self) -> str:
        if self._coord.model:
            pending_count = len(self._coord.get_pending_approvals())
            import logging
            _LOGGER = logging.getLogger(__name__)
            _LOGGER.debug(f"SimpleChores: Approval button name check - pending count: {pending_count}")
            return f"Pending Approvals ({pending_count})"
        return "Pending Approvals (0)"

    @property
    def available(self) -> bool:
        if self._coord.model:
            pending_count = len(self._coord.get_pending_approvals())
            import logging
            _LOGGER = logging.getLogger(__name__)
            _LOGGER.debug(f"SimpleChores: Approval button availability check - pending count: {pending_count}")
            return pending_count > 0
        return False

    async def async_press(self) -> None:
        import logging
        _LOGGER = logging.getLogger(__name__)
        
        pending_approvals = self._coord.get_pending_approvals()
        _LOGGER.info(f"SimpleChores: {len(pending_approvals)} pending approvals:")
        
        for approval in pending_approvals:
            _LOGGER.info(f"  - ID: {approval.id}, Kid: {approval.kid_id}, Chore: {approval.title}, Points: {approval.points}")
            _LOGGER.info(f"    To approve: simplechores.approve_chore with approval_id: {approval.id}")
            _LOGGER.info(f"    To reject: simplechores.reject_chore with approval_id: {approval.id}")

class SimpleChoresResetRejectedButton(ButtonEntity):
    _attr_icon = "mdi:restore"

    def __init__(self, coord: SimpleChoresCoordinator, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._attr_unique_id = f"{DOMAIN}_reset_rejected_button"
        self._attr_name = "Reset Rejected Chores"

    async def async_press(self) -> None:
        import logging
        _LOGGER = logging.getLogger(__name__)
        
        _LOGGER.info("SimpleChores: Reset rejected chores button pressed")
        
        # Find rejected chores and reset them
        reset_count = 0
        for chore in self._coord.model.pending_chores.values():
            if chore.status == "rejected":
                chore.status = "pending"
                chore.completed_ts = None
                chore.approved_ts = None
                reset_count += 1
                
                # Also reset the todo item if it exists
                if hasattr(self._coord, '_todo_entities') and chore.kid_id in self._coord._todo_entities:
                    todo_entity = self._coord._todo_entities[chore.kid_id]
                    for item in todo_entity._items:
                        if item.uid == chore.todo_uid:
                            # Remove [PENDING APPROVAL] prefix if present
                            if item.summary.startswith("[PENDING APPROVAL]"):
                                item.summary = item.summary.replace("[PENDING APPROVAL] ", "")
                            # Reset to uncompleted
                            from homeassistant.components.todo import TodoItemStatus
                            item.status = TodoItemStatus.NEEDS_ACTION
                            break
                    todo_entity.async_write_ha_state()
        
        # Remove rejected approvals
        rejected_approvals = [a for a in self._coord.model.pending_approvals.values() if a.status == "rejected"]
        for approval in rejected_approvals:
            del self._coord.model.pending_approvals[approval.id]
        
        await self._coord.async_save()
        
        _LOGGER.info(f"SimpleChores: Reset {reset_count} rejected chores and removed {len(rejected_approvals)} rejected approvals")