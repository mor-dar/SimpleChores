# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SimpleChores is a Home Assistant custom integration for managing kids' chores, points, and rewards. It creates a simple family chore management system with per-child point balances, recurring chores, and rewards.

## Architecture

The integration follows Home Assistant custom component patterns:

- **Domain**: `simplechores` (defined in manifest.json)
- **Platforms**: `number`, `todo`, `sensor`, `text`, `button` entities for per-child functionality
- **Config Flow**: User setup wizard for adding children and configuring calendars/todo lists
- **Data Coordinator**: Manages data updates and state synchronization
- **Storage**: Uses HA Store API (v2) for persistent ledger/history in `.storage`
- **Services**: Custom services for points management, chore creation, and reward claiming

### Key Components

- `number.py`: Per-child points balance entities (`number.<kid>_points`)
- `todo.py`: Optional to-do list entities per child (`todo.<kid>_chores`)
- `sensor.py`: Weekly and total points sensors (`sensor.<kid>_points_week`, `sensor.<kid>_points_total`)
- `text.py`: Input helper entities for dashboard chore creation
- `button.py`: Action buttons for chore creation and reward claiming
- `coordinator.py`: Data coordination with rewards and chore tracking
- `storage.py`: Persistent data handling via HA Store API
- `models.py`: Data models for kids, chores, rewards, ledger entries, and pending chores
- `config_flow.py`: Setup wizard for integration configuration

### Services Architecture

All services use the `simplechores` domain:
- `add_points` / `remove_points`: Points management with validation schemas
- `create_adhoc_chore`: One-time chore creation with point tracking via PendingChore system
- `complete_chore`: Marks chore done and awards points (supports both `chore_id` and `todo_uid`)
- `claim_reward`: Deducts points and optionally creates calendar events using reward definitions
- `log_parent_chore`: Adds parent chores to shared calendar with error handling

### Rewards System

- Default rewards: Movie Night (20pts), Extra Allowance (25pts), Park Trip (30pts), Ice Cream (15pts)
- Configurable calendar event creation with duration settings
- Automatic point validation and deduction
- Extensible reward definitions stored in coordinator

## Installation & Development

This is a Home Assistant custom component that goes in `config/custom_components/simplechores/`.

### Testing
Home Assistant development typically uses:
- `hass --script check_config` for configuration validation
- HA test framework for integration testing
- Manual testing within a Home Assistant instance

### Integration Patterns

The integration follows these HA patterns:
- Async/await throughout
- Config entries for user configuration
- Entity platforms for device representation
- Service registration via `async_register`
- Event firing for state changes

## Recurring Chores System

Two supported automation patterns:
1. **Schedule → To-do**: HA Schedule helpers trigger automations to create chores
2. **Calendar → To-do**: Integration syncs calendar events (RRULE) to to-do items

Both patterns use the blueprints in `blueprints/automation/` for user setup.

## Dashboard Integration

Ships with prebuilt Lovelace dashboard (`dashboard/simplechores-view.yaml`) using core HA cards:
- Number entities with increment/decrement buttons for points balances
- Weekly and total points tracking sensors
- To-do list cards per child with automatic point awards
- Text input helpers for ad-hoc chore creation (title, points, kid selection)
- Button entities for chore creation and reward claiming
- Rewards section with per-kid reward buttons (disabled when insufficient points)
- Parents' calendar display for family events

## Data Storage

Uses HA's Store API (version 2) for:
- Points ledger (transactions with timestamps, reasons, and categories)
- Pending chores tracking (UUID-based with point values)
- Reward definitions (title, cost, description, calendar settings)
- Kid profiles and point balances
- Persistent state across HA restarts with automatic migration