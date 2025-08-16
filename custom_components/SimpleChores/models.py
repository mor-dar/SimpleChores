"""Data models for SimpleChores integration."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime

@dataclass
class Kid:
    id: str
    name: str
    points: int = 0

@dataclass
class LedgerEntry:
    ts: float
    kid_id: str
    delta: int
    reason: str
    kind: str  # "earn" | "spend" | "adjust"

@dataclass
class Reward:
    id: str
    title: str
    cost: int
    description: str = ""
    create_calendar_event: bool = True
    calendar_duration_hours: int = 2

@dataclass
class PendingChore:
    """Tracks chores created via create_adhoc_chore with their point values"""
    todo_uid: str
    kid_id: str
    title: str
    points: int
    created_ts: float

@dataclass
class StorageModel:
    kids: Dict[str, Kid] = field(default_factory=dict)
    ledger: List[LedgerEntry] = field(default_factory=list)
    rewards: Dict[str, Reward] = field(default_factory=dict)
    pending_chores: Dict[str, PendingChore] = field(default_factory=dict)  # key: todo_uid
