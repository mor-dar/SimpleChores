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
    description: str = ""
    create_calendar_event: bool = True
    calendar_duration_hours: int = 2
    
    # Reward requirements (at least one must be specified)
    cost: int | None = None  # Legacy point-based rewards
    required_completions: int | None = None  # Complete X times
    required_streak_days: int | None = None  # Daily streak for X days
    required_chore_type: str | None = None  # Specific chore type for completions/streaks
    
    def is_point_based(self) -> bool:
        """Check if this is a point-based reward."""
        return self.cost is not None
    
    def is_completion_based(self) -> bool:
        """Check if this is a completion-based reward."""
        return self.required_completions is not None
    
    def is_streak_based(self) -> bool:
        """Check if this is a streak-based reward."""
        return self.required_streak_days is not None

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
    chore_type: str | None = None  # For reward tracking (e.g., "trash", "dishes", "bed")

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
    chore_type: str | None = None  # For reward tracking (e.g., "trash", "dishes", "bed")

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
class RewardProgress:
    """Tracks a child's progress towards a specific reward"""
    kid_id: str
    reward_id: str
    
    # Completion tracking
    current_completions: int = 0  # For completion-based rewards
    
    # Streak tracking
    current_streak: int = 0  # Current consecutive days
    last_completion_date: str | None = None  # YYYY-MM-DD format
    
    # Status
    completed: bool = False
    completion_date: float | None = None  # Timestamp when reward was achieved
    
@dataclass
class StorageModel:
    kids: dict[str, Kid] = field(default_factory=dict)
    ledger: list[LedgerEntry] = field(default_factory=list)
    rewards: dict[str, Reward] = field(default_factory=dict)
    pending_chores: dict[str, PendingChore] = field(default_factory=dict)  # key: todo_uid
    recurring_chores: dict[str, RecurringChore] = field(default_factory=dict)  # key: chore_id
    pending_approvals: dict[str, PendingApproval] = field(default_factory=dict)  # key: approval_id
    todo_items: list[TodoItemModel] = field(default_factory=list)  # persistent todo items
    reward_progress: dict[str, RewardProgress] = field(default_factory=dict)  # key: f"{kid_id}_{reward_id}"
