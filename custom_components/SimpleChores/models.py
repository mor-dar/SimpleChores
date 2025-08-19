"""Data models for SimpleChores integration."""
from __future__ import annotations

from dataclasses import dataclass, field
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
    status: str = "pending"  # "pending" | "completed" | "approved" | "rejected"
    completed_ts: float | None = None
    approved_ts: float | None = None

@dataclass
class RecurringChore:
    """Defines a recurring chore template"""
    id: str
    title: str
    points: int
    kid_id: str
    schedule_type: str  # "daily" | "weekly"
    day_of_week: int | None = None  # 0=Monday, 6=Sunday (for weekly chores)
    enabled: bool = True
    created_ts: float = field(default_factory=lambda: datetime.now().timestamp())

@dataclass
class PendingApproval:
    """Tracks chores waiting for parental approval"""
    id: str
    todo_uid: str
    kid_id: str
    title: str
    points: int
    completed_ts: float
    status: str = "pending_approval"  # "pending_approval" | "approved" | "rejected"

@dataclass
class TodoItemModel:
    """Serializable representation of a TodoItem for storage"""
    uid: str
    summary: str
    status: str  # "needs_action" | "completed"
    kid_id: str  # Which kid this todo item belongs to
    created_ts: float = field(default_factory=lambda: datetime.now().timestamp())

@dataclass
class StorageModel:
    kids: dict[str, Kid] = field(default_factory=dict)
    ledger: list[LedgerEntry] = field(default_factory=list)
    rewards: dict[str, Reward] = field(default_factory=dict)
    pending_chores: dict[str, PendingChore] = field(default_factory=dict)  # key: todo_uid
    recurring_chores: dict[str, RecurringChore] = field(default_factory=dict)  # key: chore_id
    pending_approvals: dict[str, PendingApproval] = field(default_factory=dict)  # key: approval_id
    todo_items: list[TodoItemModel] = field(default_factory=list)  # persistent todo items
