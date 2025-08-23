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
