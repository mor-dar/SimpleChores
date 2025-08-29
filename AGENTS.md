# AGENTS.md

This file provides guidance to OpenAI Codex when working with code in this repository.

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

The integration includes comprehensive pytest test coverage:

#### Running Tests
```bash
# Set up test environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements_test.txt

# Run all tests
python -m pytest tests/ -v

# Run specific test files
python -m pytest tests/test_models.py -v
python -m pytest tests/test_coordinator.py -v
python -m pytest tests/test_platforms.py -v
python -m pytest tests/test_integration.py -v
python -m pytest tests/test_config_flow.py -v

# Run with coverage
python -m pytest tests/ --cov=custom_components.simplechores --cov-report=html
```

#### Test Structure
- `tests/test_models.py` - Unit tests for data models (Kid, LedgerEntry, Reward, etc.)
- `tests/test_storage.py` - Tests for HA Store API integration
- `tests/test_coordinator.py` - Tests for core business logic and state management
- `tests/test_platforms.py` - Tests for HA platform entities (number, sensor, text, button)
- `tests/test_config_flow.py` - Integration tests for setup wizard
- `tests/test_integration.py` - End-to-end service tests
- `tests/conftest.py` - Shared test fixtures and configuration

#### Test Coverage
All core functionality is tested including:
- Data model validation and serialization
- Points management and ledger tracking
- Chore creation, completion, and approval workflows
- Reward claiming with calendar integration
- Entity state management and updates
- Service call validation and execution
- Config flow user interactions

#### Testing Best Practices
Following Home Assistant testing guidelines (https://developers.home-assistant.io/docs/development_testing/):

**Entity Testing:**
- Mock `hass` instance and `async_write_ha_state()` for entity tests
- Test entity states through the core state machine when possible
- Use proper async fixtures with `@pytest_asyncio.fixture`

**Integration Testing:**
- Use `async_setup_component` or `async_setup` for integration setup
- Assert states via `hass.states`
- Perform service calls via `hass.services`

**Storage Mocking:**
- Properly mock `Store.async_save` and `Store.async_load` as `AsyncMock`
- Inject mock stores into coordinator fixtures
- Test data persistence and state management

### Code Quality & Linting

#### Ruff Configuration
The project uses ruff for fast Python linting configured in `pyproject.toml`:

```bash
# Check for linting issues
ruff check custom_components/SimpleChores/ tests/

# Auto-fix issues
ruff check --fix custom_components/SimpleChores/ tests/

# Format code
ruff format custom_components/SimpleChores/ tests/
```

#### Standards
- PEP 8 compliance with 120 character line limit
- Modern Python type hints (`str | None` instead of `Optional[str]`)
- Home Assistant coding conventions
- Import sorting and organization
- Consistent code formatting

Home Assistant development can also use:
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