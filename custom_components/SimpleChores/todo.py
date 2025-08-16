"""Todo entities for SimpleChores integration."""
from __future__ import annotations
from typing import List
from homeassistant.components.todo import TodoListEntity, TodoItem, TodoItemStatus
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .coordinator import SimpleChoresCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add_entities: AddEntitiesCallback):
    if not entry.data.get("use_todo", True):
        return
    coordinator: SimpleChoresCoordinator = hass.data[DOMAIN][entry.entry_id]
    kids_csv = entry.data.get("kids", "alex,emma")
    kids = [k.strip() for k in kids_csv.split(",") if k.strip()]
    add_entities([KidTodoList(coordinator, kid) for kid in kids], True)

class KidTodoList(TodoListEntity):
    def __init__(self, coord: SimpleChoresCoordinator, kid_id: str):
        self._coord = coord
        self._kid_id = kid_id
        self._items: List[TodoItem] = []
        self._attr_name = f"{kid_id.capitalize()} Chores"
        self._attr_unique_id = f"simplechores_todo_{kid_id}"

    async def async_get_items(self):
        return self._items

    async def async_create_item(self, item: TodoItem):
        self._items.append(item)
        self.async_write_ha_state()

    async def async_update_item(self, item: TodoItem):
        for i, old in enumerate(self._items):
            if old.uid == item.uid:
                self._items[i] = item
                # Award points on completion
                if item.status == TodoItemStatus.COMPLETED and old.status != TodoItemStatus.COMPLETED:
                    # First try to complete by UID (for tracked chores)
                    success = await self._coord.complete_chore_by_uid(item.uid)
                    
                    if not success:
                        # Fallback: try to parse "(+X)" from summary for manual chores
                        pts = 0
                        if item.summary and "(+" in item.summary and ")" in item.summary:
                            try:
                                pts = int(item.summary.split("(+")[1].split(")")[0])
                            except Exception:
                                pts = 0
                        if pts:
                            await self._coord.add_points(self._kid_id, pts, f"Chore: {item.summary}", "earn")
                break
        self.async_write_ha_state()

    async def async_delete_item(self, uid: str):
        self._items = [i for i in self._items if i.uid != uid]
        self.async_write_ha_state()
