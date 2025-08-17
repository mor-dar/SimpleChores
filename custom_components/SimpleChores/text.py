"""Text input entities for SimpleChores integration."""
from __future__ import annotations
from homeassistant.components.text import TextEntity
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
    # Add chore input helpers
    entities.append(SimpleChoresChoreTitle(coordinator))
    entities.append(SimpleChoresChorePoints(coordinator))
    entities.append(SimpleChoresChoreKid(coordinator, kids))
    
    # Add recurring chore input helpers
    entities.append(SimpleChoresRecurringTitle(coordinator))
    entities.append(SimpleChoresRecurringPoints(coordinator))
    entities.append(SimpleChoresRecurringKid(coordinator, kids))
    entities.append(SimpleChoresRecurringSchedule(coordinator))
    entities.append(SimpleChoresRecurringDay(coordinator))
    
    add_entities(entities, True)

class SimpleChoresChoreTitle(TextEntity):
    _attr_icon = "mdi:text"
    _attr_native_min = 1
    _attr_native_max = 100
    _attr_mode = "text"

    def __init__(self, coord: SimpleChoresCoordinator):
        self._coord = coord
        self._attr_unique_id = f"{DOMAIN}_chore_title_input"
        self._attr_name = "Chore Title"
        self._attr_native_value = "Enter chore name"

    @property
    def native_value(self) -> str:
        return self._attr_native_value

    async def async_set_value(self, value: str) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()

class SimpleChoresChorePoints(TextEntity):
    _attr_icon = "mdi:star-circle"
    _attr_pattern = r"^\d+$"
    _attr_mode = "text"

    def __init__(self, coord: SimpleChoresCoordinator):
        self._coord = coord
        self._attr_unique_id = f"{DOMAIN}_chore_points_input"
        self._attr_name = "Chore Points"
        self._attr_native_value = "5"

    @property
    def native_value(self) -> str:
        return self._attr_native_value

    async def async_set_value(self, value: str) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()

class SimpleChoresChoreKid(TextEntity):
    _attr_icon = "mdi:account-child"
    _attr_mode = "text"

    def __init__(self, coord: SimpleChoresCoordinator, kids: list[str]):
        self._coord = coord
        self._kids = kids
        self._attr_unique_id = f"{DOMAIN}_chore_kid_input"
        self._attr_name = "Kid"
        self._attr_native_value = kids[0] if kids else "noam"

    @property
    def native_value(self) -> str:
        return self._attr_native_value

    async def async_set_value(self, value: str) -> None:
        if value in self._kids:
            self._attr_native_value = value
            self.async_write_ha_state()

# ---- Recurring Chore Input Entities ----

class SimpleChoresRecurringTitle(TextEntity):
    _attr_icon = "mdi:repeat"
    _attr_native_min = 1
    _attr_native_max = 100
    _attr_mode = "text"

    def __init__(self, coord: SimpleChoresCoordinator):
        self._coord = coord
        self._attr_unique_id = f"{DOMAIN}_recurring_title_input"
        self._attr_name = "Recurring Chore Title"
        self._attr_native_value = "Brush teeth"

    @property
    def native_value(self) -> str:
        return self._attr_native_value

    async def async_set_value(self, value: str) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()

class SimpleChoresRecurringPoints(TextEntity):
    _attr_icon = "mdi:star-circle"
    _attr_pattern = r"^\d+$"
    _attr_mode = "text"

    def __init__(self, coord: SimpleChoresCoordinator):
        self._coord = coord
        self._attr_unique_id = f"{DOMAIN}_recurring_points_input"
        self._attr_name = "Recurring Chore Points"
        self._attr_native_value = "2"

    @property
    def native_value(self) -> str:
        return self._attr_native_value

    async def async_set_value(self, value: str) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()

class SimpleChoresRecurringKid(TextEntity):
    _attr_icon = "mdi:account-child"
    _attr_mode = "text"

    def __init__(self, coord: SimpleChoresCoordinator, kids: list[str]):
        self._coord = coord
        self._kids = kids
        self._attr_unique_id = f"{DOMAIN}_recurring_kid_input"
        self._attr_name = "Recurring Chore Kid"
        self._attr_native_value = kids[0] if kids else "noam"

    @property
    def native_value(self) -> str:
        return self._attr_native_value

    async def async_set_value(self, value: str) -> None:
        if value in self._kids:
            self._attr_native_value = value
            self.async_write_ha_state()

class SimpleChoresRecurringSchedule(TextEntity):
    _attr_icon = "mdi:calendar-clock"
    _attr_mode = "text"

    def __init__(self, coord: SimpleChoresCoordinator):
        self._coord = coord
        self._attr_unique_id = f"{DOMAIN}_recurring_schedule_input"
        self._attr_name = "Schedule Type"
        self._attr_native_value = "daily"

    @property
    def native_value(self) -> str:
        return self._attr_native_value

    async def async_set_value(self, value: str) -> None:
        if value in ["daily", "weekly"]:
            self._attr_native_value = value
            self.async_write_ha_state()

class SimpleChoresRecurringDay(TextEntity):
    _attr_icon = "mdi:calendar-week"
    _attr_pattern = r"^[0-6]$"
    _attr_mode = "text"

    def __init__(self, coord: SimpleChoresCoordinator):
        self._coord = coord
        self._attr_unique_id = f"{DOMAIN}_recurring_day_input"
        self._attr_name = "Day of Week (0=Mon, 6=Sun)"
        self._attr_native_value = "0"

    @property
    def native_value(self) -> str:
        return self._attr_native_value

    async def async_set_value(self, value: str) -> None:
        try:
            day = int(value)
            if 0 <= day <= 6:
                self._attr_native_value = value
                self.async_write_ha_state()
        except ValueError:
            pass