"""Tests for reward progress tracking in SimpleChores integration."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from custom_components.simplechores.coordinator import SimpleChoresCoordinator
from custom_components.simplechores.models import Reward, RewardProgress, StorageModel
from custom_components.simplechores.storage import SimpleChoresStore


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    hass = Mock()
    hass.bus = Mock()
    hass.bus.async_fire = Mock()
    return hass


@pytest.fixture  
def mock_store():
    """Return a mock store."""
    store = Mock()
    store.async_load = AsyncMock()
    store.async_save = AsyncMock()
    return store


@pytest.fixture
def coordinator_with_rewards(mock_hass, mock_store):
    """Create a coordinator with test rewards."""
    with patch('custom_components.simplechores.coordinator.SimpleChoresStore') as mock_store_class:
        mock_store_class.return_value = mock_store
        
        # Create a model with completion and streak rewards
        model = StorageModel()
        model.rewards = {
            "trash_master": Reward(
                id="trash_master",
                title="Trash Master Badge",
                required_completions=10,
                required_chore_type="trash",
                description="Take out trash 10 times"
            ),
            "bed_streak": Reward(
                id="bed_streak", 
                title="Perfect Week - Bed Made",
                required_streak_days=7,
                required_chore_type="bed",
                description="Make bed every day for 1 week"
            ),
            "movie_night": Reward(
                id="movie_night",
                title="Family Movie Night", 
                cost=20,
                description="Pick tonight's movie"
            )
        }
        
        mock_store.async_load.return_value = model
        
        coordinator = SimpleChoresCoordinator(mock_hass)
        coordinator.model = model
        coordinator.store = mock_store
        
        return coordinator


class TestRewardProgress:
    """Test reward progress tracking functionality."""
    
    @pytest.mark.asyncio
    async def test_completion_reward_progress(self, coordinator_with_rewards):
        """Test completion-based reward progress tracking."""
        coord = coordinator_with_rewards
        kid_id = "alex"
        
        # Initially no progress
        progress = coord.get_reward_progress(kid_id, "trash_master")
        assert progress is None
        
        # Complete a trash chore
        achieved = await coord.update_reward_progress(kid_id, "trash", "2024-01-01")
        assert achieved == []  # Not achieved yet
        
        # Check progress was created
        progress = coord.get_reward_progress(kid_id, "trash_master")
        assert progress is not None
        assert progress.current_completions == 1
        assert not progress.completed
        
        # Complete 9 more trash chores to reach 10 total
        for i in range(2, 11):  # Days 2-10
            achieved = await coord.update_reward_progress(kid_id, "trash", f"2024-01-{i:02d}")
            if i < 10:
                assert achieved == []
                progress = coord.get_reward_progress(kid_id, "trash_master")
                assert progress.current_completions == i
                assert not progress.completed
        
        # 10th completion should achieve the reward
        progress = coord.get_reward_progress(kid_id, "trash_master")
        assert progress.current_completions == 10
        assert progress.completed
        assert progress.completion_date is not None
    
    @pytest.mark.asyncio 
    async def test_streak_reward_progress(self, coordinator_with_rewards):
        """Test streak-based reward progress tracking."""
        coord = coordinator_with_rewards
        kid_id = "emma"
        
        # Complete bed chore on consecutive days
        achieved = await coord.update_reward_progress(kid_id, "bed", "2024-01-01")
        assert achieved == []
        
        progress = coord.get_reward_progress(kid_id, "bed_streak")
        assert progress.current_streak == 1
        assert progress.last_completion_date == "2024-01-01"
        assert not progress.completed
        
        # Continue streak for 6 more days
        for day in range(2, 8):  # Days 2-7
            achieved = await coord.update_reward_progress(kid_id, "bed", f"2024-01-{day:02d}")
            progress = coord.get_reward_progress(kid_id, "bed_streak")
            
            if day < 7:
                assert achieved == []
                assert progress.current_streak == day
                assert not progress.completed
            else:
                assert "bed_streak" in achieved
                assert progress.current_streak == 7
                assert progress.completed
                assert progress.completion_date is not None
    
    @pytest.mark.asyncio
    async def test_streak_broken_and_reset(self, coordinator_with_rewards):
        """Test that broken streaks reset properly."""
        coord = coordinator_with_rewards
        kid_id = "alex"
        
        # Build up a streak
        await coord.update_reward_progress(kid_id, "bed", "2024-01-01")
        await coord.update_reward_progress(kid_id, "bed", "2024-01-02")
        await coord.update_reward_progress(kid_id, "bed", "2024-01-03")
        
        progress = coord.get_reward_progress(kid_id, "bed_streak")
        assert progress.current_streak == 3
        
        # Skip a day - this should break the streak
        await coord.update_reward_progress(kid_id, "bed", "2024-01-05")  # Skip day 4
        
        progress = coord.get_reward_progress(kid_id, "bed_streak")
        assert progress.current_streak == 1  # Reset to 1
        assert progress.last_completion_date == "2024-01-05"
    
    @pytest.mark.asyncio
    async def test_same_day_doesnt_break_streak(self, coordinator_with_rewards):
        """Test that completing the same chore twice on same day doesn't break streak."""
        coord = coordinator_with_rewards
        kid_id = "alex"
        
        # Complete chore twice on same day
        await coord.update_reward_progress(kid_id, "bed", "2024-01-01")
        await coord.update_reward_progress(kid_id, "bed", "2024-01-01")  # Same day
        
        progress = coord.get_reward_progress(kid_id, "bed_streak")
        assert progress.current_streak == 1  # Should still be 1, not reset
        
        # Next day should continue streak
        await coord.update_reward_progress(kid_id, "bed", "2024-01-02")
        
        progress = coord.get_reward_progress(kid_id, "bed_streak")
        assert progress.current_streak == 2
    
    @pytest.mark.asyncio
    async def test_chore_type_filtering(self, coordinator_with_rewards):
        """Test that only matching chore types contribute to rewards."""
        coord = coordinator_with_rewards
        kid_id = "alex"
        
        # Complete a dishes chore - shouldn't affect trash reward
        achieved = await coord.update_reward_progress(kid_id, "dishes", "2024-01-01")
        assert achieved == []
        
        progress = coord.get_reward_progress(kid_id, "trash_master")
        assert progress is None  # No progress created for wrong chore type
        
        # Complete a trash chore - should affect trash reward
        achieved = await coord.update_reward_progress(kid_id, "trash", "2024-01-01")
        assert achieved == []
        
        progress = coord.get_reward_progress(kid_id, "trash_master")
        assert progress is not None
        assert progress.current_completions == 1
    
    @pytest.mark.asyncio
    async def test_point_based_rewards_unaffected(self, coordinator_with_rewards):
        """Test that point-based rewards are not affected by chore completion tracking."""
        coord = coordinator_with_rewards
        kid_id = "alex"
        
        # Complete any chore - shouldn't create progress for point-based rewards
        achieved = await coord.update_reward_progress(kid_id, "any_chore", "2024-01-01")
        assert achieved == []
        
        progress = coord.get_reward_progress(kid_id, "movie_night")
        assert progress is None  # Point-based rewards don't track progress
    
    @pytest.mark.asyncio
    async def test_reward_achievement_event(self, coordinator_with_rewards):
        """Test that reward achievement fires Home Assistant event."""
        coord = coordinator_with_rewards
        kid_id = "alex"
        
        # Complete enough chores to achieve reward
        for i in range(1, 11):
            await coord.update_reward_progress(kid_id, "trash", f"2024-01-{i:02d}")
        
        # Verify event was fired
        coord.hass.bus.async_fire.assert_called_with(
            "simplechores_reward_achieved",
            {
                "kid_id": kid_id,
                "reward_id": "trash_master",
                "reward_title": "Trash Master Badge",
            }
        )
    
    @pytest.mark.asyncio
    async def test_already_completed_rewards_ignored(self, coordinator_with_rewards):
        """Test that already completed rewards don't get updated further."""
        coord = coordinator_with_rewards
        kid_id = "alex"
        
        # Complete reward
        for i in range(1, 11):
            await coord.update_reward_progress(kid_id, "trash", f"2024-01-{i:02d}")
        
        progress = coord.get_reward_progress(kid_id, "trash_master")
        assert progress.completed
        completion_date = progress.completion_date
        
        # Try to complete more - shouldn't change anything
        achieved = await coord.update_reward_progress(kid_id, "trash", "2024-01-15")
        assert achieved == []
        
        progress = coord.get_reward_progress(kid_id, "trash_master")
        assert progress.current_completions == 10  # Unchanged
        assert progress.completion_date == completion_date  # Unchanged
    
    @pytest.mark.asyncio
    async def test_chore_completion_updates_progress(self, coordinator_with_rewards):
        """Test that completing chores via coordinator updates reward progress."""
        coord = coordinator_with_rewards
        kid_id = "alex"
        
        # Create a pending chore with chore_type
        todo_uid = await coord.create_pending_chore(kid_id, "Take out trash", 5, "trash")
        
        # Complete the chore
        success = await coord.complete_chore_by_uid(todo_uid)
        assert success
        
        # Check that reward progress was updated
        progress = coord.get_reward_progress(kid_id, "trash_master")
        assert progress is not None
        assert progress.current_completions == 1
    
    @pytest.mark.asyncio
    async def test_approval_updates_progress(self, coordinator_with_rewards):
        """Test that approving chores updates reward progress."""
        coord = coordinator_with_rewards
        kid_id = "alex"
        
        # Create and request approval for a chore
        todo_uid = await coord.create_pending_chore(kid_id, "Take out trash", 5, "trash")
        approval_id = await coord.request_approval(todo_uid)
        
        # Approve the chore
        success = await coord.approve_chore(approval_id)
        assert success
        
        # Check that reward progress was updated
        progress = coord.get_reward_progress(kid_id, "trash_master")
        assert progress is not None
        assert progress.current_completions == 1


class TestRewardTypes:
    """Test reward type detection methods."""
    
    def test_point_based_reward_detection(self):
        """Test point-based reward detection."""
        reward = Reward(
            id="movie",
            title="Movie Night",
            cost=20,
            description="Family movie"
        )
        
        assert reward.is_point_based()
        assert not reward.is_completion_based()
        assert not reward.is_streak_based()
    
    def test_completion_based_reward_detection(self):
        """Test completion-based reward detection."""
        reward = Reward(
            id="master",
            title="Chore Master",
            required_completions=10,
            required_chore_type="trash",
            description="Complete 10 trash chores"
        )
        
        assert not reward.is_point_based()
        assert reward.is_completion_based()
        assert not reward.is_streak_based()
    
    def test_streak_based_reward_detection(self):
        """Test streak-based reward detection."""
        reward = Reward(
            id="streak",
            title="Daily Streak",
            required_streak_days=7,
            required_chore_type="bed",
            description="7 day bed making streak"
        )
        
        assert not reward.is_point_based()
        assert not reward.is_completion_based()
        assert reward.is_streak_based()