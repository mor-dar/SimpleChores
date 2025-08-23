"""Data coordinator for SimpleChores integration."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any
import uuid

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

from .models import Kid, LedgerEntry, PendingApproval, PendingChore, RecurringChore, Reward, RewardProgress, StorageModel, TodoItemModel
from .storage import SimpleChoresStore


class SimpleChoresCoordinator:
    """Coordinates data operations for SimpleChores integration."""
    
    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.store = SimpleChoresStore(hass)
        self.model: StorageModel | None = None

    async def async_init(self) -> None:
        """Initialize the coordinator by loading data."""
        self.model = await self.store.async_load()
        # Add default rewards if none exist
        if not self.model.rewards:
            await self._add_default_rewards()

    async def async_save(self) -> None:
        """Save the model data."""
        if self.model is None:
            raise RuntimeError("Model not initialized")
        await self.store.async_save(self.model)

    # ---- kids/points ----
    async def ensure_kid(self, kid_id: str, name: str | None = None) -> None:
        """Ensure a kid exists in the system."""
        if self.model is None:
            raise RuntimeError("Model not initialized")
        if kid_id not in self.model.kids:
            self.model.kids[kid_id] = Kid(id=kid_id, name=name or kid_id)
            await self.async_save()

    def get_points(self, kid_id: str) -> int:
        """Get current points for a kid."""
        if not self.model or kid_id not in self.model.kids:
            return 0
        return self.model.kids[kid_id].points

    async def add_points(self, kid_id: str, amount: int, reason: str, kind: str = "earn") -> None:
        """Add points to a kid's account."""
        if self.model is None:
            raise RuntimeError("Model not initialized")
        if kid_id not in self.model.kids:
            self.model.kids[kid_id] = Kid(id=kid_id, name=kid_id)
        self.model.kids[kid_id].points += amount
        self.model.ledger.append(
            LedgerEntry(ts=datetime.now().timestamp(), kid_id=kid_id, delta=amount, reason=reason, kind=kind)
        )
        await self.async_save()
        # Trigger entity updates
        await self._update_entities(kid_id)

    async def remove_points(self, kid_id: str, amount: int, reason: str, kind: str = "spend") -> None:
        """Remove points from a kid's account."""
        await self.add_points(kid_id, -abs(amount), reason, kind)

    # ---- rewards ----
    async def _add_default_rewards(self) -> None:
        """Add some default rewards for demo purposes."""
        if self.model is None:
            raise RuntimeError("Model not initialized")
        default_rewards = [
            # Legacy point-based rewards (still supported)
            Reward(id="movie_night", title="Family Movie Night", cost=20, description="Pick tonight's movie"),
            Reward(id="extra_allowance", title="Extra $5 Allowance", cost=25, description="Bonus money", create_calendar_event=False),
            
            # New completion-based rewards
            Reward(id="trash_master", title="Trash Master Badge", required_completions=10, required_chore_type="trash", 
                  description="Take out trash 10 times", create_calendar_event=False),
            Reward(id="bed_streak", title="Perfect Week - Bed Made", required_streak_days=7, required_chore_type="bed",
                  description="Make bed every day for 1 week", calendar_duration_hours=2),
            Reward(id="dish_hero", title="Dish Washing Hero", required_completions=15, required_chore_type="dishes",
                  description="Wash dishes 15 times", create_calendar_event=False),
            Reward(id="clean_streak", title="Super Clean Streak", required_streak_days=14, required_chore_type="room",
                  description="Clean room every day for 2 weeks", calendar_duration_hours=3),
        ]
        for reward in default_rewards:
            self.model.rewards[reward.id] = reward
        await self.async_save()

    def get_rewards(self) -> list[Reward]:
        """Get all available rewards."""
        if not self.model:
            return []
        return list(self.model.rewards.values())

    def get_reward(self, reward_id: str) -> Reward | None:
        """Get a specific reward by ID."""
        if not self.model:
            return None
        return self.model.rewards.get(reward_id)

    async def add_reward(self, title: str, cost: int, description: str = "", create_calendar_event: bool = True) -> str:
        """Add a new reward and return its ID."""
        if self.model is None:
            raise RuntimeError("Model not initialized")
        reward_id = str(uuid.uuid4())[:8]
        reward = Reward(id=reward_id, title=title, cost=cost, description=description, create_calendar_event=create_calendar_event)
        self.model.rewards[reward_id] = reward
        await self.async_save()
        return reward_id

    def _get_progress_key(self, kid_id: str, reward_id: str) -> str:
        """Generate key for reward progress tracking."""
        return f"{kid_id}_{reward_id}"

    def get_reward_progress(self, kid_id: str, reward_id: str) -> RewardProgress | None:
        """Get progress for a specific kid-reward combination."""
        if not self.model:
            return None
        key = self._get_progress_key(kid_id, reward_id)
        return self.model.reward_progress.get(key)

    async def _ensure_reward_progress(self, kid_id: str, reward_id: str) -> RewardProgress:
        """Ensure reward progress exists for a kid-reward combination."""
        if not self.model:
            raise RuntimeError("Model not initialized")
        key = self._get_progress_key(kid_id, reward_id)
        if key not in self.model.reward_progress:
            self.model.reward_progress[key] = RewardProgress(kid_id=kid_id, reward_id=reward_id)
        return self.model.reward_progress[key]

    async def update_reward_progress(self, kid_id: str, chore_type: str | None, completed_date: str) -> list[str]:
        """Update reward progress when a chore is completed. Returns list of newly achieved reward IDs."""
        if not self.model:
            raise RuntimeError("Model not initialized")
        
        achieved_rewards = []
        
        for reward in self.model.rewards.values():
            # Skip point-based rewards
            if reward.is_point_based():
                continue
                
            # Skip if chore type doesn't match reward requirement
            if reward.required_chore_type and reward.required_chore_type != chore_type:
                continue
            
            progress = await self._ensure_reward_progress(kid_id, reward.id)
            
            # Skip if already completed
            if progress.completed:
                continue
            
            if reward.is_completion_based():
                progress.current_completions += 1
                if progress.current_completions >= reward.required_completions:
                    progress.completed = True
                    progress.completion_date = datetime.now().timestamp()
                    achieved_rewards.append(reward.id)
                    _LOGGER.info("Reward achieved: %s completed %s (%d/%d)", 
                               kid_id, reward.title, progress.current_completions, reward.required_completions)
            
            elif reward.is_streak_based():
                # Check if this continues the streak
                from datetime import timedelta
                today = datetime.now().date()
                completed_date_obj = datetime.strptime(completed_date, "%Y-%m-%d").date()
                
                if progress.last_completion_date:
                    last_date = datetime.strptime(progress.last_completion_date, "%Y-%m-%d").date()
                    days_diff = (completed_date_obj - last_date).days
                    
                    if days_diff == 1:
                        # Consecutive day - continue streak
                        progress.current_streak += 1
                    elif days_diff == 0:
                        # Same day - don't increment but don't break streak
                        pass
                    else:
                        # Streak broken - reset
                        progress.current_streak = 1
                else:
                    # First completion
                    progress.current_streak = 1
                
                progress.last_completion_date = completed_date
                
                if progress.current_streak >= reward.required_streak_days:
                    progress.completed = True
                    progress.completion_date = datetime.now().timestamp()
                    achieved_rewards.append(reward.id)
                    _LOGGER.info("Streak reward achieved: %s completed %s (%d days)", 
                               kid_id, reward.title, progress.current_streak)
        
        if achieved_rewards:
            await self.async_save()
            # Trigger reward celebration/notification
            await self._notify_reward_achievements(kid_id, achieved_rewards)
        
        return achieved_rewards

    async def _notify_reward_achievements(self, kid_id: str, reward_ids: list[str]) -> None:
        """Handle reward achievements - create calendar events, fire events, etc."""
        from datetime import timedelta
        
        for reward_id in reward_ids:
            reward = self.get_reward(reward_id)
            if not reward:
                continue
                
            _LOGGER.info("🎉 %s achieved reward: %s", kid_id, reward.title)
            
            # Create calendar event if enabled
            if reward.create_calendar_event:
                # This will be handled by the service layer to access hass services
                pass
            
            # Fire Home Assistant event for automations
            if hasattr(self, 'hass'):
                self.hass.bus.async_fire(
                    "simplechores_reward_achieved",
                    {
                        "kid_id": kid_id,
                        "reward_id": reward_id,
                        "reward_title": reward.title,
                    }
                )

    # ---- chores ----
    async def create_pending_chore(self, kid_id: str, title: str, points: int, chore_type: str | None = None) -> str:
        """Create a chore and return the todo_uid to track it"""
        todo_uid = str(uuid.uuid4())
        chore = PendingChore(
            todo_uid=todo_uid,
            kid_id=kid_id,
            title=title,
            points=points,
            created_ts=datetime.now().timestamp(),
            chore_type=chore_type
        )
        self.model.pending_chores[todo_uid] = chore
        await self.async_save()
        
        # Update dynamic buttons when new chore is created (with error handling for tests)
        try:
            await self._update_approval_buttons()
        except Exception:
            # Ignore entity update errors in test environments
            pass
        
        return todo_uid

    async def complete_chore_by_uid(self, todo_uid: str) -> bool:
        """Complete a chore by todo UID and award points"""
        if todo_uid in self.model.pending_chores:
            chore = self.model.pending_chores.pop(todo_uid)
            await self.add_points(chore.kid_id, chore.points, f"Chore: {chore.title}", "earn")
            
            # Update reward progress
            completed_date = datetime.now().strftime("%Y-%m-%d")
            achieved_rewards = await self.update_reward_progress(chore.kid_id, chore.chore_type, completed_date)
            
            await self.async_save()
            return True
        return False

    def get_pending_chore(self, todo_uid: str) -> PendingChore | None:
        return self.model.pending_chores.get(todo_uid)

    async def _update_entities(self, kid_id: str) -> None:
        """Trigger entity updates after point changes."""
        _LOGGER.debug("Triggering entity updates for %s", kid_id)

        # Direct entity state update - most reliable method
        entity = None
        if hasattr(self, '_entities'):
            # Try exact match first
            if kid_id in self._entities:
                entity = self._entities[kid_id]
            else:
                # Try case-insensitive match
                for registered_kid, registered_entity in self._entities.items():
                    if registered_kid.lower() == kid_id.lower():
                        entity = registered_entity
                        break

        if entity:
            entity.async_write_ha_state()
            _LOGGER.debug("Updated entity state for %s", kid_id)
        else:
            if hasattr(self, '_entities'):
                _LOGGER.warning("No entity found for %s. Available: %s", 
                              kid_id, list(self._entities.keys()))
            else:
                _LOGGER.debug("No entities registered yet")

        # Fallback: trigger entity update via service
        entity_id = f"number.{kid_id}_points"
        try:
            await self.hass.services.async_call(
                "homeassistant", "update_entity", 
                {"entity_id": entity_id}, 
                blocking=False
            )
        except Exception as ex:
            _LOGGER.debug("Fallback entity update failed: %s", ex)

    # ---- recurring chores ----
    async def create_recurring_chore(self, kid_id: str, title: str, points: int, schedule_type: str, day_of_week: int = None, chore_type: str = None) -> str:
        """Create a recurring chore template"""
        assert self.model
        chore_id = str(uuid.uuid4())[:8]

        recurring_chore = RecurringChore(
            id=chore_id,
            title=title,
            points=points,
            kid_id=kid_id,
            schedule_type=schedule_type,
            day_of_week=day_of_week,
            enabled=True,
            chore_type=chore_type
        )

        self.model.recurring_chores[chore_id] = recurring_chore
        await self.async_save()
        return chore_id

    def get_recurring_chores(self, kid_id: str = None) -> list[RecurringChore]:
        """Get recurring chores, optionally filtered by kid"""
        chores = list(self.model.recurring_chores.values())
        if kid_id:
            chores = [c for c in chores if c.kid_id == kid_id]
        return chores

    async def generate_daily_chores(self):
        """Generate daily recurring chores"""
        for chore in self.model.recurring_chores.values():
            if chore.enabled and chore.schedule_type == "daily":
                # Create a new todo item for this chore
                todo_uid = await self.create_pending_chore(chore.kid_id, chore.title, chore.points, chore.chore_type)
                # Also create in todo list if available
                if hasattr(self, '_todo_entities') and chore.kid_id in self._todo_entities:
                    from homeassistant.components.todo import TodoItem, TodoItemStatus
                    todo_entity = self._todo_entities[chore.kid_id]
                    new_item = TodoItem(
                        summary=f"{chore.title} (+{chore.points})",
                        uid=todo_uid,
                        status=TodoItemStatus.NEEDS_ACTION
                    )
                    await todo_entity.async_create_item(new_item)

    async def generate_weekly_chores(self, target_day: int):
        """Generate weekly recurring chores for specific day (0=Monday, 6=Sunday)"""
        for chore in self.model.recurring_chores.values():
            if chore.enabled and chore.schedule_type == "weekly" and chore.day_of_week == target_day:
                # Create a new todo item for this chore
                todo_uid = await self.create_pending_chore(chore.kid_id, chore.title, chore.points, chore.chore_type)
                # Also create in todo list if available
                if hasattr(self, '_todo_entities') and chore.kid_id in self._todo_entities:
                    from homeassistant.components.todo import TodoItem, TodoItemStatus
                    todo_entity = self._todo_entities[chore.kid_id]
                    new_item = TodoItem(
                        summary=f"{chore.title} (+{chore.points})",
                        uid=todo_uid,
                        status=TodoItemStatus.NEEDS_ACTION
                    )
                    await todo_entity.async_create_item(new_item)

    # ---- parental approval ----
    async def request_approval(self, todo_uid: str) -> str:
        """Move a completed chore to pending approval state"""
        assert self.model

        if todo_uid in self.model.pending_chores:
            chore = self.model.pending_chores[todo_uid]
            
            # Validate chore status - only pending chores can request approval
            if chore.status != "pending":
                _LOGGER.warning("Cannot request approval for chore %s - status is %s (must be pending)", 
                              todo_uid, chore.status)
                return None
                
            approval_id = str(uuid.uuid4())[:8]

            # Create approval request
            approval = PendingApproval(
                id=approval_id,
                todo_uid=todo_uid,
                kid_id=chore.kid_id,
                title=chore.title,
                points=chore.points,
                completed_ts=datetime.now().timestamp()
            )

            # Update chore status
            chore.status = "completed"
            chore.completed_ts = datetime.now().timestamp()

            self.model.pending_approvals[approval_id] = approval
            await self.async_save()

            # Update approval buttons (with error handling for tests)
            try:
                await self._update_approval_buttons()
            except Exception:
                # Ignore entity update errors in test environments
                pass

            return approval_id
        return None

    async def approve_chore(self, approval_id: str) -> bool:
        """Approve a pending chore and award points"""
        assert self.model

        if approval_id in self.model.pending_approvals:
            approval = self.model.pending_approvals[approval_id]

            # Award points
            await self.add_points(approval.kid_id, approval.points, f"Approved: {approval.title}", "earn")

            # Update reward progress
            chore_type = None
            if approval.todo_uid in self.model.pending_chores:
                chore_type = self.model.pending_chores[approval.todo_uid].chore_type
            
            completed_date = datetime.now().strftime("%Y-%m-%d")
            achieved_rewards = await self.update_reward_progress(approval.kid_id, chore_type, completed_date)

            # Update approval status
            approval.status = "approved"

            # Update original chore status
            if approval.todo_uid in self.model.pending_chores:
                self.model.pending_chores[approval.todo_uid].status = "approved"
                self.model.pending_chores[approval.todo_uid].approved_ts = datetime.now().timestamp()

            await self.async_save()
            return True
        return False

    async def reject_chore(self, approval_id: str, reason: str = "Did not meet standards") -> bool:
        """Reject a pending chore"""
        assert self.model

        if approval_id in self.model.pending_approvals:
            approval = self.model.pending_approvals[approval_id]

            # Update approval status
            approval.status = "rejected"

            # Update original chore status
            if approval.todo_uid in self.model.pending_chores:
                self.model.pending_chores[approval.todo_uid].status = "rejected"

            await self.async_save()

            # Update approval buttons (with error handling for tests)
            try:
                await self._update_approval_buttons()
            except Exception:
                # Ignore entity update errors in test environments
                pass

            return True
        return False

    async def _update_approval_buttons(self):
        """Trigger updates for all dynamic buttons and sensors"""
        # Update approval status buttons
        if hasattr(self, '_approval_buttons'):
            for button in self._approval_buttons:
                button.async_write_ha_state()

        # Update dynamic claim buttons
        if hasattr(self, '_claim_buttons'):
            for button in self._claim_buttons:
                button.async_write_ha_state()
                
        # Update dynamic approval management buttons
        if hasattr(self, '_approval_manager_buttons'):
            for button in self._approval_manager_buttons:
                button.async_write_ha_state()

        # Update sensors
        if hasattr(self, '_approval_sensors'):
            for sensor in self._approval_sensors:
                sensor.async_write_ha_state()

    def get_pending_approvals(self) -> list[PendingApproval]:
        """Get all pending approval requests"""
        return [a for a in self.model.pending_approvals.values() if a.status == "pending_approval"]

    def get_pending_approval(self, approval_id: str):
        """Get a specific pending approval by ID"""
        if not self.model:
            return None
        return self.model.pending_approvals.get(approval_id)

    # ---- persistent todo items ----
    async def save_todo_item(self, uid: str, summary: str, status: str, kid_id: str, skip_save: bool = False) -> None:
        """Save a todo item to persistent storage"""
        assert self.model
        
        # Remove existing item with same UID
        self.model.todo_items = [item for item in self.model.todo_items if item.uid != uid]
        
        # Add new/updated item
        todo_item = TodoItemModel(
            uid=uid,
            summary=summary,
            status=status,
            kid_id=kid_id
        )
        self.model.todo_items.append(todo_item)
        if not skip_save:
            await self.async_save()

    async def remove_todo_item(self, uid: str) -> None:
        """Remove a todo item from persistent storage"""
        assert self.model
        self.model.todo_items = [item for item in self.model.todo_items if item.uid != uid]
        await self.async_save()

    def get_todo_items_for_kid(self, kid_id: str) -> list[TodoItemModel]:
        """Get all stored todo items for a specific kid"""
        if not self.model:
            return []
        return [item for item in self.model.todo_items if item.kid_id == kid_id]

    def get_todo_item(self, uid: str) -> TodoItemModel | None:
        """Get a specific todo item by UID"""
        if not self.model:
            return None
        for item in self.model.todo_items:
            if item.uid == uid:
                return item
        return None
