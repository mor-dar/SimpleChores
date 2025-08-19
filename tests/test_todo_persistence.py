"""Test todo item persistence across restarts."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock
import uuid

import pytest
import pytest_asyncio
from homeassistant.components.todo import TodoItem, TodoItemStatus

from custom_components.simplechores.coordinator import SimpleChoresCoordinator
from custom_components.simplechores.models import StorageModel, TodoItemModel
from custom_components.simplechores.todo import KidTodoList


class TestTodoPersistence:
    """Test todo item persistence functionality."""

    @pytest.fixture
    def mock_coordinator(self):
        """Return a mock coordinator with persistence methods."""
        coordinator = Mock(spec=SimpleChoresCoordinator)
        coordinator.model = StorageModel()
        coordinator.model.todo_items = []
        coordinator.model.pending_chores = {}
        coordinator.model.pending_approvals = {}
        
        # Mock persistence methods
        coordinator.get_todo_items_for_kid = Mock(return_value=[])
        coordinator.save_todo_item = AsyncMock()
        coordinator.remove_todo_item = AsyncMock()
        coordinator.async_save = AsyncMock()
        
        # Mock approval workflow methods
        coordinator.request_approval = AsyncMock(return_value="approval-123")
        coordinator.get_pending_approvals = Mock(return_value=[])
        coordinator._update_approval_buttons = AsyncMock()
        
        return coordinator

    @pytest.mark.asyncio
    async def test_todo_items_restore_on_startup(self, mock_coordinator):
        """Test that todo items are restored when entity is added to Home Assistant."""
        # Prepare stored items that should be restored
        stored_items = [
            TodoItemModel(
                uid="item-1",
                summary="Stored chore 1 (+10)",
                status="needs_action",
                kid_id="alice"
            ),
            TodoItemModel(
                uid="item-2", 
                summary="Stored chore 2 (+15)",
                status="completed",
                kid_id="alice"
            )
        ]
        mock_coordinator.get_todo_items_for_kid.return_value = stored_items
        
        # Create todo entity
        todo_list = KidTodoList(mock_coordinator, "alice")
        todo_list.hass = Mock()
        todo_list.async_write_ha_state = Mock()
        
        # Simulate startup restoration
        await todo_list.async_added_to_hass()
        
        # Verify items were restored
        items = todo_list.todo_items
        assert len(items) == 2
        
        # Verify item contents
        assert items[0].uid == "item-1"
        assert items[0].summary == "Stored chore 1 (+10)"
        assert items[0].status == TodoItemStatus.NEEDS_ACTION
        
        assert items[1].uid == "item-2"
        assert items[1].summary == "Stored chore 2 (+15)" 
        assert items[1].status == TodoItemStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_todo_item_creation_persists(self, mock_coordinator):
        """Test that creating a todo item saves it to persistent storage."""
        todo_list = KidTodoList(mock_coordinator, "alice")
        todo_list.hass = Mock()
        todo_list.async_write_ha_state = Mock()
        todo_list.async_schedule_update_ha_state = Mock()
        
        # Create a todo item
        test_item = TodoItem(
            summary="New persistent chore (+20)",
            uid=str(uuid.uuid4()),
            status=TodoItemStatus.NEEDS_ACTION
        )
        
        await todo_list.async_create_item(test_item)
        
        # Verify save_todo_item was called with correct parameters
        mock_coordinator.save_todo_item.assert_called_once_with(
            test_item.uid, test_item.summary, "needs_action", "alice"
        )

    @pytest.mark.asyncio 
    async def test_todo_item_update_persists(self, mock_coordinator):
        """Test that updating a todo item saves changes to persistent storage."""
        todo_list = KidTodoList(mock_coordinator, "alice")
        todo_list.hass = Mock()
        todo_list.async_write_ha_state = Mock()
        
        # Set up initial item (without points to avoid approval workflow)
        test_uid = str(uuid.uuid4())
        initial_item = TodoItem(
            summary="Simple chore without points",
            uid=test_uid,
            status=TodoItemStatus.NEEDS_ACTION
        )
        todo_list._items = [initial_item]
        
        # Update the item (simulate completion)
        updated_item = TodoItem(
            summary="Simple chore without points",
            uid=test_uid,
            status=TodoItemStatus.COMPLETED
        )
        
        await todo_list.async_update_item(updated_item)
        
        # Verify save_todo_item was called with updated status
        mock_coordinator.save_todo_item.assert_called_with(
            test_uid, "Simple chore without points", "completed", "alice"
        )

    @pytest.mark.asyncio 
    async def test_todo_item_with_points_triggers_approval_workflow(self, mock_coordinator):
        """Test that completing a todo item with points triggers the approval workflow."""
        todo_list = KidTodoList(mock_coordinator, "alice")
        todo_list.hass = Mock()
        todo_list.async_write_ha_state = Mock()
        
        # Set up initial item with points
        test_uid = str(uuid.uuid4())
        initial_item = TodoItem(
            summary="Chore with points (+10)",
            uid=test_uid,
            status=TodoItemStatus.NEEDS_ACTION
        )
        todo_list._items = [initial_item]
        
        # Update the item (simulate completion)
        updated_item = TodoItem(
            summary="Chore with points (+10)",
            uid=test_uid,
            status=TodoItemStatus.COMPLETED
        )
        
        await todo_list.async_update_item(updated_item)
        
        # Verify that the approval workflow was triggered
        # The item should be saved with the [PENDING APPROVAL] tag and needs_action status
        mock_coordinator.save_todo_item.assert_called_with(
            test_uid, "[PENDING APPROVAL] Chore with points (+10)", "needs_action", "alice"
        )
        
        # Verify that an approval was created
        assert len(mock_coordinator.model.pending_approvals) == 1

    @pytest.mark.asyncio
    async def test_todo_item_deletion_persists(self, mock_coordinator):
        """Test that deleting a todo item removes it from persistent storage."""
        todo_list = KidTodoList(mock_coordinator, "alice")
        todo_list.hass = Mock()
        todo_list.async_write_ha_state = Mock()
        
        # Set up initial item
        test_uid = str(uuid.uuid4())
        initial_item = TodoItem(
            summary="Item to delete (+5)",
            uid=test_uid,
            status=TodoItemStatus.NEEDS_ACTION
        )
        todo_list._items = [initial_item]
        
        # Delete the item
        await todo_list.async_delete_item(test_uid)
        
        # Verify remove_todo_item was called
        mock_coordinator.remove_todo_item.assert_called_once_with(test_uid)
        
        # Verify item was removed from local list
        assert len(todo_list._items) == 0

    @pytest.mark.asyncio
    async def test_persistence_across_simulated_restart(self, mock_coordinator):
        """Test complete persistence workflow simulating a restart."""
        # === BEFORE RESTART: Create and save items ===
        todo_list_1 = KidTodoList(mock_coordinator, "alice")
        todo_list_1.hass = Mock()
        todo_list_1.async_write_ha_state = Mock()
        todo_list_1.async_schedule_update_ha_state = Mock()
        
        # Create items
        item1_uid = str(uuid.uuid4())
        item2_uid = str(uuid.uuid4())
        
        item1 = TodoItem(
            summary="Persistent chore 1 (+10)",
            uid=item1_uid,
            status=TodoItemStatus.NEEDS_ACTION
        )
        item2 = TodoItem(
            summary="Persistent chore 2 (+15)", 
            uid=item2_uid,
            status=TodoItemStatus.COMPLETED
        )
        
        await todo_list_1.async_create_item(item1)
        await todo_list_1.async_create_item(item2)
        
        # Verify persistence calls were made
        assert mock_coordinator.save_todo_item.call_count == 2
        
        # === SIMULATE RESTART: Prepare coordinator with "stored" data ===
        stored_items = [
            TodoItemModel(
                uid=item1_uid,
                summary="Persistent chore 1 (+10)",
                status="needs_action", 
                kid_id="alice"
            ),
            TodoItemModel(
                uid=item2_uid,
                summary="Persistent chore 2 (+15)",
                status="completed",
                kid_id="alice"
            )
        ]
        mock_coordinator.get_todo_items_for_kid.return_value = stored_items
        
        # === AFTER RESTART: Create new todo entity and restore ===
        todo_list_2 = KidTodoList(mock_coordinator, "alice")
        todo_list_2.hass = Mock()
        todo_list_2.async_write_ha_state = Mock()
        
        # Simulate entity being added after restart
        await todo_list_2.async_added_to_hass()
        
        # Verify items were restored
        restored_items = todo_list_2.todo_items
        assert len(restored_items) == 2
        
        # Verify restored item details
        restored_uids = [item.uid for item in restored_items]
        assert item1_uid in restored_uids
        assert item2_uid in restored_uids
        
        # Find and verify each item
        item1_restored = next(item for item in restored_items if item.uid == item1_uid)
        item2_restored = next(item for item in restored_items if item.uid == item2_uid)
        
        assert item1_restored.summary == "Persistent chore 1 (+10)"
        assert item1_restored.status == TodoItemStatus.NEEDS_ACTION
        
        assert item2_restored.summary == "Persistent chore 2 (+15)"
        assert item2_restored.status == TodoItemStatus.COMPLETED