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
class StorageModel:
    kids: Dict[str, Kid] = field(default_factory=dict)
    ledger: List[LedgerEntry] = field(default_factory=list)
