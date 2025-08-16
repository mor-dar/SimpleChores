"""Data coordinator for SimpleChores integration."""
from __future__ import annotations
from datetime import datetime
from typing import Dict
from homeassistant.core import HomeAssistant
from .storage import SimpleChoresStore
from .models import StorageModel, LedgerEntry, Kid

class SimpleChoresCoordinator:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.store = SimpleChoresStore(hass)
        self.model: StorageModel | None = None

    async def async_init(self):
        self.model = await self.store.async_load()

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
