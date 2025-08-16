# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SimpleChores is a Home Assistant custom integration for managing kids' chores, points, and rewards. It creates a simple family chore management system with per-child point balances, recurring chores, and rewards.

## Architecture

The integration follows Home Assistant custom component patterns:

- **Domain**: `simplechores` (defined in manifest.json)
- **Platforms**: `number`, `todo`, `sensor` entities for per-child functionality
- **Config Flow**: User setup wizard for adding children and configuring calendars/todo lists
- **Data Coordinator**: Manages data updates and state synchronization
- **Storage**: Uses HA Store API for persistent ledger/history in `.storage`
- **Services**: Custom services for points management, chore creation, and reward claiming

### Key Components

- `number.py`: Per-child points balance entities (`number.<kid>_points`)
- `todo.py`: Optional to-do list entities per child (`todo.<kid>_chores`)
- `sensor.py`: Summary sensors (planned: weekly/total points)
- `coordinator.py`: Data coordination and state management
- `storage.py`: Persistent data handling via HA Store API
- `models.py`: Data models for chores, rewards, and transactions
- `config_flow.py`: Setup wizard for integration configuration

### Services Architecture

All services use the `simplechores` domain:
- `add_points` / `remove_points`: Points management
- `create_adhoc_chore`: One-time chore creation
- `complete_chore`: Marks chore done and awards points
- `claim_reward`: Deducts points and creates calendar events
- `log_parent_chore`: Adds parent chores to shared calendar

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
- Number entities for points balances
- To-do list cards per child
- Input helpers for ad-hoc chore creation
- Rewards claiming interface
- Parents' calendar display

## Data Storage

Uses HA's Store API for:
- Points ledger (transactions with reasons)
- Chore history
- Reward definitions and claims
- Persistent state across HA restarts