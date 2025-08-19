"""Data coordinator for SimpleChores integration."""
from __future__ import annotations

from datetime import datetime
import uuid

from homeassistant.core import HomeAssistant

from .models import Kid, LedgerEntry, PendingApproval, PendingChore, RecurringChore, Reward, StorageModel, TodoItemModel
from .storage import SimpleChoresStore


class SimpleChoresCoordinator:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.store = SimpleChoresStore(hass)
        self.model: StorageModel | None = None

    async def async_init(self):
        self.model = await self.store.async_load()
        # Add default rewards if none exist
        if not self.model.rewards:
            await self._add_default_rewards()

    async def async_save(self):
        await self.store.async_save(self.model)

    # ---- kids/points ----
    async def ensure_kid(self, kid_id: str, name: str | None = None):
        assert self.model
        if kid_id not in self.model.kids:
            self.model.kids[kid_id] = Kid(id=kid_id, name=name or kid_id)
            await self.async_save()

    def get_points(self, kid_id: str) -> int:
        if not self.model:
            return 0
        if kid_id not in self.model.kids:
            return 0
        return self.model.kids[kid_id].points

    async def add_points(self, kid_id: str, amount: int, reason: str, kind: str = "earn"):
        assert self.model
        if kid_id not in self.model.kids:
            self.model.kids[kid_id] = Kid(id=kid_id, name=kid_id)
        self.model.kids[kid_id].points += amount
        self.model.ledger.append(
            LedgerEntry(ts=datetime.now().timestamp(), kid_id=kid_id, delta=amount, reason=reason, kind=kind)
        )
        await self.async_save()
        # Trigger entity updates
        await self._update_entities(kid_id)

    async def remove_points(self, kid_id: str, amount: int, reason: str, kind: str = "spend"):
        await self.add_points(kid_id, -abs(amount), reason, kind)

    # ---- rewards ----
    async def _add_default_rewards(self):
        """Add some default rewards for demo purposes"""
        default_rewards = [
            Reward(id="movie_night", title="Family Movie Night", cost=20, description="Pick tonight's movie"),
            Reward(id="extra_allowance", title="Extra $5 Allowance", cost=25, description="Bonus money", create_calendar_event=False),
            Reward(id="trip_park", title="Trip to the Park", cost=30, description="Special outing", calendar_duration_hours=3),
            Reward(id="ice_cream", title="Ice Cream Trip", cost=15, description="Sweet treat outing", calendar_duration_hours=1),
        ]
        for reward in default_rewards:
            self.model.rewards[reward.id] = reward
        await self.async_save()

    def get_rewards(self) -> list[Reward]:
        return list(self.model.rewards.values())

    def get_reward(self, reward_id: str) -> Reward | None:
        return self.model.rewards.get(reward_id)

    async def add_reward(self, title: str, cost: int, description: str = "", create_calendar_event: bool = True) -> str:
        reward_id = str(uuid.uuid4())[:8]
        reward = Reward(id=reward_id, title=title, cost=cost, description=description, create_calendar_event=create_calendar_event)
        self.model.rewards[reward_id] = reward
        await self.async_save()
        return reward_id

    # ---- chores ----
    async def create_pending_chore(self, kid_id: str, title: str, points: int) -> str:
        """Create a chore and return the todo_uid to track it"""
        todo_uid = str(uuid.uuid4())
        chore = PendingChore(
            todo_uid=todo_uid,
            kid_id=kid_id,
            title=title,
            points=points,
            created_ts=datetime.now().timestamp()
        )
        self.model.pending_chores[todo_uid] = chore
        await self.async_save()
        return todo_uid

    async def complete_chore_by_uid(self, todo_uid: str) -> bool:
        """Complete a chore by todo UID and award points"""
        if todo_uid in self.model.pending_chores:
            chore = self.model.pending_chores.pop(todo_uid)
            await self.add_points(chore.kid_id, chore.points, f"Chore: {chore.title}", "earn")
            await self.async_save()
            return True
        return False

    def get_pending_chore(self, todo_uid: str) -> PendingChore | None:
        return self.model.pending_chores.get(todo_uid)

    async def _update_entities(self, kid_id: str):
        """Trigger entity updates after point changes"""
        import logging
        _LOGGER = logging.getLogger(__name__)

        _LOGGER.debug(f"SimpleChores: Triggering entity updates for {kid_id}")

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
            _LOGGER.debug(f"SimpleChores: Updated entity state for {kid_id}")
        else:
            if hasattr(self, '_entities'):
                _LOGGER.warning(f"SimpleChores: No entity found for {kid_id}. Available: {list(self._entities.keys())}")
            else:
                _LOGGER.warning("SimpleChores: No entities registered yet")

        # Fallback: trigger entity update via service
        entity_id = f"number.{kid_id}_points"
        try:
            await self.hass.services.async_call("homeassistant", "update_entity", {"entity_id": entity_id}, blocking=False)
        except Exception as e:
            _LOGGER.debug(f"SimpleChores: Fallback update failed: {e}")

    # ---- recurring chores ----
    async def create_recurring_chore(self, kid_id: str, title: str, points: int, schedule_type: str, day_of_week: int = None) -> str:
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
            enabled=True
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
                todo_uid = await self.create_pending_chore(chore.kid_id, chore.title, chore.points)
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
                todo_uid = await self.create_pending_chore(chore.kid_id, chore.title, chore.points)
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

            # Update approval buttons
            await self._update_approval_buttons()

            return approval_id
        return None

    async def approve_chore(self, approval_id: str) -> bool:
        """Approve a pending chore and award points"""
        assert self.model

        if approval_id in self.model.pending_approvals:
            approval = self.model.pending_approvals[approval_id]

            # Award points
            await self.add_points(approval.kid_id, approval.points, f"Approved: {approval.title}", "earn")

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

            # Update approval buttons
            await self._update_approval_buttons()

            return True
        return False

    async def _update_approval_buttons(self):
        """Trigger updates for approval status buttons and sensors"""
        if hasattr(self, '_approval_buttons'):
            for button in self._approval_buttons:
                button.async_write_ha_state()

        if hasattr(self, '_approval_sensors'):
            for sensor in self._approval_sensors:
                sensor.async_write_ha_state()

    def get_pending_approvals(self) -> list[PendingApproval]:
        """Get all pending approval requests"""
        return [a for a in self.model.pending_approvals.values() if a.status == "pending_approval"]

    # ---- persistent todo items ----
    async def save_todo_item(self, uid: str, summary: str, status: str, kid_id: str) -> None:
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
