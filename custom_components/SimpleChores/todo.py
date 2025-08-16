"""Todo entities for SimpleChores integration."""
from __future__ import annotations
from typing import List
from homeassistant.components.todo import TodoListEntity, TodoItem, TodoItemStatus, TodoListEntityFeature
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
        self.entity_id = f"todo.{kid_id}_chores"
        # Enable todo features
        self._attr_supported_features = (
            TodoListEntityFeature.CREATE_TODO_ITEM |
            TodoListEntityFeature.UPDATE_TODO_ITEM |
            TodoListEntityFeature.DELETE_TODO_ITEM
        )
        
        # Store reference in coordinator for direct access
        if not hasattr(coord, '_todo_entities'):
            coord._todo_entities = {}
        coord._todo_entities[kid_id] = self
        
        # Add a test item to verify the todo list is working
        import uuid
        test_item = TodoItem(
            summary="Test chore - check if todo list works",
            uid=str(uuid.uuid4()),
            status=TodoItemStatus.NEEDS_ACTION
        )
        self._items.append(test_item)

    async def async_get_items(self):
        """Get todo items - called by Home Assistant."""
        import logging
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.debug(f"SimpleChores: async_get_items called, returning {len(self._items)} items")
        return self._items
    
    async def async_get_todo_items(self):
        """Alternative method name that Home Assistant might call."""
        return await self.async_get_items()
    
    @property
    def todo_items(self) -> List[TodoItem]:
        """Property access to todo items."""
        return self._items

    async def async_create_item(self, item: TodoItem):
        import logging
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.debug(f"SimpleChores: Creating todo item: {item}")
        _LOGGER.debug(f"SimpleChores: Item UID: {getattr(item, 'uid', 'NO_UID')}")
        _LOGGER.debug(f"SimpleChores: Item summary: {getattr(item, 'summary', 'NO_SUMMARY')}")
        _LOGGER.debug(f"SimpleChores: Item status: {getattr(item, 'status', 'NO_STATUS')}")
        
        # Ensure the item has all required properties - create a new item if needed
        if not hasattr(item, 'status') or item.status is None or not hasattr(item, 'uid') or item.uid is None:
            _LOGGER.warning("SimpleChores: Item missing required properties, creating new item")
            import uuid
            
            # Create a properly formed TodoItem
            fixed_item = TodoItem(
                summary=getattr(item, 'summary', 'Unknown chore'),
                uid=getattr(item, 'uid', None) or str(uuid.uuid4()),
                status=getattr(item, 'status', None) or TodoItemStatus.NEEDS_ACTION
            )
            self._items.append(fixed_item)
        else:
            self._items.append(item)
        # Force state update
        self.async_write_ha_state()
        # Also schedule an update
        self.async_schedule_update_ha_state(force_refresh=True)
        _LOGGER.info(f"SimpleChores: Todo item created successfully. Total items: {len(self._items)}")
    
    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a new todo item - this is the method Home Assistant calls."""
        import logging
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.debug(f"SimpleChores: async_create_todo_item called with: {item}")
        await self.async_create_item(item)

    async def async_update_item(self, item: TodoItem):
        import logging
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.debug(f"SimpleChores: Updating todo item: {item}")
        
        for i, old in enumerate(self._items):
            if old.uid == item.uid:
                _LOGGER.debug(f"SimpleChores: Found item to update - old status: {old.status}, new status: {item.status}")
                self._items[i] = item
                # Award points on completion
                if item.status == TodoItemStatus.COMPLETED and old.status != TodoItemStatus.COMPLETED:
                    _LOGGER.info(f"SimpleChores: Item completed: {item.summary}")
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
                            _LOGGER.info(f"SimpleChores: Awarding {pts} points for completed chore")
                            await self._coord.add_points(self._kid_id, pts, f"Chore: {item.summary}", "earn")
                break
        self.async_write_ha_state()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a todo item - this is the method Home Assistant calls."""
        import logging
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.debug(f"SimpleChores: async_update_todo_item called with: {item}")
        _LOGGER.debug(f"SimpleChores: Item type: {type(item)}")
        _LOGGER.debug(f"SimpleChores: Item attributes: {dir(item) if item else 'None'}")
        
        if item is None:
            _LOGGER.error("SimpleChores: Received None item in async_update_todo_item")
            return
            
        try:
            # Log all item properties for debugging
            _LOGGER.debug(f"SimpleChores: Item UID: {getattr(item, 'uid', 'NO_UID')}")
            _LOGGER.debug(f"SimpleChores: Item summary: {getattr(item, 'summary', 'NO_SUMMARY')}")
            _LOGGER.debug(f"SimpleChores: Item status: {getattr(item, 'status', 'NO_STATUS')}")
            
            if not hasattr(item, 'uid') or item.uid is None:
                _LOGGER.error(f"SimpleChores: Item missing UID: {item}")
                return
                
            await self.async_update_item(item)
        except Exception as e:
            _LOGGER.error(f"SimpleChores: Error in async_update_todo_item: {e}")
            import traceback
            _LOGGER.error(f"SimpleChores: Traceback: {traceback.format_exc()}")

    async def async_delete_item(self, uid: str):
        self._items = [i for i in self._items if i.uid != uid]
        self.async_write_ha_state()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete todo items - this is the method Home Assistant calls."""
        for uid in uids:
            await self.async_delete_item(uid)
