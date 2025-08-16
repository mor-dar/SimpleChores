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
    add_entities([SimpleChoresWeekSensor(coordinator, kid) for kid in kids], True)

class SimpleChoresWeekSensor(SensorEntity):
    def __init__(self, coord: SimpleChoresCoordinator, kid_id: str):
        self._coord = coord
        self._kid_id = kid_id
        self._attr_unique_id = f"{DOMAIN}_{kid_id}_points_week"
        self._attr_name = f"{kid_id.capitalize()} Points (This Week)"

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
