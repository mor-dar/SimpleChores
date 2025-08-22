"""Diagnostics support for SimpleChores integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SimpleChoresCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: SimpleChoresCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    if not coordinator.model:
        return {"error": "Coordinator model not initialized"}

    # Calculate some useful statistics
    total_points_earned = sum(
        ledger_entry.delta 
        for ledger_entry in coordinator.model.ledger 
        if ledger_entry.delta > 0
    )
    
    total_points_spent = sum(
        abs(ledger_entry.delta) 
        for ledger_entry in coordinator.model.ledger 
        if ledger_entry.delta < 0
    )
    
    # Get recent activity (last 10 ledger entries)
    recent_activity = []
    for ledger_entry in coordinator.model.ledger[-10:]:
        recent_activity.append({
            "timestamp": ledger_entry.ts,
            "kid_id": ledger_entry.kid_id,
            "delta": ledger_entry.delta,
            "reason": ledger_entry.reason,
            "kind": ledger_entry.kind
        })
    
    # Count items by status
    pending_chores_by_status = {}
    for chore in coordinator.model.pending_chores.values():
        status = chore.status
        pending_chores_by_status[status] = pending_chores_by_status.get(status, 0) + 1
    
    approvals_by_status = {}
    for approval in coordinator.model.pending_approvals.values():
        status = approval.status
        approvals_by_status[status] = approvals_by_status.get(status, 0) + 1

    return {
        "integration_version": "1.3.0",
        "config_data": {
            "kids": entry.data.get("kids", ""),
            "use_todo": entry.data.get("use_todo", True),
            "has_parents_calendar": bool(entry.data.get("parents_calendar"))
        },
        "statistics": {
            "total_kids": len(coordinator.model.kids),
            "total_ledger_entries": len(coordinator.model.ledger),
            "total_points_earned": total_points_earned,
            "total_points_spent": total_points_spent,
            "total_rewards": len(coordinator.model.rewards),
            "pending_chores_count": len(coordinator.model.pending_chores),
            "pending_chores_by_status": pending_chores_by_status,
            "pending_approvals_count": len(coordinator.model.pending_approvals),
            "approvals_by_status": approvals_by_status,
            "recurring_chores": len(coordinator.model.recurring_chores),
            "persistent_todo_items": len(coordinator.model.todo_items)
        },
        "kids_summary": {
            kid.id: {
                "name": kid.name,
                "current_points": kid.points,
                "points_earned": sum(
                    ledger_entry.delta for ledger_entry in coordinator.model.ledger 
                    if ledger_entry.kid_id == kid.id and ledger_entry.delta > 0
                ),
                "points_spent": sum(
                    abs(ledger_entry.delta) for ledger_entry in coordinator.model.ledger 
                    if ledger_entry.kid_id == kid.id and ledger_entry.delta < 0
                )
            }
            for kid in coordinator.model.kids.values()
        },
        "recent_activity": recent_activity,
        "entity_registry": {
            "has_number_entities": hasattr(coordinator, '_entities'),
            "has_todo_entities": hasattr(coordinator, '_todo_entities'),
            "has_approval_buttons": hasattr(coordinator, '_approval_buttons'),
            "registered_entities_count": len(getattr(coordinator, '_entities', {}))
        },
        "storage_status": {
            "model_loaded": coordinator.model is not None,
            "storage_version": coordinator.store._store.version,
            "storage_key": coordinator.store._store.key
        }
    }