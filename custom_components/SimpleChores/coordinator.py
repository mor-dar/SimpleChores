"""Data coordinator for SimpleChores integration."""
from __future__ import annotations
from datetime import datetime
import uuid
from typing import List
from homeassistant.core import HomeAssistant
from .storage import SimpleChoresStore
from .models import StorageModel, LedgerEntry, Kid, Reward, PendingChore

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
        return self.model.kids.get(kid_id, Kid(id=kid_id, name=kid_id)).points

    async def add_points(self, kid_id: str, amount: int, reason: str, kind: str = "earn"):
        assert self.model
        if kid_id not in self.model.kids:
            self.model.kids[kid_id] = Kid(id=kid_id, name=kid_id)
        self.model.kids[kid_id].points += amount
        self.model.ledger.append(
            LedgerEntry(ts=datetime.now().timestamp(), kid_id=kid_id, delta=amount, reason=reason, kind=kind)
        )
        await self.async_save()

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

    def get_rewards(self) -> List[Reward]:
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
