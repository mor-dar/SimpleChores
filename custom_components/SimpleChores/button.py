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

    # Dynamic approval/rejection buttons - create discovery buttons for each kid
    for kid_id in kids:
        entities.append(SimpleChoresTodayApprovalButton(coordinator, kid_id, hass))

    # Individual chore claim buttons - create a button for each pending chore
    if hasattr(coordinator.model, 'pending_chores') and coordinator.model.pending_chores:
        for todo_uid, chore in coordinator.model.pending_chores.items():
            if chore.status == "pending":  # Only create buttons for pending chores
                entities.append(SimpleChoresIndividualClaimButton(coordinator, todo_uid, hass))

    # Fallback bulk claim button for each kid (for remaining chores after individual claims)
    for kid_id in kids:
        entities.append(SimpleChoresTodayClaimButton(coordinator, kid_id, hass))

    # Dynamic approval button for parents (shows all pending approvals)
    entities.append(SimpleChoresApprovalManagerButton(coordinator, hass))

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
        self._attr_name = "SimpleChores Create Chore"

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
            _LOGGER.warning(f"SimpleChores: Found states - title: {title_entity}, points: {points_entity}, kid: {kid_entity}")
            return

        title = title_entity.state if title_entity else ""
        try:
            points = int(points_entity.state) if points_entity and points_entity.state else 5
        except (ValueError, TypeError):
            points = 5
        kid = kid_entity.state if kid_entity else ""

        _LOGGER.info(f"SimpleChores: Creating chore - title: '{title}', points: {points}, kid: '{kid}'")

        # Validate inputs
        if not title or title.strip() == "" or title == "Enter chore name":
            _LOGGER.warning("SimpleChores: Title is empty or still default value")
            return
            
        if not kid or kid.strip() == "":
            _LOGGER.warning("SimpleChores: Kid is empty")
            return

        # Create chore via service
        try:
            await self._hass.services.async_call(
                DOMAIN, "create_adhoc_chore",
                {"kid": kid.strip(), "title": title.strip(), "points": points}
            )
            _LOGGER.info("SimpleChores: Successfully called create_adhoc_chore service")
            
            # Clear the title field after successful creation
            if title_entity_id:
                await self._hass.services.async_call(
                    "text", "set_value",
                    {"entity_id": title_entity_id, "value": ""}
                )
        except Exception as e:
            _LOGGER.error(f"SimpleChores: Failed to call create_adhoc_chore service: {e}")
            import traceback
            _LOGGER.error(f"SimpleChores: Traceback: {traceback.format_exc()}")

class SimpleChoresRewardButton(ButtonEntity):
    _attr_icon = "mdi:gift"

    def __init__(self, coord: SimpleChoresCoordinator, reward_id: str, kid_id: str, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._reward_id = reward_id
        self._kid_id = kid_id
        reward = coord.get_reward(reward_id)
        # Use consistent naming pattern for auto-entities: simplechores_{reward_id}_reward_{kid_id}
        self._attr_unique_id = f"{DOMAIN}_{reward_id}_reward_{kid_id}"
        if reward:
            if reward.is_point_based():
                self._attr_name = f"SimpleChores {reward.title} ({kid_id.capitalize()}) - {reward.cost}pts"
            else:
                self._attr_name = f"SimpleChores {reward.title} ({kid_id.capitalize()})"
        else:
            self._attr_name = f"SimpleChores Unknown Reward ({kid_id.capitalize()})"

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
        self._attr_name = "SimpleChores Create Recurring Chore"

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
            _LOGGER.warning(f"SimpleChores: Found states - title: {title_entity}, points: {points_entity}, kid: {kid_entity}, schedule: {schedule_entity}, day: {day_entity}")
            return

        title = title_entity.state if title_entity else ""
        try:
            points = int(points_entity.state) if points_entity and points_entity.state else 2
        except (ValueError, TypeError):
            points = 2
        kid = kid_entity.state if kid_entity else ""
        schedule_type = schedule_entity.state if schedule_entity else ""
        try:
            day_of_week = int(day_entity.state) if schedule_type == "weekly" and day_entity and day_entity.state else None
        except (ValueError, TypeError):
            day_of_week = None

        _LOGGER.info(f"SimpleChores: Creating recurring chore - title: '{title}', points: {points}, kid: '{kid}', schedule: '{schedule_type}', day: {day_of_week}")

        # Validate inputs
        if not title or title.strip() == "":
            _LOGGER.warning("SimpleChores: Recurring title is empty")
            return
            
        if not kid or kid.strip() == "":
            _LOGGER.warning("SimpleChores: Recurring kid is empty")
            return
            
        if not schedule_type or schedule_type not in ["daily", "weekly"]:
            _LOGGER.warning(f"SimpleChores: Invalid schedule type: '{schedule_type}' (must be 'daily' or 'weekly')")
            return

        try:
            service_data = {
                "kid": kid.strip(),
                "title": title.strip(),
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
            
            # Clear the title field after successful creation
            if title_entity_id:
                await self._hass.services.async_call(
                    "text", "set_value",
                    {"entity_id": title_entity_id, "value": "Brush teeth"}
                )
        except Exception as e:
            _LOGGER.error(f"SimpleChores: Failed to call create_recurring_chore service: {e}")
            import traceback
            _LOGGER.error(f"SimpleChores: Traceback: {traceback.format_exc()}")

class SimpleChoresGenerateDailyButton(ButtonEntity):
    _attr_icon = "mdi:calendar-today"

    def __init__(self, coord: SimpleChoresCoordinator, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._attr_unique_id = f"{DOMAIN}_generate_daily_button"
        self._attr_name = "SimpleChores Generate Today's Chores"

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
        self._attr_name = "SimpleChores Show Pending Approvals"
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
            return f"SimpleChores Pending Approvals ({pending_count})"
        return "SimpleChores Pending Approvals (0)"

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

class SimpleChoresApproveButton(ButtonEntity):
    """Button to approve a specific chore."""
    _attr_icon = "mdi:check-circle"

    def __init__(self, coord: SimpleChoresCoordinator, approval_id: str, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._approval_id = approval_id
        # Use consistent naming pattern: simplechores_approve_{approval_id}
        self._attr_unique_id = f"{DOMAIN}_approve_{approval_id}"
        
        # Get approval details for friendly name
        approval = coord.get_pending_approval(approval_id)
        if approval:
            self._attr_name = f"SimpleChores Approve {approval.title} ({approval.kid_id.capitalize()})"
        else:
            self._attr_name = f"SimpleChores Approve {approval_id}"

    async def async_press(self) -> None:
        """Handle the button press."""
        import logging
        _LOGGER = logging.getLogger(__name__)
        
        try:
            await self._hass.services.async_call(
                DOMAIN, "approve_chore",
                {"approval_id": self._approval_id}
            )
            _LOGGER.info("SimpleChores: Approved chore %s", self._approval_id)
        except Exception as e:
            _LOGGER.error(f"SimpleChores: Failed to approve chore {self._approval_id}: {e}")

    @property
    def available(self) -> bool:
        """Check if approval button should be available."""
        if self._coord.model is None:
            return False
        approval = self._coord.get_pending_approval(self._approval_id)
        return approval is not None


class SimpleChoresRejectButton(ButtonEntity):
    """Button to reject a specific chore."""
    _attr_icon = "mdi:close-circle"

    def __init__(self, coord: SimpleChoresCoordinator, approval_id: str, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._approval_id = approval_id
        # Use consistent naming pattern: simplechores_reject_{approval_id}
        self._attr_unique_id = f"{DOMAIN}_reject_{approval_id}"
        
        # Get approval details for friendly name
        approval = coord.get_pending_approval(approval_id)
        if approval:
            self._attr_name = f"SimpleChores Reject {approval.title} ({approval.kid_id.capitalize()})"
        else:
            self._attr_name = f"SimpleChores Reject {approval_id}"

    async def async_press(self) -> None:
        """Handle the button press."""
        import logging
        _LOGGER = logging.getLogger(__name__)
        
        try:
            await self._hass.services.async_call(
                DOMAIN, "reject_chore",
                {"approval_id": self._approval_id, "reason": "Rejected via dashboard"}
            )
            _LOGGER.info("SimpleChores: Rejected chore %s", self._approval_id)
        except Exception as e:
            _LOGGER.error(f"SimpleChores: Failed to reject chore {self._approval_id}: {e}")

    @property
    def available(self) -> bool:
        """Check if rejection button should be available."""
        if self._coord.model is None:
            return False
        approval = self._coord.get_pending_approval(self._approval_id)
        return approval is not None


class SimpleChoresClaimButton(ButtonEntity):
    """Button for kids to claim chore completion and request approval."""
    _attr_icon = "mdi:hand-heart"

    def __init__(self, coord: SimpleChoresCoordinator, todo_uid: str, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._todo_uid = todo_uid
        # Use consistent naming pattern: simplechores_claim_{todo_uid}
        self._attr_unique_id = f"{DOMAIN}_claim_{todo_uid}"
        
        # Get chore details for friendly name
        chore = coord.get_pending_chore(todo_uid)
        if chore:
            self._attr_name = f"SimpleChores Claim {chore.title} ({chore.kid_id.capitalize()}) - {chore.points}pts"
        else:
            self._attr_name = f"SimpleChores Claim {todo_uid}"

    async def async_press(self) -> None:
        """Handle the button press - kid claims chore completion."""
        import logging
        _LOGGER = logging.getLogger(__name__)
        
        try:
            await self._hass.services.async_call(
                DOMAIN, "request_approval",
                {"todo_uid": self._todo_uid}
            )
            _LOGGER.info("SimpleChores: Requested approval for chore %s", self._todo_uid)
        except Exception as e:
            _LOGGER.error(f"SimpleChores: Failed to request approval for chore {self._todo_uid}: {e}")

    @property
    def available(self) -> bool:
        """Check if claim button should be available."""
        if self._coord.model is None:
            return False
        chore = self._coord.get_pending_chore(self._todo_uid)
        # Only available for pending chores (not completed/approved/rejected)
        return chore is not None and chore.status == "pending"


class SimpleChoresResetRejectedButton(ButtonEntity):
    _attr_icon = "mdi:restore"

    def __init__(self, coord: SimpleChoresCoordinator, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._attr_unique_id = f"{DOMAIN}_reset_rejected_button"
        self._attr_name = "SimpleChores Reset Rejected Chores"

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


class SimpleChoresTodayClaimButton(ButtonEntity):
    """Dynamic button for kids to claim their pending chores for approval."""
    _attr_icon = "mdi:hand-heart"

    def __init__(self, coord: SimpleChoresCoordinator, kid_id: str, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._kid_id = kid_id
        self._attr_unique_id = f"{DOMAIN}_claim_chores_{kid_id}"
        self._attr_name = f"SimpleChores Claim Chores ({kid_id.capitalize()})"
        
        # Register with coordinator for updates
        if not hasattr(coord, '_claim_buttons'):
            coord._claim_buttons = []
        coord._claim_buttons.append(self)

    @property
    def available(self) -> bool:
        """Show button only when kid has multiple pending chores (fallback for bulk operations)."""
        if self._coord.model is None:
            return False
        
        # Check if this kid has multiple pending chores
        # Individual buttons handle single chores, this is for bulk claiming
        pending_chores = [
            chore for chore in self._coord.model.pending_chores.values() 
            if chore.kid_id == self._kid_id and chore.status == "pending"
        ]
        return len(pending_chores) > 1  # Only show for multiple chores

    @property
    def name(self) -> str:
        """Show count of pending chores in button name."""
        if self._coord.model is None:
            return f"SimpleChores Claim Chores ({self._kid_id.capitalize()})"
            
        pending_count = len([
            chore for chore in self._coord.model.pending_chores.values() 
            if chore.kid_id == self._kid_id and chore.status == "pending"
        ])
        
        return f"SimpleChores Claim ALL Chores ({self._kid_id.capitalize()}) - {pending_count} remaining"

    async def async_press(self) -> None:
        """Claim ALL pending chores for this kid (bulk operation)."""
        import logging
        _LOGGER = logging.getLogger(__name__)
        
        if self._coord.model is None:
            _LOGGER.warning("No model available")
            return
            
        # Find all pending chores for this kid
        pending_chores = [
            chore for chore in self._coord.model.pending_chores.values()
            if chore.kid_id == self._kid_id and chore.status == "pending"
        ]
                
        if not pending_chores:
            _LOGGER.warning("No pending chores found for %s", self._kid_id)
            return
            
        _LOGGER.info("Bulk claiming %d chores for %s", len(pending_chores), self._kid_id)
        
        claimed_count = 0
        for chore in pending_chores:
            try:
                await self._hass.services.async_call(
                    DOMAIN, "request_approval",
                    {"todo_uid": chore.todo_uid}
                )
                claimed_count += 1
                _LOGGER.info("Bulk claimed: %s for %s", chore.title, self._kid_id)
            except Exception as e:
                _LOGGER.error("Failed to claim chore %s for %s: %s", chore.title, self._kid_id, e)
        
        _LOGGER.info("Bulk claim complete: %d/%d chores claimed for %s", 
                    claimed_count, len(pending_chores), self._kid_id)


class SimpleChoresIndividualClaimButton(ButtonEntity):
    """Individual button for claiming a specific chore."""
    _attr_icon = "mdi:check-circle"

    def __init__(self, coord: SimpleChoresCoordinator, todo_uid: str, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._todo_uid = todo_uid
        self._attr_unique_id = f"{DOMAIN}_claim_chore_{todo_uid[:8]}"
        
        # Get chore details for friendly name
        chore = coord.get_pending_chore(todo_uid)
        if chore:
            self._attr_name = f"SimpleChores Claim: {chore.title} (+{chore.points}pts)"
        else:
            self._attr_name = f"SimpleChores Claim Chore {todo_uid[:8]}"

        # Register with coordinator for updates
        if not hasattr(coord, '_individual_claim_buttons'):
            coord._individual_claim_buttons = []
        coord._individual_claim_buttons.append(self)

    @property
    def available(self) -> bool:
        """Show button only when chore exists and is pending."""
        if self._coord.model is None:
            return False
        
        chore = self._coord.get_pending_chore(self._todo_uid)
        return chore is not None and chore.status == "pending"

    @property
    def name(self) -> str:
        """Dynamic name based on current chore state."""
        if self._coord.model is None:
            return self._attr_name
            
        chore = self._coord.get_pending_chore(self._todo_uid)
        if chore:
            return f"SimpleChores Claim: {chore.title} (+{chore.points}pts)"
        else:
            return f"SimpleChores Claim Chore {self._todo_uid[:8]} (Not Found)"

    async def async_press(self) -> None:
        """Claim this specific chore."""
        import logging
        _LOGGER = logging.getLogger(__name__)
        
        chore = self._coord.get_pending_chore(self._todo_uid)
        if not chore:
            _LOGGER.warning("Cannot claim chore %s - not found", self._todo_uid)
            return
            
        if chore.status != "pending":
            _LOGGER.warning("Cannot claim chore %s - status is %s", self._todo_uid, chore.status)
            return
            
        try:
            await self._hass.services.async_call(
                DOMAIN, "request_approval",
                {"todo_uid": self._todo_uid}
            )
            _LOGGER.info("Claimed specific chore: %s for %s", chore.title, chore.kid_id)
        except Exception as e:
            _LOGGER.error("Failed to claim chore %s: %s", self._todo_uid, e)


class SimpleChoresTodayApprovalButton(ButtonEntity):
    """Dynamic button for parents to approve/reject chores for a specific kid."""
    _attr_icon = "mdi:clipboard-check"

    def __init__(self, coord: SimpleChoresCoordinator, kid_id: str, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._kid_id = kid_id
        self._attr_unique_id = f"{DOMAIN}_approve_chores_{kid_id}"
        self._attr_name = f"SimpleChores Manage Approvals ({kid_id.capitalize()})"
        
        # Register with coordinator for updates
        if not hasattr(coord, '_approval_manager_buttons'):
            coord._approval_manager_buttons = []
        coord._approval_manager_buttons.append(self)

    @property
    def available(self) -> bool:
        """Show button only when kid has pending approvals."""
        if self._coord.model is None:
            return False
        
        # Check if this kid has any pending approvals
        pending_approvals = [
            approval for approval in self._coord.model.pending_approvals.values() 
            if approval.kid_id == self._kid_id and approval.status == "pending_approval"
        ]
        return len(pending_approvals) > 0

    @property  
    def name(self) -> str:
        """Show count of pending approvals in button name."""
        if self._coord.model is None:
            return f"SimpleChores Manage Approvals ({self._kid_id.capitalize()})"
            
        pending_count = len([
            approval for approval in self._coord.model.pending_approvals.values() 
            if approval.kid_id == self._kid_id and approval.status == "pending_approval"
        ])
        
        return f"SimpleChores Manage Approvals ({self._kid_id.capitalize()}) - {pending_count} pending"

    async def async_press(self) -> None:
        """Log all pending approvals for this kid with approve/reject instructions."""
        import logging
        _LOGGER = logging.getLogger(__name__)
        
        if self._coord.model is None:
            _LOGGER.warning("No model available")
            return
            
        # Find all pending approvals for this kid
        pending_approvals = [
            approval for approval in self._coord.model.pending_approvals.values() 
            if approval.kid_id == self._kid_id and approval.status == "pending_approval"
        ]
        
        if not pending_approvals:
            _LOGGER.warning("No pending approvals found for %s", self._kid_id)
            return
            
        _LOGGER.info("=== PENDING APPROVALS FOR %s ===", self._kid_id.upper())
        for approval in pending_approvals:
            _LOGGER.info("📋 %s - %d points", approval.title, approval.points)
            _LOGGER.info("   ✅ Approve: simplechores.approve_chore - approval_id: %s", approval.id)
            _LOGGER.info("   ❌ Reject:  simplechores.reject_chore - approval_id: %s", approval.id)
            _LOGGER.info("")


class SimpleChoresApprovalManagerButton(ButtonEntity):
    """Unified button for managing all pending approvals across all kids."""
    _attr_icon = "mdi:account-supervisor"

    def __init__(self, coord: SimpleChoresCoordinator, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._attr_unique_id = f"{DOMAIN}_approval_manager"
        self._attr_name = "SimpleChores Approval Manager"
        
        # Register with coordinator for updates  
        if not hasattr(coord, '_approval_manager_buttons'):
            coord._approval_manager_buttons = []
        coord._approval_manager_buttons.append(self)

    @property
    def available(self) -> bool:
        """Show button only when there are any pending approvals."""
        if self._coord.model is None:
            return False
        
        pending_approvals = [
            approval for approval in self._coord.model.pending_approvals.values() 
            if approval.status == "pending_approval"
        ]
        return len(pending_approvals) > 0

    @property  
    def name(self) -> str:
        """Show total count of pending approvals."""
        if self._coord.model is None:
            return "SimpleChores Approval Manager"
            
        pending_count = len([
            approval for approval in self._coord.model.pending_approvals.values() 
            if approval.status == "pending_approval"
        ])
        
        if pending_count == 0:
            return "SimpleChores Approval Manager"
        else:
            return f"SimpleChores Approval Manager - {pending_count} total pending"

    async def async_press(self) -> None:
        """Show all pending approvals with bulk management options."""
        import logging
        _LOGGER = logging.getLogger(__name__)
        
        if self._coord.model is None:
            _LOGGER.warning("No model available")
            return
            
        # Find all pending approvals
        pending_approvals = [
            approval for approval in self._coord.model.pending_approvals.values() 
            if approval.status == "pending_approval"
        ]
        
        if not pending_approvals:
            _LOGGER.info("🎉 No pending approvals - all caught up!")
            return
            
        _LOGGER.info("=== ALL PENDING APPROVALS ===")
        
        # Group by kid for better organization
        by_kid = {}
        for approval in pending_approvals:
            if approval.kid_id not in by_kid:
                by_kid[approval.kid_id] = []
            by_kid[approval.kid_id].append(approval)
            
        for kid_id, approvals in by_kid.items():
            _LOGGER.info("👦 %s (%d pending):", kid_id.upper(), len(approvals))
            for approval in approvals:
                _LOGGER.info("  📋 %s - %d points [ID: %s]", approval.title, approval.points, approval.id)
            _LOGGER.info("")
            
        _LOGGER.info("💡 Use individual kid approval buttons or call services directly:")
        _LOGGER.info("   ✅ simplechores.approve_chore")  
        _LOGGER.info("   ❌ simplechores.reject_chore")
