"""Todo entities for SimpleChores integration."""
from __future__ import annotations

from datetime import datetime
import uuid

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity, TodoListEntityFeature
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
        self._items: list[TodoItem] = []
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

    async def async_added_to_hass(self):
        """Called when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        # Restore todo items from persistent storage
        await self._restore_todo_items()

    async def _restore_todo_items(self):
        """Restore todo items from coordinator storage"""
        import logging
        _LOGGER = logging.getLogger(__name__)
        
        stored_items = self._coord.get_todo_items_for_kid(self._kid_id)
        _LOGGER.info(f"SimpleChores: Restoring {len(stored_items)} todo items for {self._kid_id}")
        
        self._items = []
        for stored_item in stored_items:
            # Convert stored status back to enum
            status = TodoItemStatus.COMPLETED if stored_item.status == "completed" else TodoItemStatus.NEEDS_ACTION
            
            todo_item = TodoItem(
                summary=stored_item.summary,
                uid=stored_item.uid,
                status=status
            )
            self._items.append(todo_item)
            
        _LOGGER.info(f"SimpleChores: Restored {len(self._items)} todo items for {self._kid_id}")

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
    def todo_items(self) -> list[TodoItem]:
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
            item = fixed_item
        else:
            self._items.append(item)
            
        # Save to persistent storage
        status_str = "completed" if item.status == TodoItemStatus.COMPLETED else "needs_action"
        await self._coord.save_todo_item(item.uid, item.summary, status_str, self._kid_id)
        
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

        handled_approval_logic = False
        for i, old in enumerate(self._items):
            if old.uid == item.uid:
                _LOGGER.debug(
                    f"SimpleChores: Found item to update - old status: {old.status}, new status: {item.status}"
                )
                # Handle chore completion with approval workflow
                if item.status == TodoItemStatus.COMPLETED and old.status != TodoItemStatus.COMPLETED:
                    _LOGGER.info(f"SimpleChores: Item completed: {item.summary}")

                    # Check if this already has pending approval tag - don't reprocess
                    if "[PENDING APPROVAL]" in item.summary:
                        _LOGGER.info(f"SimpleChores: Item already pending approval, skipping: {item.summary}")
                        # Reset status back to needs action to show pending state
                        item.status = TodoItemStatus.NEEDS_ACTION
                        self._items[i] = item
                        continue

                    # Check if this is a tracked chore that needs approval
                    if item.uid in self._coord.model.pending_chores:
                        _LOGGER.info(f"SimpleChores: Requesting approval for tracked chore: {item.uid}")
                        approval_id = await self._coord.request_approval(item.uid)
                        if approval_id:
                            # Update item summary to show pending approval AND reset status
                            item.summary = f"[PENDING APPROVAL] {item.summary}"
                            item.status = TodoItemStatus.NEEDS_ACTION  # Reset to uncompleted
                            _LOGGER.info(f"SimpleChores: Chore moved to approval queue: {approval_id}")
                            handled_approval_logic = True
                    else:
                        # Fallback: try to parse "(+X)" from summary for manual chores
                        # These also go through approval workflow
                        pts = 0
                        if item.summary and "(+" in item.summary and ")" in item.summary:
                            try:
                                pts = int(item.summary.split("(+")[1].split(")")[0])
                            except Exception:
                                pts = 0

                        if pts:
                            _LOGGER.info("SimpleChores: Manual chore completed, requesting approval")
                            # Create a pending approval for manual chores too
                            approval_id = str(uuid.uuid4())[:8]
                            from .models import PendingApproval
                            approval = PendingApproval(
                                id=approval_id,
                                todo_uid=item.uid,
                                kid_id=self._kid_id,
                                title=item.summary,
                                points=pts,
                                completed_ts=datetime.now().timestamp()
                            )
                            self._coord.model.pending_approvals[approval_id] = approval
                            await self._coord.async_save()

                            # Update approval buttons
                            await self._coord._update_approval_buttons()

                            # Update item summary to show pending approval AND reset status
                            item.summary = f"[PENDING APPROVAL] {item.summary}"
                            item.status = TodoItemStatus.NEEDS_ACTION  # Reset to uncompleted
                            _LOGGER.info(f"SimpleChores: Manual chore moved to approval queue: {approval_id}")

                            # Debug: Check pending approvals
                            pending_count = len(self._coord.get_pending_approvals())
                            _LOGGER.info(f"SimpleChores: Total pending approvals after creation: {pending_count}")
                            handled_approval_logic = True

                # Handle removing pending approval status (unchecking or de-selecting)
                # Case 1: Unchecking - transitioning from completed to needs_action
                # Case 2: De-selecting - user manually removed the [PENDING APPROVAL] tag
                elif (item.status == TodoItemStatus.NEEDS_ACTION and 
                      ("[PENDING APPROVAL]" in item.summary or "[PENDING APPROVAL]" in old.summary)):
                    
                    should_clear_approval = False
                    log_message = ""
                    
                    # Case 1: Unchecking a completed item with pending approval
                    if old.status == TodoItemStatus.COMPLETED and "[PENDING APPROVAL]" in item.summary:
                        should_clear_approval = True
                        log_message = f"Unchecking pending approval item: {item.summary}"
                        # Remove the pending approval tag
                        item.summary = item.summary.replace("[PENDING APPROVAL] ", "")
                    
                    # Case 2: De-selecting by removing the tag (no status change)
                    elif (old.status == TodoItemStatus.NEEDS_ACTION and 
                          "[PENDING APPROVAL]" in old.summary and 
                          "[PENDING APPROVAL]" not in item.summary):
                        should_clear_approval = True
                        log_message = f"De-selecting pending item by tag removal: {old.summary} -> {item.summary}"
                    
                    if should_clear_approval:
                        _LOGGER.info(f"SimpleChores: {log_message}")
                        
                        # Remove from pending approvals
                        approvals_to_remove = []
                        for approval_id, approval in self._coord.model.pending_approvals.items():
                            if approval.todo_uid == item.uid and approval.status == "pending_approval":
                                approvals_to_remove.append(approval_id)

                        for approval_id in approvals_to_remove:
                            del self._coord.model.pending_approvals[approval_id]
                            _LOGGER.info(f"SimpleChores: Removed pending approval: {approval_id}")

                        # Reset chore status if it exists
                        if item.uid in self._coord.model.pending_chores:
                            self._coord.model.pending_chores[item.uid].status = "pending"
                            self._coord.model.pending_chores[item.uid].completed_ts = None

                        # Always save and update UI when clearing approval state
                        await self._coord.async_save()
                        await self._coord._update_approval_buttons()

                        _LOGGER.info(f"SimpleChores: Cleared pending approval for item: {item.summary}")
                        handled_approval_logic = True

                # Update the item in the list after all modifications
                self._items[i] = item
                break
                
        # Save updated todo items to persistent storage
        status_str = "completed" if item.status == TodoItemStatus.COMPLETED else "needs_action"
        # Save todo item changes, skip coordinator save if approval logic already handled it
        skip_save = handled_approval_logic
        await self._coord.save_todo_item(item.uid, item.summary, status_str, self._kid_id, skip_save=skip_save)
        
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
        import logging
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.debug(f"SimpleChores: Deleting todo item: {uid}")

        # Remove the item from the todo list
        self._items = [i for i in self._items if i.uid != uid]

        # Clean up associated pending chore data
        removed_pending_chore = False
        if uid in self._coord.model.pending_chores:
            _LOGGER.info(f"SimpleChores: Removing pending chore for deleted item: {uid}")
            del self._coord.model.pending_chores[uid]
            removed_pending_chore = True

        # Clean up any associated pending approvals
        approvals_to_remove = []
        for approval_id, approval in self._coord.model.pending_approvals.items():
            if approval.todo_uid == uid:
                approvals_to_remove.append(approval_id)

        for approval_id in approvals_to_remove:
            _LOGGER.info(f"SimpleChores: Removing pending approval for deleted item: {approval_id}")
            del self._coord.model.pending_approvals[approval_id]

        # Save the updated coordinator state if we removed any data
        if removed_pending_chore or approvals_to_remove:
            await self._coord.async_save()
            # Update approval buttons if any approvals were removed
            if approvals_to_remove:
                await self._coord._update_approval_buttons()

        # Remove from persistent todo storage
        await self._coord.remove_todo_item(uid)

        self.async_write_ha_state()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete todo items - this is the method Home Assistant calls."""
        for uid in uids:
            await self.async_delete_item(uid)
