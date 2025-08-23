"""Sensor entities for SimpleChores integration."""
from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorEntity
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
    for kid in kids:
        entities.append(SimpleChoresWeekSensor(coordinator, kid))
        entities.append(SimpleChoresTotalSensor(coordinator, kid))
        
        # Add reward progress sensors for each kid
        rewards = coordinator.get_rewards()
        for reward in rewards:
            if not reward.is_point_based():  # Only create progress sensors for completion/streak rewards
                entities.append(SimpleChoresRewardProgressSensor(coordinator, kid, reward))

    # Add pending approvals sensor
    entities.append(SimpleChoresPendingApprovalsSensor(coordinator))

    add_entities(entities, True)

class SimpleChoresWeekSensor(SensorEntity):
    def __init__(self, coord: SimpleChoresCoordinator, kid_id: str):
        self._coord = coord
        self._kid_id = kid_id
        self._attr_unique_id = f"{DOMAIN}_{kid_id}_points_week"
        self._attr_name = f"SimpleChores {kid_id.capitalize()} Points (This Week)"

    @property
    def native_value(self):
        # simple derived value from ledger
        model = self._coord.model
        if not model or not model.ledger:
            return 0
        monday = (datetime.now() - timedelta(days=datetime.now().weekday())).timestamp()
        return sum(e.delta for e in model.ledger if e.kid_id == self._kid_id and e.ts >= monday)

    @property
    def available(self) -> bool:
        """Check if coordinator is ready."""
        return self._coord.model is not None

class SimpleChoresTotalSensor(SensorEntity):
    def __init__(self, coord: SimpleChoresCoordinator, kid_id: str):
        self._coord = coord
        self._kid_id = kid_id
        self._attr_unique_id = f"{DOMAIN}_{kid_id}_points_total"
        self._attr_name = f"SimpleChores {kid_id.capitalize()} Points (Total Earned)"
        self._attr_icon = "mdi:star-circle-outline"

    @property
    def native_value(self):
        # Total points earned (not current balance)
        model = self._coord.model
        if not model or not model.ledger:
            return 0
        return sum(e.delta for e in model.ledger if e.kid_id == self._kid_id and e.delta > 0)

    @property
    def available(self) -> bool:
        """Check if coordinator is ready."""
        return self._coord.model is not None

class SimpleChoresPendingApprovalsSensor(SensorEntity):
    def __init__(self, coord: SimpleChoresCoordinator):
        self._coord = coord
        self._attr_unique_id = f"{DOMAIN}_pending_approvals"
        self._attr_name = "SimpleChores Pending Chore Approvals"
        self._attr_icon = "mdi:clipboard-check-multiple"
        # Store reference in coordinator for updates
        if not hasattr(coord, '_approval_sensors'):
            coord._approval_sensors = []
        coord._approval_sensors.append(self)

    @property
    def native_value(self):
        """Return the number of pending approvals."""
        if not self._coord.model:
            return 0
        return len(self._coord.get_pending_approvals())

    @property
    def extra_state_attributes(self):
        """Return the pending approvals as attributes."""
        if not self._coord.model:
            return {}

        pending_approvals = self._coord.get_pending_approvals()
        attributes = {
            "count": len(pending_approvals),
            "approvals": []
        }

        for approval in pending_approvals:
            attributes["approvals"].append({
                "id": approval.id,
                "kid": approval.kid_id,
                "title": approval.title,
                "points": approval.points,
                "completed_time": approval.completed_ts,
                "approve_service": "simplechores.approve_chore",
                "approve_data": {"approval_id": approval.id},
                "reject_service": "simplechores.reject_chore",
                "reject_data": {"approval_id": approval.id, "reason": "Not done properly"}
            })

        return attributes

    @property
    def available(self) -> bool:
        """Check if coordinator is ready."""
        return self._coord.model is not None


class SimpleChoresRewardProgressSensor(SensorEntity):
    """Sensor to track progress towards a completion/streak-based reward."""
    
    def __init__(self, coord: SimpleChoresCoordinator, kid_id: str, reward):
        self._coord = coord
        self._kid_id = kid_id
        self._reward = reward
        self._attr_unique_id = f"{DOMAIN}_{kid_id}_{reward.id}_progress"
        self._attr_name = f"{kid_id.capitalize()} Progress: {reward.title}"
        
        if reward.is_completion_based():
            self._attr_icon = "mdi:counter"
            self._attr_unit_of_measurement = "completions"
        else:  # streak-based
            self._attr_icon = "mdi:calendar-check"
            self._attr_unit_of_measurement = "days"

    @property
    def native_value(self):
        """Return current progress value."""
        progress = self._coord.get_reward_progress(self._kid_id, self._reward.id)
        if not progress:
            return 0
            
        if self._reward.is_completion_based():
            return progress.current_completions
        else:  # streak-based
            return progress.current_streak

    @property
    def extra_state_attributes(self):
        """Return detailed progress information."""
        progress = self._coord.get_reward_progress(self._kid_id, self._reward.id)
        
        attributes = {
            "reward_id": self._reward.id,
            "reward_title": self._reward.title,
            "reward_description": self._reward.description,
            "kid_id": self._kid_id,
            "completed": False,
            "completion_date": None,
            "reward_type": None,
            "progress_percentage": 0
        }
        
        if self._reward.is_completion_based():
            attributes.update({
                "reward_type": "completion",
                "required_completions": self._reward.required_completions,
                "current_completions": progress.current_completions if progress else 0,
                "remaining_completions": max(0, (self._reward.required_completions or 0) - (progress.current_completions if progress else 0)),
                "chore_type_required": self._reward.required_chore_type
            })
            if self._reward.required_completions:
                attributes["progress_percentage"] = int((progress.current_completions if progress else 0) / self._reward.required_completions * 100)
                
        elif self._reward.is_streak_based():
            attributes.update({
                "reward_type": "streak",
                "required_streak_days": self._reward.required_streak_days,
                "current_streak": progress.current_streak if progress else 0,
                "remaining_days": max(0, (self._reward.required_streak_days or 0) - (progress.current_streak if progress else 0)),
                "last_completion_date": progress.last_completion_date if progress else None,
                "chore_type_required": self._reward.required_chore_type
            })
            if self._reward.required_streak_days:
                attributes["progress_percentage"] = int((progress.current_streak if progress else 0) / self._reward.required_streak_days * 100)
        
        if progress:
            attributes["completed"] = progress.completed
            attributes["completion_date"] = progress.completion_date
            
        return attributes

    @property
    def available(self) -> bool:
        """Check if coordinator is ready."""
        return self._coord.model is not None
