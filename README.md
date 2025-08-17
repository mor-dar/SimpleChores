# SimpleChores – Simple Chore & Reward Management for Home Assistant

**SimpleChores** is a lightweight Home Assistant custom integration for managing kids’ chores, points, and rewards – without the overhead of heavy templates or complicated dashboards.

It’s designed for simplicity, transparency, and family-friendly dashboards.  
Each child gets a points balance, chores can be recurring or ad-hoc, and parents’ chores can be added to a calendar to model teamwork.

---

## ✨ Features

- **Per-kid points balance**  
  Each child has a `number` entity (`number.simplechores_alex_points`, `number.simplechores_emma_points`) with easy add/remove buttons.

- **Chores → Points**  
  - Recurring chores (daily/weekly) using HA **Schedules** or **Calendars**.  
  - Ad-hoc chores: one-time tasks created from the dashboard.  
  - To-do list integration: chores appear in kids’ To-do lists, checked off when done.

- **Rewards system**  
  Define rewards with a point cost. Claiming a reward deducts points and (optionally) creates a calendar event (“Movie night”, “Trip to park”).

- **Parents’ chores**  
  Log parent chores into a shared calendar to show kids that chores are for everyone.

- **Dashboards included**  
  Ships with a prebuilt Lovelace view using only core cards (no custom JS).  
  - Kids’ points  
  - Chore To-dos  
  - Ad-hoc chore creator  
  - Rewards and parents’ calendar

- **Simple history/ledger**  
  Integration stores a JSON ledger under `.storage` for basic “earned/spent” tracking.

---

## 📦 Installation

1. Copy this repository into `config/custom_components/simplechores/`.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration → simplechores**.
4. Follow the config flow to:
   - Add children’s names.
   - Pick whether to use Local To-do lists.
   - Select a calendar for parents’ chores (Local or Google, RW enabled).

---

## ⚙️ Entities

### Numbers
- `number.simplechores_<kid>_points` – current points balance per child.

### To-do lists (optional)
- `todo.simplechores_todo_<kid>` – if enabled, integration exposes a To-do list entity per child.

### Sensors
- `sensor.simplechores_<kid>_points_week` – points earned this week
- `sensor.simplechores_<kid>_points_total` – total points earned all-time

### Dashboard Helpers
- `text.simplechores_chore_title_input` – chore title input
- `text.simplechores_chore_points_input` – points value input
- `text.simplechores_chore_kid_input` – kid selection input
- `button.simplechores_create_chore_button` – create chore action
- `button.simplechores_reward_*` – reward claim buttons per kid

---

## 🛠️ Services

All services are under the `simplechores` domain:

- `simplechores.add_points`
  - `kid`: child name/id  
  - `amount`: integer  
  - `reason` (optional)

- `simplechores.remove_points`
  - Same fields as `add_points`.

- `simplechores.create_adhoc_chore`
  - `kid`: child  
  - `title`: string  
  - `points`: integer  
  - `due`: datetime (optional)

- `simplechores.complete_chore`
  - `kid`: child  
  - `chore_id`: To-do item ID

- `simplechores.claim_reward`
  - `kid`: child  
  - `reward_id`: defined in config  
  - Deducts cost, logs event, and (optionally) creates a calendar entry.

- `simplechores.log_parent_chore`
  - `title`: string  
  - `start`, `end`: datetime  
  - `all_day`: bool

---

## 📅 Recurring chores

Two supported patterns:

### A. Schedule → To-do
Use HA’s **Schedule helper**.  
Example: “Every day 7–8 PM” triggers a simplechores automation to add chores.

### B. Calendar → To-do
Maintain a Local or Google calendar with recurring events (RRULE). Integration syncs each event to a To-do item. Kids check it off when done, and points are awarded.

---

## 📋 Dashboards

A ready-to-use Lovelace view is included:

- **Kids’ balances**: tile cards for each `number.kid_points`.  
- **To-do cards**: per-kid chores lists.  
- **Ad-hoc creator**: `input_text` + `number` + button to spawn a new chore.  
- **Rewards**: claim buttons with point costs.  
- **Parents’ calendar**: built-in Calendar card.

---

## 🧑‍💻 Development

This integration follows HA best practices:
- Platforms: `number/`, `todo/`, `sensor/`, `text/`, `button/`  
- Services: registered via `async_register` with voluptuous schemas
- Storage: HA `Store` API v2 for ledger/history with data models

### Testing

The project includes comprehensive unit and integration tests using pytest:

```bash
# Set up development environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements_test.txt

# Run all tests
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_models.py -v  # Unit tests for data models
python -m pytest tests/test_coordinator.py -v  # Coordinator logic tests
python -m pytest tests/test_integration.py -v  # Service integration tests

# Run tests with coverage
python -m pytest tests/ --cov=custom_components.simplechores --cov-report=html
```

### Code Quality & Linting

The project uses ruff for fast Python linting and formatting:

```bash
# Install ruff (if not already installed)
pip install ruff

# Check code for linting issues
ruff check custom_components/SimpleChores/ tests/

# Auto-fix issues where possible
ruff check --fix custom_components/SimpleChores/ tests/

# Format code
ruff format custom_components/SimpleChores/ tests/
```

All code follows:
- PEP 8 style guidelines
- Home Assistant coding conventions
- Type hints with modern Python syntax (`str | None` instead of `Optional[str]`)
- Maximum line length of 120 characters

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting: `pytest tests/ && ruff check .`
5. Submit a pull request

Scaffold created with [cookiecutter-homeassistant-custom-component](https://github.com/oncleben31/cookiecutter-homeassistant-custom-component).

---

## 🚀 Roadmap / TODO

- [x] **Weekly/monthly summary sensors** – ✅ Implemented (`sensor.<kid>_points_week`, `sensor.<kid>_points_total`)
- [x] **Rewards system** – ✅ Implemented with default rewards and calendar integration
- [x] **Dashboard input helpers** – ✅ Implemented with text inputs and action buttons
- [ ] **Config UI for rewards** (currently uses default rewards, could add config flow step)
- [ ] **Ledger dashboard** (history of points earned/spent with reasons)
- [ ] **Mobile-friendly dashboard pack** (Mushroom UI optional)
- [ ] **Import tool** for KidsChores users
- [ ] **Advanced rewards** (badges, streaks, achievements – optional add-on)

---

## 📄 License

Choose the license that fits your goals:  
- **MIT** (permissive, closed-source forks allowed), or  
- **Apache 2.0** (permissive, with patent grant), or  
- **GPL-3.0** (copyleft, if you want derivatives to remain open).

---

## 🙌 Credits

- Inspired by [KidsChores HA integration](https://github.com/ad-ha/kidschores-ha).  
- Built on modern [Home Assistant](https://www.home-assistant.io/) (tested on 2025.8.x).  
- Thanks to the HA community for the To-do and Calendar building blocks.

