"""Number entities for SimpleChores integration."""
from __future__ import annotations
from homeassistant.components.number import NumberEntity
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
        await coordinator.ensure_kid(kid, kid.capitalize())
        entities.append(SimpleChoresNumber(coordinator, kid))
    add_entities(entities, True)

class SimpleChoresNumber(NumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 99999
    _attr_native_step = 1

    def __init__(self, coord: SimpleChoresCoordinator, kid_id: str):
        self._coord = coord
        self._kid_id = kid_id
        self._attr_unique_id = f"{DOMAIN}_{kid_id}_points"
        self._attr_name = f"{kid_id.capitalize()} Points"

    @property
    def native_value(self) -> float | None:
        return float(self._coord.get_points(self._kid_id))

    async def async_set_native_value(self, value: float) -> None:
        current = self._coord.get_points(self._kid_id)
        delta = int(value) - current
        if delta != 0:
            if delta > 0:
                await self._coord.add_points(self._kid_id, delta, "Manual adjust", "adjust")
            else:
                await self._coord.remove_points(self._kid_id, -delta, "Manual adjust", "adjust")
        self.async_write_ha_state()
