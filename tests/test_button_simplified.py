"""Simplified tests for button platform functionality."""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotFound

from custom_components.simplechores.button import (
    SimpleChoresCreateChoreButton,
    SimpleChoresCreateRecurringButton, 
    SimpleChoresGenerateDailyButton,
    SimpleChoresApprovalStatusButton,
    SimpleChoresResetRejectedButton,
    SimpleChoresRewardButton,
    async_setup_entry
)
from custom_components.simplechores.coordinator import SimpleChoresCoordinator
from custom_components.simplechores.models import StorageModel, PendingApproval, Reward


class TestSimpleChoresCreateChoreButton:
    """Test the create chore button functionality."""
    
    @pytest.fixture
    def button(self, coordinator, mock_hass):
        return SimpleChoresCreateChoreButton(coordinator, mock_hass)
    
    def test_button_properties(self, button):
        """Test button basic properties."""
        assert button._attr_name == "Create Chore"
        assert button._attr_unique_id == "simplechores_create_chore_button"
        assert button._attr_icon == "mdi:plus-circle"
    
    @pytest.mark.asyncio
    async def test_button_press(self, button):
        """Test button press logs correctly."""
        with patch('custom_components.simplechores.button._LOGGER') as mock_logger:
            await button.async_press()
            
            # Should log the button press
            mock_logger.info.assert_called_with("SimpleChores: Create chore button pressed")


class TestSimpleChoresRewardButton:
    """Test the reward button functionality."""
    
    @pytest.fixture
    def reward_button(self, coordinator, mock_hass):
        return SimpleChoresRewardButton(coordinator, "movie_night", "alice", mock_hass)
    
    def test_button_properties(self, coordinator, mock_hass):
        """Test reward button properties."""
        # Mock a reward
        reward = Reward(id="ice_cream", title="Ice Cream", cost=15, description="Sweet treat")
        coordinator.get_reward = Mock(return_value=reward)
        
        button = SimpleChoresRewardButton(coordinator, "ice_cream", "alice", mock_hass)
        
        assert button._reward_id == "ice_cream"
        assert button._kid_id == "alice"
        assert button._attr_unique_id == "simplechores_reward_ice_cream_alice"
        assert button._attr_name == "Ice Cream (Alice)"
    
    @pytest.mark.asyncio
    async def test_reward_button_press_sufficient_points(self, coordinator, mock_hass):
        """Test reward button press with sufficient points."""
        # Setup reward and points
        reward = Reward(id="movie", title="Movie Night", cost=20, description="Family movie")
        coordinator.get_reward = Mock(return_value=reward)
        coordinator.get_points = Mock(return_value=25)  # Sufficient points
        
        button = SimpleChoresRewardButton(coordinator, "movie", "alice", mock_hass)
        mock_hass.services.async_call = AsyncMock()
        
        await button.async_press()
        
        # Should call claim_reward service
        mock_hass.services.async_call.assert_called_once_with(
            "simplechores", "claim_reward",
            {"kid": "alice", "reward_id": "movie"},
            blocking=False
        )
    
    @pytest.mark.asyncio
    async def test_reward_button_press_insufficient_points(self, coordinator, mock_hass):
        """Test reward button press with insufficient points."""
        # Setup reward and insufficient points
        reward = Reward(id="movie", title="Movie Night", cost=20, description="Family movie")
        coordinator.get_reward = Mock(return_value=reward)
        coordinator.get_points = Mock(return_value=10)  # Insufficient points
        
        button = SimpleChoresRewardButton(coordinator, "movie", "alice", mock_hass)
        mock_hass.services.async_call = AsyncMock()
        
        await button.async_press()
        
        # Should not call service
        mock_hass.services.async_call.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_reward_button_press_no_reward(self, coordinator, mock_hass):
        """Test reward button press when reward doesn't exist."""
        # Setup no reward found
        coordinator.get_reward = Mock(return_value=None)
        coordinator.get_points = Mock(return_value=25)
        
        button = SimpleChoresRewardButton(coordinator, "nonexistent", "alice", mock_hass)
        mock_hass.services.async_call = AsyncMock()
        
        await button.async_press()
        
        # Should not call service
        mock_hass.services.async_call.assert_not_called()


class TestSimpleChoresCreateRecurringButton:
    """Test the create recurring chore button."""
    
    @pytest.fixture
    def button(self, coordinator, mock_hass):
        return SimpleChoresCreateRecurringButton(coordinator, mock_hass)
    
    def test_button_properties(self, button):
        """Test button properties."""
        assert button._attr_name == "Create Recurring Chore"
        assert button._attr_unique_id == "simplechores_create_recurring_button"
        assert button._attr_icon == "mdi:repeat"
    
    @pytest.mark.asyncio
    async def test_button_press(self, button):
        """Test button press logs correctly."""
        with patch('custom_components.simplechores.button._LOGGER') as mock_logger:
            await button.async_press()
            
            mock_logger.info.assert_called_with("SimpleChores: Create recurring chore button pressed")


class TestSimpleChoresGenerateDailyButton:
    """Test the generate daily chores button."""
    
    @pytest.fixture
    def button(self, coordinator, mock_hass):
        return SimpleChoresGenerateDailyButton(coordinator, mock_hass)
    
    def test_button_properties(self, button):
        """Test button properties."""
        assert button._attr_name == "Generate Daily Chores"
        assert button._attr_unique_id == "simplechores_generate_daily_button"
        assert button._attr_icon == "mdi:calendar-today"
    
    @pytest.mark.asyncio
    async def test_button_press(self, button, mock_hass):
        """Test button press calls service."""
        mock_hass.services.async_call = AsyncMock()
        
        await button.async_press()
        
        # Should call generate service
        mock_hass.services.async_call.assert_called_once_with(
            "simplechores", "generate_recurring_chores",
            {"schedule_type": "daily"},
            blocking=False
        )


class TestSimpleChoresApprovalStatusButton:
    """Test the approval status button."""
    
    @pytest.fixture
    def button(self, coordinator, mock_hass):
        return SimpleChoresApprovalStatusButton(coordinator, mock_hass)
    
    def test_button_properties(self, button):
        """Test button properties."""
        assert button._attr_name == "Show Pending Approvals"
        assert button._attr_unique_id == "simplechores_approval_status_button"
        assert button._attr_icon == "mdi:clipboard-list"
    
    @pytest.mark.asyncio
    async def test_button_press_with_approvals(self, button, coordinator):
        """Test button press with pending approvals."""
        # Mock pending approvals
        approvals = [
            PendingApproval(
                id="approval1",
                todo_uid="uid1",
                kid_id="alice", 
                title="Clean room",
                points=5
            ),
            PendingApproval(
                id="approval2",
                todo_uid="uid2",
                kid_id="bob",
                title="Do homework", 
                points=3
            )
        ]
        coordinator.get_pending_approvals = Mock(return_value=approvals)
        
        with patch('custom_components.simplechores.button._LOGGER') as mock_logger:
            await button.async_press()
            
            # Should log pending approvals count and details
            mock_logger.info.assert_called()
            # Check that info was called with expected format
            calls = mock_logger.info.call_args_list
            assert any("2 pending approvals:" in str(call) for call in calls)
    
    @pytest.mark.asyncio
    async def test_button_press_no_approvals(self, button, coordinator):
        """Test button press with no pending approvals."""
        coordinator.get_pending_approvals = Mock(return_value=[])
        
        with patch('custom_components.simplechores.button._LOGGER') as mock_logger:
            await button.async_press()
            
            # Should still log (0 pending approvals)
            mock_logger.info.assert_called()


class TestSimpleChoresResetRejectedButton:
    """Test the reset rejected chores button."""
    
    @pytest.fixture
    def button(self, coordinator, mock_hass):
        return SimpleChoresResetRejectedButton(coordinator, mock_hass)
    
    def test_button_properties(self, button):
        """Test button properties."""
        assert button._attr_name == "Reset Rejected Chores"
        assert button._attr_unique_id == "simplechores_reset_rejected_button"
        assert button._attr_icon == "mdi:restore"
    
    @pytest.mark.asyncio
    async def test_button_press(self, button):
        """Test button press logs correctly."""
        with patch('custom_components.simplechores.button._LOGGER') as mock_logger:
            await button.async_press()
            
            mock_logger.info.assert_called_with("SimpleChores: Reset rejected chores button pressed")


class TestButtonSetupEntry:
    """Test button platform setup."""
    
    @pytest.mark.asyncio
    async def test_async_setup_entry_basic(self, mock_hass, coordinator):
        """Test basic button setup."""
        # Mock some rewards for testing
        rewards = [
            Reward(id="movie", title="Movie Night", cost=20, description="Family movie"),
            Reward(id="ice_cream", title="Ice Cream", cost=15, description="Sweet treat")
        ]
        coordinator.get_rewards = Mock(return_value=rewards)
        
        config_entry = Mock()
        config_entry.data = {"kids": "alice,bob"}
        
        add_entities = Mock()
        
        await async_setup_entry(mock_hass, config_entry, add_entities)
        
        # Should create buttons
        add_entities.assert_called_once()
        entities = add_entities.call_args[0][0]
        
        # Should have: basic buttons + reward buttons for each kid
        # Basic: Create, Create Recurring, Generate Daily, Approval Status, Reset Rejected = 5
        # Rewards: 2 rewards × 2 kids = 4
        # Total: 5 + 4 = 9
        assert len(entities) >= 5  # At least the basic buttons
        
        entity_names = [entity._attr_name for entity in entities]
        
        # Check basic buttons
        assert "Create Chore" in entity_names
        assert "Create Recurring Chore" in entity_names
        assert "Generate Daily Chores" in entity_names
        assert "Show Pending Approvals" in entity_names
        assert "Reset Rejected Chores" in entity_names
        
        # Check reward buttons (should exist for each kid)
        reward_button_names = [name for name in entity_names if "(" in name and ")" in name]
        assert len(reward_button_names) >= 4  # 2 rewards × 2 kids
    
    @pytest.mark.asyncio
    async def test_async_setup_entry_no_rewards(self, mock_hass, coordinator):
        """Test setup with no rewards."""
        coordinator.get_rewards = Mock(return_value=[])
        
        config_entry = Mock()
        config_entry.data = {"kids": "alice"}
        
        add_entities = Mock()
        
        await async_setup_entry(mock_hass, config_entry, add_entities)
        
        entities = add_entities.call_args[0][0]
        
        # Should only have basic buttons (no reward buttons)
        assert len(entities) == 5
        
        entity_names = [entity._attr_name for entity in entities]
        assert "Create Chore" in entity_names
        assert "Reset Rejected Chores" in entity_names
        
        # No reward buttons
        reward_button_names = [name for name in entity_names if "(" in name and ")" in name]
        assert len(reward_button_names) == 0
    
    @pytest.mark.asyncio
    async def test_async_setup_entry_default_kids(self, mock_hass, coordinator):
        """Test setup with default kids."""
        coordinator.get_rewards = Mock(return_value=[])
        
        config_entry = Mock()
        config_entry.data = {}  # No kids specified, should use default
        
        add_entities = Mock()
        
        await async_setup_entry(mock_hass, config_entry, add_entities)
        
        entities = add_entities.call_args[0][0]
        
        # Should create entities (even with default kids)
        assert len(entities) >= 5
    
    @pytest.mark.asyncio
    async def test_async_setup_entry_empty_kids(self, mock_hass, coordinator):
        """Test setup with empty kids list."""
        coordinator.get_rewards = Mock(return_value=[])
        
        config_entry = Mock()
        config_entry.data = {"kids": "  ,  "}  # Empty after stripping
        
        add_entities = Mock()
        
        await async_setup_entry(mock_hass, config_entry, add_entities)
        
        entities = add_entities.call_args[0][0]
        
        # Should still create basic buttons (no reward buttons due to no kids)
        assert len(entities) == 5
        
        entity_names = [entity._attr_name for entity in entities]
        assert "Create Chore" in entity_names
        assert "Reset Rejected Chores" in entity_names


class TestButtonEntityTypes:
    """Test that buttons are of correct entity types."""
    
    def test_all_buttons_are_button_entities(self, coordinator, mock_hass):
        """Test all button classes inherit from ButtonEntity."""
        buttons = [
            SimpleChoresCreateChoreButton(coordinator, mock_hass),
            SimpleChoresCreateRecurringButton(coordinator, mock_hass),
            SimpleChoresGenerateDailyButton(coordinator, mock_hass),
            SimpleChoresApprovalStatusButton(coordinator, mock_hass),
            SimpleChoresResetRejectedButton(coordinator, mock_hass),
            SimpleChoresRewardButton(coordinator, "test_reward", "alice", mock_hass)
        ]
        
        for button in buttons:
            assert isinstance(button, ButtonEntity)


class TestButtonUniqueIds:
    """Test button unique ID generation."""
    
    def test_basic_button_unique_ids(self, coordinator, mock_hass):
        """Test basic buttons have unique IDs."""
        buttons = [
            SimpleChoresCreateChoreButton(coordinator, mock_hass),
            SimpleChoresCreateRecurringButton(coordinator, mock_hass),
            SimpleChoresGenerateDailyButton(coordinator, mock_hass),
            SimpleChoresApprovalStatusButton(coordinator, mock_hass),
            SimpleChoresResetRejectedButton(coordinator, mock_hass)
        ]
        
        unique_ids = [button._attr_unique_id for button in buttons]
        
        # All should be different
        assert len(set(unique_ids)) == len(unique_ids)
        
        # All should contain domain
        for uid in unique_ids:
            assert "simplechores" in uid
    
    def test_reward_button_unique_ids(self, coordinator, mock_hass):
        """Test reward buttons have unique IDs per reward/kid combination."""
        button1 = SimpleChoresRewardButton(coordinator, "movie", "alice", mock_hass)
        button2 = SimpleChoresRewardButton(coordinator, "movie", "bob", mock_hass)
        button3 = SimpleChoresRewardButton(coordinator, "ice_cream", "alice", mock_hass)
        
        unique_ids = [
            button1._attr_unique_id,
            button2._attr_unique_id,
            button3._attr_unique_id
        ]
        
        # All should be different
        assert len(set(unique_ids)) == 3
        
        # Should contain reward and kid info
        assert "movie" in button1._attr_unique_id
        assert "alice" in button1._attr_unique_id
        assert "bob" in button2._attr_unique_id
        assert "ice_cream" in button3._attr_unique_id