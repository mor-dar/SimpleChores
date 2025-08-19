"""Storage utilities for SimpleChores integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION
from .models import Kid, LedgerEntry, PendingChore, Reward, StorageModel, TodoItemModel


class SimpleChoresStore:
    def __init__(self, hass: HomeAssistant):
        self._store: Store[dict] = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self) -> StorageModel:
        data = await self._store.async_load() or {}
        kids = {k: Kid(**v) for k, v in data.get("kids", {}).items()}
        ledger = [LedgerEntry(**e) for e in data.get("ledger", [])]
        rewards = {k: Reward(**v) for k, v in data.get("rewards", {}).items()}
        pending_chores = {k: PendingChore(**v) for k, v in data.get("pending_chores", {}).items()}
        # Handle missing fields for backwards compatibility
        from .models import RecurringChore, PendingApproval
        recurring_chores = {k: RecurringChore(**v) for k, v in data.get("recurring_chores", {}).items()}
        pending_approvals = {k: PendingApproval(**v) for k, v in data.get("pending_approvals", {}).items()}
        todo_items = [TodoItemModel(**e) for e in data.get("todo_items", [])]
        return StorageModel(
            kids=kids, 
            ledger=ledger, 
            rewards=rewards, 
            pending_chores=pending_chores,
            recurring_chores=recurring_chores,
            pending_approvals=pending_approvals,
            todo_items=todo_items
        )

    async def async_save(self, model: StorageModel) -> None:
        data = {
            "kids": {k: vars(v) for k, v in model.kids.items()},
            "ledger": [vars(e) for e in model.ledger],
            "rewards": {k: vars(v) for k, v in model.rewards.items()},
            "pending_chores": {k: vars(v) for k, v in model.pending_chores.items()},
            "recurring_chores": {k: vars(v) for k, v in model.recurring_chores.items()},
            "pending_approvals": {k: vars(v) for k, v in model.pending_approvals.items()},
            "todo_items": [vars(e) for e in model.todo_items],
        }
        await self._store.async_save(data)
