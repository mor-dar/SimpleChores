"""Comprehensive tests for todo platform functionality."""
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
import uuid

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntityFeature
import pytest

from custom_components.simplechores.models import PendingApproval, PendingChore
from custom_components.simplechores.todo import KidTodoList, async_setup_entry


class TestKidTodoListInitialization:
    """Test todo list entity initialization."""

    @pytest.fixture
    def todo_list(self, coordinator):
        return KidTodoList(coordinator, "alice")

    def test_todo_list_properties(self, todo_list):
        """Test basic todo list properties."""
        assert todo_list._attr_name == "Alice Chores"
        assert todo_list._attr_unique_id == "simplechores_todo_alice"
        assert todo_list.entity_id == "todo.alice_chores"
        assert todo_list._kid_id == "alice"

    def test_todo_list_features(self, todo_list):
        """Test supported features."""
        expected_features = (
            TodoListEntityFeature.CREATE_TODO_ITEM |
            TodoListEntityFeature.UPDATE_TODO_ITEM |
            TodoListEntityFeature.DELETE_TODO_ITEM
        )
        assert todo_list._attr_supported_features == expected_features

    def test_coordinator_registration(self, coordinator):
        """Test that todo list registers with coordinator."""
        todo_list = KidTodoList(coordinator, "bob")

        assert hasattr(coordinator, "_todo_entities")
        assert "bob" in coordinator._todo_entities
        assert coordinator._todo_entities["bob"] is todo_list

    def test_initial_test_item(self, todo_list):
        """Test that initial test item is created."""
        assert len(todo_list._items) == 1
        test_item = todo_list._items[0]
        assert "Test chore" in test_item.summary
        assert test_item.status == TodoItemStatus.NEEDS_ACTION
        assert test_item.uid is not None


class TestTodoItemCreation:
    """Test todo item creation functionality."""

    @pytest.fixture
    def todo_list(self, coordinator):
        todo_list = KidTodoList(coordinator, "alice")
        # Clear initial test item for clean tests
        todo_list._items = []
        return todo_list

    @pytest.mark.asyncio
    async def test_async_create_item_valid(self, todo_list):
        """Test creating valid todo item."""
        todo_list.async_write_ha_state = Mock()
        todo_list.async_schedule_update_ha_state = Mock()

        item = TodoItem(
            summary="Clean room",
            uid=str(uuid.uuid4()),
            status=TodoItemStatus.NEEDS_ACTION
        )

        await todo_list.async_create_item(item)

        assert len(todo_list._items) == 1
        assert todo_list._items[0].summary == "Clean room"
        assert todo_list._items[0].status == TodoItemStatus.NEEDS_ACTION

        # Should trigger state updates
        todo_list.async_write_ha_state.assert_called_once()
        todo_list.async_schedule_update_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_create_item_missing_properties(self, todo_list):
        """Test creating item with missing required properties."""
        todo_list.async_write_ha_state = Mock()
        todo_list.async_schedule_update_ha_state = Mock()

        # Create item with missing properties
        item = Mock()
        item.summary = "Incomplete item"
        # Missing uid and status

        with patch('custom_components.simplechores.todo._LOGGER') as mock_logger:
            await todo_list.async_create_item(item)

            # Should log warning and create fixed item
            mock_logger.warning.assert_called()

            # Should still add item with fixed properties
            assert len(todo_list._items) == 1
            created_item = todo_list._items[0]
            assert created_item.summary == "Incomplete item"
            assert created_item.uid is not None
            assert created_item.status == TodoItemStatus.NEEDS_ACTION

    @pytest.mark.asyncio
    async def test_async_create_todo_item_wrapper(self, todo_list):
        """Test the Home Assistant wrapper method."""
        todo_list.async_create_item = AsyncMock()

        item = TodoItem(
            summary="Test wrapper",
            uid=str(uuid.uuid4()),
            status=TodoItemStatus.NEEDS_ACTION
        )

        await todo_list.async_create_todo_item(item)

        # Should delegate to async_create_item
        todo_list.async_create_item.assert_called_once_with(item)


class TestTodoItemUpdates:
    """Test todo item update functionality."""

    @pytest.fixture
    def todo_list_with_items(self, coordinator):
        todo_list = KidTodoList(coordinator, "alice")
        todo_list._items = []

        # Add test items
        test_items = [
            TodoItem(
                summary="Tracked chore (+5)",
                uid="tracked_uid",
                status=TodoItemStatus.NEEDS_ACTION
            ),
            TodoItem(
                summary="Manual chore (+3)",
                uid="manual_uid",
                status=TodoItemStatus.NEEDS_ACTION
            ),
            TodoItem(
                summary="[PENDING APPROVAL] Approved chore (+2)",
                uid="pending_uid",
                status=TodoItemStatus.NEEDS_ACTION
            )
        ]
        todo_list._items.extend(test_items)

        # Add corresponding pending chore for tracked item
        coordinator.model.pending_chores = {
            "tracked_uid": PendingChore(
                todo_uid="tracked_uid",
                kid_id="alice",
                title="Tracked chore",
                points=5,
                created_ts=datetime.now().timestamp(),
                status="pending"
            )
        }

        return todo_list

    @pytest.mark.asyncio
    async def test_complete_tracked_chore_with_approval(self, todo_list_with_items, coordinator):
        """Test completing tracked chore that needs approval."""
        todo_list = todo_list_with_items
        todo_list.async_write_ha_state = Mock()

        # Mock coordinator methods
        coordinator.request_approval = AsyncMock(return_value="approval123")

        # Update tracked item to completed
        updated_item = TodoItem(
            summary="Tracked chore (+5)",
            uid="tracked_uid",
            status=TodoItemStatus.COMPLETED
        )

        with patch('custom_components.simplechores.todo._LOGGER'):
            await todo_list.async_update_item(updated_item)

            # Should request approval
            coordinator.request_approval.assert_called_once_with("tracked_uid")

            # Should update item summary and reset status
            found_item = next(item for item in todo_list._items if item.uid == "tracked_uid")
            assert "[PENDING APPROVAL]" in found_item.summary
            assert found_item.status == TodoItemStatus.NEEDS_ACTION

    @pytest.mark.asyncio
    async def test_complete_manual_chore_with_points(self, todo_list_with_items, coordinator):
        """Test completing manual chore with points in summary."""
        todo_list = todo_list_with_items
        todo_list.async_write_ha_state = Mock()

        # Mock coordinator methods
        coordinator.async_save = AsyncMock()
        coordinator._update_approval_buttons = AsyncMock()
        coordinator.get_pending_approvals = Mock(return_value=[])

        # Update manual item to completed
        updated_item = TodoItem(
            summary="Manual chore (+3)",
            uid="manual_uid",
            status=TodoItemStatus.COMPLETED
        )

        with patch('custom_components.simplechores.todo._LOGGER'):
            await todo_list.async_update_item(updated_item)

            # Should create pending approval for manual chore
            assert len(coordinator.model.pending_approvals) == 1
            approval = list(coordinator.model.pending_approvals.values())[0]
            assert approval.kid_id == "alice"
            assert approval.points == 3
            assert approval.todo_uid == "manual_uid"

            # Should update item summary and reset status
            found_item = next(item for item in todo_list._items if item.uid == "manual_uid")
            assert "[PENDING APPROVAL]" in found_item.summary
            assert found_item.status == TodoItemStatus.NEEDS_ACTION

            # Should save and update buttons
            coordinator.async_save.assert_called_once()
            coordinator._update_approval_buttons.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_already_pending_approval(self, todo_list_with_items):
        """Test completing item that already has pending approval tag."""
        todo_list = todo_list_with_items
        todo_list.async_write_ha_state = Mock()

        # Update pending approval item to completed (should be ignored)
        updated_item = TodoItem(
            summary="[PENDING APPROVAL] Approved chore (+2)",
            uid="pending_uid",
            status=TodoItemStatus.COMPLETED
        )

        with patch('custom_components.simplechores.todo._LOGGER') as mock_logger:
            await todo_list.async_update_item(updated_item)

            # Should log skip message and reset status
            mock_logger.info.assert_called_with(
                "SimpleChores: Item already pending approval, skipping: [PENDING APPROVAL] Approved chore (+2)"
            )

            # Should reset status back to needs action
            found_item = next(item for item in todo_list._items if item.uid == "pending_uid")
            assert found_item.status == TodoItemStatus.NEEDS_ACTION

    @pytest.mark.asyncio
    async def test_uncheck_pending_approval_item(self, todo_list_with_items, coordinator):
        """Test unchecking (undoing) pending approval item."""
        todo_list = todo_list_with_items
        todo_list.async_write_ha_state = Mock()

        # Add pending approval to coordinator
        coordinator.model.pending_approvals = {
            "approval123": PendingApproval(
                id="approval123",
                todo_uid="pending_uid",
                kid_id="alice",
                title="Approved chore",
                points=2,
                completed_ts=datetime.now().timestamp(),
                status="pending_approval"
            )
        }
        coordinator.async_save = AsyncMock()
        coordinator._update_approval_buttons = AsyncMock()

        # Uncheck the pending approval item (completed -> needs_action)
        updated_item = TodoItem(
            summary="[PENDING APPROVAL] Approved chore (+2)",
            uid="pending_uid",
            status=TodoItemStatus.NEEDS_ACTION
        )

        # Simulate old status as completed
        todo_list._items[2].status = TodoItemStatus.COMPLETED

        await todo_list.async_update_item(updated_item)

        # Should remove pending approval tag
        found_item = next(item for item in todo_list._items if item.uid == "pending_uid")
        assert "[PENDING APPROVAL]" not in found_item.summary
        assert "Approved chore (+2)" in found_item.summary

        # Should remove from pending approvals
        assert "approval123" not in coordinator.model.pending_approvals

        # Should reset chore status if it exists
        if "pending_uid" in coordinator.model.pending_chores:
            assert coordinator.model.pending_chores["pending_uid"].status == "pending"

        # Should save and update buttons
        coordinator.async_save.assert_called_once()
        coordinator._update_approval_buttons.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_nonexistent_item(self, todo_list_with_items):
        """Test updating item that doesn't exist in list."""
        todo_list = todo_list_with_items
        todo_list.async_write_ha_state = Mock()

        # Try to update item that doesn't exist
        nonexistent_item = TodoItem(
            summary="Nonexistent",
            uid="nonexistent_uid",
            status=TodoItemStatus.COMPLETED
        )

        await todo_list.async_update_item(nonexistent_item)

        # Should not change anything
        assert len(todo_list._items) == 3
        todo_list.async_write_ha_state.assert_called_once()  # Still called at end

    @pytest.mark.asyncio
    async def test_async_update_todo_item_wrapper_none(self, todo_list_with_items):
        """Test wrapper method with None item."""
        todo_list = todo_list_with_items

        with patch('custom_components.simplechores.todo._LOGGER') as mock_logger:
            await todo_list.async_update_todo_item(None)

            # Should log error and return early
            mock_logger.error.assert_called_with(
                "SimpleChores: Received None item in async_update_todo_item"
            )

    @pytest.mark.asyncio
    async def test_async_update_todo_item_wrapper_missing_uid(self, todo_list_with_items):
        """Test wrapper method with item missing UID."""
        todo_list = todo_list_with_items

        # Create item without UID
        item_without_uid = Mock()
        item_without_uid.summary = "No UID item"
        # Missing uid attribute

        with patch('custom_components.simplechores.todo._LOGGER') as mock_logger:
            await todo_list.async_update_todo_item(item_without_uid)

            # Should log error about missing UID
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_async_update_todo_item_wrapper_exception(self, todo_list_with_items):
        """Test wrapper method exception handling."""
        todo_list = todo_list_with_items
        todo_list.async_update_item = AsyncMock(side_effect=Exception("Test error"))

        item = TodoItem(
            summary="Test item",
            uid="test_uid",
            status=TodoItemStatus.COMPLETED
        )

        with patch('custom_components.simplechores.todo._LOGGER') as mock_logger:
            await todo_list.async_update_todo_item(item)

            # Should log the exception
            mock_logger.error.assert_called()
            assert "Error in async_update_todo_item" in str(mock_logger.error.call_args)


class TestTodoItemDeletion:
    """Test todo item deletion functionality."""

    @pytest.fixture
    def todo_list_with_items(self, coordinator):
        todo_list = KidTodoList(coordinator, "alice")
        todo_list._items = [
            TodoItem(summary="Item 1", uid="uid1", status=TodoItemStatus.NEEDS_ACTION),
            TodoItem(summary="Item 2", uid="uid2", status=TodoItemStatus.NEEDS_ACTION),
            TodoItem(summary="Item 3", uid="uid3", status=TodoItemStatus.COMPLETED)
        ]
        return todo_list

    @pytest.mark.asyncio
    async def test_async_delete_item(self, todo_list_with_items):
        """Test deleting single item."""
        todo_list = todo_list_with_items
        todo_list.async_write_ha_state = Mock()

        await todo_list.async_delete_item("uid2")

        # Should remove item with uid2
        assert len(todo_list._items) == 2
        remaining_uids = [item.uid for item in todo_list._items]
        assert "uid1" in remaining_uids
        assert "uid3" in remaining_uids
        assert "uid2" not in remaining_uids

        todo_list.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_delete_nonexistent_item(self, todo_list_with_items):
        """Test deleting item that doesn't exist."""
        todo_list = todo_list_with_items
        todo_list.async_write_ha_state = Mock()

        await todo_list.async_delete_item("nonexistent")

        # Should not change anything
        assert len(todo_list._items) == 3
        todo_list.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_delete_todo_items_wrapper(self, todo_list_with_items):
        """Test the Home Assistant wrapper method for multiple deletions."""
        todo_list = todo_list_with_items
        todo_list.async_delete_item = AsyncMock()

        uids_to_delete = ["uid1", "uid3"]
        await todo_list.async_delete_todo_items(uids_to_delete)

        # Should call async_delete_item for each UID
        assert todo_list.async_delete_item.call_count == 2
        todo_list.async_delete_item.assert_any_call("uid1")
        todo_list.async_delete_item.assert_any_call("uid3")


class TestTodoItemRetrieval:
    """Test todo item retrieval methods."""

    @pytest.fixture
    def todo_list_with_items(self, coordinator):
        todo_list = KidTodoList(coordinator, "alice")
        todo_list._items = [
            TodoItem(summary="Item 1", uid="uid1", status=TodoItemStatus.NEEDS_ACTION),
            TodoItem(summary="Item 2", uid="uid2", status=TodoItemStatus.COMPLETED)
        ]
        return todo_list

    @pytest.mark.asyncio
    async def test_async_get_items(self, todo_list_with_items):
        """Test getting all items."""
        todo_list = todo_list_with_items

        with patch('custom_components.simplechores.todo._LOGGER') as mock_logger:
            items = await todo_list.async_get_items()

            assert len(items) == 2
            assert items == todo_list._items

            # Should log debug information
            mock_logger.debug.assert_called()

    @pytest.mark.asyncio
    async def test_async_get_todo_items_wrapper(self, todo_list_with_items):
        """Test the alternative method name."""
        todo_list = todo_list_with_items
        todo_list.async_get_items = AsyncMock(return_value=["test"])

        result = await todo_list.async_get_todo_items()

        # Should delegate to async_get_items
        todo_list.async_get_items.assert_called_once()
        assert result == ["test"]

    def test_todo_items_property(self, todo_list_with_items):
        """Test property access to todo items."""
        todo_list = todo_list_with_items

        items = todo_list.todo_items

        assert len(items) == 2
        assert items == todo_list._items


class TestTodoSetupEntry:
    """Test todo platform setup."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_todo_enabled(self, mock_hass, coordinator):
        """Test setup when todo is enabled."""
        config_entry = Mock()
        config_entry.data = {"use_todo": True, "kids": "alice,bob,charlie"}

        add_entities = Mock()

        await async_setup_entry(mock_hass, config_entry, add_entities)

        # Should create todo entities for all kids
        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]

        assert len(entities) == 3
        entity_names = [entity._attr_name for entity in entities]
        assert "Alice Chores" in entity_names
        assert "Bob Chores" in entity_names
        assert "Charlie Chores" in entity_names

    @pytest.mark.asyncio
    async def test_async_setup_entry_with_todo_disabled(self, mock_hass, coordinator):
        """Test setup when todo is disabled."""
        config_entry = Mock()
        config_entry.data = {"use_todo": False, "kids": "alice,bob"}

        add_entities = Mock()

        await async_setup_entry(mock_hass, config_entry, add_entities)

        # Should not create any entities
        add_entities.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_setup_entry_default_kids(self, mock_hass, coordinator):
        """Test setup with default kids configuration."""
        config_entry = Mock()
        config_entry.data = {}  # No kids specified, should use default

        add_entities = Mock()

        await async_setup_entry(mock_hass, config_entry, add_entities)

        # Should use default kids (alex,emma)
        entities = add_entities.call_args[0][0]
        assert len(entities) == 2
        entity_names = [entity._attr_name for entity in entities]
        assert "Alex Chores" in entity_names
        assert "Emma Chores" in entity_names

    @pytest.mark.asyncio
    async def test_async_setup_entry_empty_kids_list(self, mock_hass, coordinator):
        """Test setup with empty kids list."""
        config_entry = Mock()
        config_entry.data = {"kids": "  ,  ,  "}  # Empty after stripping

        add_entities = Mock()

        await async_setup_entry(mock_hass, config_entry, add_entities)

        # Should not create any entities for empty kids
        entities = add_entities.call_args[0][0]
        assert len(entities) == 0


class TestTodoItemDeletionWithPendingData:
    """Test todo item deletion with pending chore and approval cleanup."""

    @pytest.fixture
    def todo_list_with_pending_data(self, coordinator):
        """Create todo list with pending chore and approval data."""
        todo_list = KidTodoList(coordinator, "alice")

        # Add some todo items
        todo_list._items = [
            TodoItem(summary="Regular chore", uid="regular-uid", status=TodoItemStatus.NEEDS_ACTION),
            TodoItem(summary="Pending chore", uid="pending-uid", status=TodoItemStatus.NEEDS_ACTION),
            TodoItem(summary="Approval chore", uid="approval-uid", status=TodoItemStatus.NEEDS_ACTION),
        ]

        # Add pending chore data for some items
        coordinator.model.pending_chores["pending-uid"] = PendingChore(
            todo_uid="pending-uid",
            kid_id="alice",
            title="Pending chore",
            points=10,
            created_ts=datetime.now().timestamp(),
            status="pending"
        )

        # Add pending approval data
        coordinator.model.pending_approvals["approval-123"] = PendingApproval(
            id="approval-123",
            todo_uid="approval-uid",
            kid_id="alice",
            title="Approval chore",
            points=15,
            completed_ts=datetime.now().timestamp(),
            status="pending_approval"
        )

        return todo_list

    @pytest.mark.asyncio
    async def test_delete_regular_item_no_cleanup(self, todo_list_with_pending_data):
        """Test deleting regular item without pending data."""
        todo_list = todo_list_with_pending_data
        coordinator = todo_list._coord

        # Mock methods
        todo_list.async_write_ha_state = Mock()
        coordinator.async_save = AsyncMock()
        coordinator._update_approval_buttons = AsyncMock()

        await todo_list.async_delete_item("regular-uid")

        # Should remove item from list
        assert len(todo_list._items) == 2
        remaining_uids = [item.uid for item in todo_list._items]
        assert "regular-uid" not in remaining_uids

        # Should not affect pending data
        assert "pending-uid" in coordinator.model.pending_chores
        assert "approval-123" in coordinator.model.pending_approvals

        # Should not save coordinator or update buttons (no cleanup needed)
        coordinator.async_save.assert_not_called()
        coordinator._update_approval_buttons.assert_not_called()
        todo_list.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_item_with_pending_chore(self, todo_list_with_pending_data):
        """Test deleting item with associated pending chore."""
        todo_list = todo_list_with_pending_data
        coordinator = todo_list._coord

        # Mock methods
        todo_list.async_write_ha_state = Mock()
        coordinator.async_save = AsyncMock()
        coordinator._update_approval_buttons = AsyncMock()

        await todo_list.async_delete_item("pending-uid")

        # Should remove item from list
        assert len(todo_list._items) == 2
        remaining_uids = [item.uid for item in todo_list._items]
        assert "pending-uid" not in remaining_uids

        # Should remove pending chore
        assert "pending-uid" not in coordinator.model.pending_chores

        # Should not affect other pending data
        assert "approval-123" in coordinator.model.pending_approvals

        # Should save coordinator state
        coordinator.async_save.assert_called_once()
        coordinator._update_approval_buttons.assert_not_called()  # No approvals removed
        todo_list.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_item_with_pending_approval(self, todo_list_with_pending_data):
        """Test deleting item with associated pending approval."""
        todo_list = todo_list_with_pending_data
        coordinator = todo_list._coord

        # Mock methods
        todo_list.async_write_ha_state = Mock()
        coordinator.async_save = AsyncMock()
        coordinator._update_approval_buttons = AsyncMock()

        await todo_list.async_delete_item("approval-uid")

        # Should remove item from list
        assert len(todo_list._items) == 2
        remaining_uids = [item.uid for item in todo_list._items]
        assert "approval-uid" not in remaining_uids

        # Should remove pending approval
        assert "approval-123" not in coordinator.model.pending_approvals

        # Should not affect other pending data
        assert "pending-uid" in coordinator.model.pending_chores

        # Should save coordinator state and update approval buttons
        coordinator.async_save.assert_called_once()
        coordinator._update_approval_buttons.assert_called_once()
        todo_list.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_item_with_both_pending_data(self, todo_list_with_pending_data):
        """Test deleting item with both pending chore and approval."""
        todo_list = todo_list_with_pending_data
        coordinator = todo_list._coord

        # Add both types of data for the same item
        coordinator.model.pending_chores["approval-uid"] = PendingChore(
            todo_uid="approval-uid",
            kid_id="alice",
            title="Both types chore",
            points=20,
            created_ts=datetime.now().timestamp(),
            status="completed"
        )

        # Mock methods
        todo_list.async_write_ha_state = Mock()
        coordinator.async_save = AsyncMock()
        coordinator._update_approval_buttons = AsyncMock()

        await todo_list.async_delete_item("approval-uid")

        # Should remove item from list
        assert len(todo_list._items) == 2
        remaining_uids = [item.uid for item in todo_list._items]
        assert "approval-uid" not in remaining_uids

        # Should remove both pending chore and approval
        assert "approval-uid" not in coordinator.model.pending_chores
        assert "approval-123" not in coordinator.model.pending_approvals

        # Should not affect other pending data
        assert "pending-uid" in coordinator.model.pending_chores

        # Should save coordinator state and update approval buttons
        coordinator.async_save.assert_called_once()
        coordinator._update_approval_buttons.assert_called_once()
        todo_list.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_item_with_pending_data(self, todo_list_with_pending_data):
        """Test deleting nonexistent item doesn't affect pending data."""
        todo_list = todo_list_with_pending_data
        coordinator = todo_list._coord

        # Mock methods
        todo_list.async_write_ha_state = Mock()
        coordinator.async_save = AsyncMock()
        coordinator._update_approval_buttons = AsyncMock()

        await todo_list.async_delete_item("nonexistent-uid")

        # Should not change item count
        assert len(todo_list._items) == 3

        # Should not affect any pending data
        assert "pending-uid" in coordinator.model.pending_chores
        assert "approval-123" in coordinator.model.pending_approvals

        # Should not save coordinator or update buttons
        coordinator.async_save.assert_not_called()
        coordinator._update_approval_buttons.assert_not_called()
        todo_list.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_multiple_items_via_wrapper(self, todo_list_with_pending_data):
        """Test deleting multiple items via async_delete_todo_items."""
        todo_list = todo_list_with_pending_data

        # Mock the single delete method to track calls
        todo_list.async_delete_item = AsyncMock()

        await todo_list.async_delete_todo_items(["pending-uid", "approval-uid"])

        # Should call async_delete_item for each UID
        assert todo_list.async_delete_item.call_count == 2
        todo_list.async_delete_item.assert_any_call("pending-uid")
        todo_list.async_delete_item.assert_any_call("approval-uid")


class TestTodoItemUncheckingBehavior:
    """Test detailed unchecking behavior for pending approval items."""

    @pytest.fixture
    def todo_list_with_approval_items(self, coordinator):
        """Create todo list with items in pending approval state."""
        todo_list = KidTodoList(coordinator, "alice")

        # Add some todo items with different approval states
        todo_list._items = [
            TodoItem(
                summary="[PENDING APPROVAL] Regular approval item",
                uid="regular-approval-uid",
                status=TodoItemStatus.NEEDS_ACTION
            ),
            TodoItem(
                summary="[PENDING APPROVAL] Points approval (+10)",
                uid="points-approval-uid",
                status=TodoItemStatus.NEEDS_ACTION
            ),
            TodoItem(
                summary="Normal chore (no approval)",
                uid="normal-uid",
                status=TodoItemStatus.NEEDS_ACTION
            ),
        ]

        return todo_list

    @pytest.mark.asyncio
    async def test_uncheck_removes_approval_tag_completely(self, todo_list_with_approval_items, coordinator):
        """Test that unchecking removes [PENDING APPROVAL] tag completely."""
        todo_list = todo_list_with_approval_items
        todo_list.async_write_ha_state = Mock()

        # Add pending approval data
        coordinator.model.pending_approvals = {
            "approval456": PendingApproval(
                id="approval456",
                todo_uid="regular-approval-uid",
                kid_id="alice",
                title="Regular approval item",
                points=5,
                completed_ts=datetime.now().timestamp(),
                status="pending_approval"
            )
        }
        coordinator.async_save = AsyncMock()
        coordinator._update_approval_buttons = AsyncMock()

        # Simulate that the item was previously completed (old status)
        todo_list._items[0].status = TodoItemStatus.COMPLETED

        # Now uncheck it (change to needs_action)
        updated_item = TodoItem(
            summary="[PENDING APPROVAL] Regular approval item",
            uid="regular-approval-uid",
            status=TodoItemStatus.NEEDS_ACTION
        )

        await todo_list.async_update_item(updated_item)

        # Should remove [PENDING APPROVAL] tag completely
        found_item = next(item for item in todo_list._items if item.uid == "regular-approval-uid")
        assert found_item.summary == "Regular approval item"
        assert "[PENDING APPROVAL]" not in found_item.summary

        # Should clean up approval data
        assert "approval456" not in coordinator.model.pending_approvals
        coordinator.async_save.assert_called_once()
        coordinator._update_approval_buttons.assert_called_once()

    @pytest.mark.asyncio
    async def test_uncheck_preserves_points_notation(self, todo_list_with_approval_items, coordinator):
        """Test that unchecking preserves points notation in title."""
        todo_list = todo_list_with_approval_items
        todo_list.async_write_ha_state = Mock()

        # Add pending approval data
        coordinator.model.pending_approvals = {
            "approval789": PendingApproval(
                id="approval789",
                todo_uid="points-approval-uid",
                kid_id="alice",
                title="Points approval",
                points=10,
                completed_ts=datetime.now().timestamp(),
                status="pending_approval"
            )
        }
        coordinator.async_save = AsyncMock()
        coordinator._update_approval_buttons = AsyncMock()

        # Simulate that the item was previously completed
        todo_list._items[1].status = TodoItemStatus.COMPLETED

        # Now uncheck it
        updated_item = TodoItem(
            summary="[PENDING APPROVAL] Points approval (+10)",
            uid="points-approval-uid",
            status=TodoItemStatus.NEEDS_ACTION
        )

        await todo_list.async_update_item(updated_item)

        # Should remove only [PENDING APPROVAL] tag, keep points notation
        found_item = next(item for item in todo_list._items if item.uid == "points-approval-uid")
        assert found_item.summary == "Points approval (+10)"
        assert "[PENDING APPROVAL]" not in found_item.summary
        assert "(+10)" in found_item.summary

    @pytest.mark.asyncio
    async def test_uncheck_item_without_approval_data(self, todo_list_with_approval_items, coordinator):
        """Test unchecking item that has approval tag but no approval data."""
        todo_list = todo_list_with_approval_items
        todo_list.async_write_ha_state = Mock()

        # No approval data in coordinator
        coordinator.model.pending_approvals = {}
        coordinator.async_save = AsyncMock()
        coordinator._update_approval_buttons = AsyncMock()

        # Simulate that the item was previously completed
        todo_list._items[0].status = TodoItemStatus.COMPLETED

        # Now uncheck it
        updated_item = TodoItem(
            summary="[PENDING APPROVAL] Regular approval item",
            uid="regular-approval-uid",
            status=TodoItemStatus.NEEDS_ACTION
        )

        await todo_list.async_update_item(updated_item)

        # Should still remove [PENDING APPROVAL] tag even without approval data
        found_item = next(item for item in todo_list._items if item.uid == "regular-approval-uid")
        assert found_item.summary == "Regular approval item"
        assert "[PENDING APPROVAL]" not in found_item.summary

        # Should save coordinator state even if no approvals removed
        coordinator.async_save.assert_called_once()
        coordinator._update_approval_buttons.assert_called_once()

    @pytest.mark.asyncio
    async def test_uncheck_item_with_pending_chore_data(self, todo_list_with_approval_items, coordinator):
        """Test unchecking item that also has pending chore data."""
        todo_list = todo_list_with_approval_items
        todo_list.async_write_ha_state = Mock()

        # Add both approval and pending chore data
        coordinator.model.pending_approvals = {
            "approval999": PendingApproval(
                id="approval999",
                todo_uid="regular-approval-uid",
                kid_id="alice",
                title="Regular approval item",
                points=5,
                completed_ts=datetime.now().timestamp(),
                status="pending_approval"
            )
        }
        coordinator.model.pending_chores = {
            "regular-approval-uid": PendingChore(
                todo_uid="regular-approval-uid",
                kid_id="alice",
                title="Regular approval item",
                points=5,
                created_ts=datetime.now().timestamp(),
                status="completed"
            )
        }
        coordinator.async_save = AsyncMock()
        coordinator._update_approval_buttons = AsyncMock()

        # Simulate that the item was previously completed
        todo_list._items[0].status = TodoItemStatus.COMPLETED

        # Now uncheck it
        updated_item = TodoItem(
            summary="[PENDING APPROVAL] Regular approval item",
            uid="regular-approval-uid",
            status=TodoItemStatus.NEEDS_ACTION
        )

        await todo_list.async_update_item(updated_item)

        # Should remove [PENDING APPROVAL] tag
        found_item = next(item for item in todo_list._items if item.uid == "regular-approval-uid")
        assert found_item.summary == "Regular approval item"
        assert "[PENDING APPROVAL]" not in found_item.summary

        # Should reset pending chore status and clear completed timestamp
        assert coordinator.model.pending_chores["regular-approval-uid"].status == "pending"
        assert coordinator.model.pending_chores["regular-approval-uid"].completed_ts is None

        # Should clean up approval data
        assert "approval999" not in coordinator.model.pending_approvals

    @pytest.mark.asyncio
    async def test_normal_item_uncheck_no_approval_processing(self, todo_list_with_approval_items, coordinator):
        """Test that normal items (without approval tag) don't trigger approval logic."""
        todo_list = todo_list_with_approval_items
        todo_list.async_write_ha_state = Mock()

        coordinator.async_save = AsyncMock()
        coordinator._update_approval_buttons = AsyncMock()
        coordinator.save_todo_item = AsyncMock()

        # Simulate that normal item was previously completed
        todo_list._items[2].status = TodoItemStatus.COMPLETED

        # Now uncheck it
        updated_item = TodoItem(
            summary="Normal chore (no approval)",
            uid="normal-uid",
            status=TodoItemStatus.NEEDS_ACTION
        )

        await todo_list.async_update_item(updated_item)

        # Should not change summary at all
        found_item = next(item for item in todo_list._items if item.uid == "normal-uid")
        assert found_item.summary == "Normal chore (no approval)"

        # Should not trigger coordinator save or button updates
        coordinator.async_save.assert_not_called()
        coordinator._update_approval_buttons.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_approval_items_for_same_todo(self, todo_list_with_approval_items, coordinator):
        """Test unchecking when multiple approval items exist for same todo UID."""
        todo_list = todo_list_with_approval_items
        todo_list.async_write_ha_state = Mock()

        # Add multiple approval records for same todo_uid
        coordinator.model.pending_approvals = {
            "approval001": PendingApproval(
                id="approval001",
                todo_uid="regular-approval-uid",
                kid_id="alice",
                title="First approval",
                points=5,
                completed_ts=datetime.now().timestamp(),
                status="pending_approval"
            ),
            "approval002": PendingApproval(
                id="approval002",
                todo_uid="regular-approval-uid",
                kid_id="alice",
                title="Second approval",
                points=3,
                completed_ts=datetime.now().timestamp(),
                status="pending_approval"
            ),
            "approval003": PendingApproval(
                id="approval003",
                todo_uid="other-uid",
                kid_id="alice",
                title="Other approval",
                points=2,
                completed_ts=datetime.now().timestamp(),
                status="pending_approval"
            ),
        }
        coordinator.async_save = AsyncMock()
        coordinator._update_approval_buttons = AsyncMock()

        # Simulate that the item was previously completed
        todo_list._items[0].status = TodoItemStatus.COMPLETED

        # Now uncheck it
        updated_item = TodoItem(
            summary="[PENDING APPROVAL] Regular approval item",
            uid="regular-approval-uid",
            status=TodoItemStatus.NEEDS_ACTION
        )

        await todo_list.async_update_item(updated_item)

        # Should remove [PENDING APPROVAL] tag
        found_item = next(item for item in todo_list._items if item.uid == "regular-approval-uid")
        assert found_item.summary == "Regular approval item"

        # Should remove all approvals for this todo_uid but keep others
        assert "approval001" not in coordinator.model.pending_approvals
        assert "approval002" not in coordinator.model.pending_approvals
        assert "approval003" in coordinator.model.pending_approvals  # Different UID, should remain
