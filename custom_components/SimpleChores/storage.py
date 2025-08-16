"""Storage utilities for SimpleChores integration."""
from __future__ import annotations
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from .const import STORAGE_KEY, STORAGE_VERSION
from .models import StorageModel, Kid, LedgerEntry, Reward, PendingChore
from typing import Any, Dict, List

class SimpleChoresStore:
    def __init__(self, hass: HomeAssistant):
        self._store: Store[dict] = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self) -> StorageModel:
        data = await self._store.async_load() or {}
        kids = {k: Kid(**v) for k, v in data.get("kids", {}).items()}
        ledger = [LedgerEntry(**e) for e in data.get("ledger", [])]
        rewards = {k: Reward(**v) for k, v in data.get("rewards", {}).items()}
        pending_chores = {k: PendingChore(**v) for k, v in data.get("pending_chores", {}).items()}
        return StorageModel(kids=kids, ledger=ledger, rewards=rewards, pending_chores=pending_chores)

    async def async_save(self, model: StorageModel) -> None:
        data = {
            "kids": {k: vars(v) for k, v in model.kids.items()},
            "ledger": [vars(e) for e in model.ledger],
            "rewards": {k: vars(v) for k, v in model.rewards.items()},
            "pending_chores": {k: vars(v) for k, v in model.pending_chores.items()},
        }
        await self._store.async_save(data)
