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
  Define rewards with point costs or completion/streak requirements. Traditional point-based rewards deduct points and create calendar events. New completion-based rewards track progress toward goals like "Take out trash 10 times" or "Make bed every day for 1 week".

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

### Option 1: HACS (Recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed
2. In HACS, go to **Integrations**
3. Click the **⋮** menu → **Custom repositories**
4. Add this repository URL: `https://github.com/mor-dar/SimpleChores`
5. Select **Integration** as the category
6. Click **Add**
7. Find "SimpleChores" in HACS and click **Download**
8. Restart Home Assistant
9. Go to **Settings → Devices & Services → Add Integration → SimpleChores**

### Option 2: Manual Installation

1. Copy this repository into `config/custom_components/simplechores/`
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration → SimpleChores**

### Configuration

After installation, follow the config flow to:
- Add children's names
- Pick whether to use Local To-do lists (`use_todo: true/false`)
- Select a calendar for parents' chores (Local or Google, RW enabled)

#### Todo Mode vs Button Mode

**Todo Mode (Default)**: Each child gets todo list entities for chore management with approval workflow  
**Button Mode**: Uses buttons and sensors for chore creation and direct approval (no todo lists)

---

## ⚙️ Entities

### Numbers
- `number.simplechores_<kid>_points` – current points balance per child.

### To-do lists (optional)
- `todo.simplechores_todo_<kid>` – if enabled, integration exposes a To-do list entity per child.

### Sensors
- `sensor.simplechores_<kid>_points_week` – points earned this week
- `sensor.simplechores_<kid>_points_total` – total points earned all-time
- `sensor.simplechores_<reward_id>_progress_<kid>` – progress toward completion-based rewards

### Buttons
- `button.simplechores_create_chore_button` – create ad-hoc chore action
- `button.simplechores_create_recurring_button` – create recurring chore action
- `button.simplechores_generate_daily_button` – generate today's recurring chores
- `button.simplechores_<reward_id>_reward_<kid>` – reward claim buttons per kid
- `button.simplechores_approve_<approval_id>` – approve pending chores
- `button.simplechores_reject_<approval_id>` – reject pending chores
- `button.simplechores_approval_status_button` – show pending approvals count
- `button.simplechores_reset_rejected_button` – reset rejected chores to pending

### Text Input Helpers
- `text.simplechores_chore_title_input` – chore title input (starts empty)
- `text.simplechores_chore_points_input` – points value input
- `text.simplechores_chore_kid_input` – kid selection input
- `text.simplechores_recurring_title_input` – recurring chore title
- `text.simplechores_recurring_points_input` – recurring chore points
- `text.simplechores_recurring_kid_input` – recurring chore kid selection
- `text.simplechores_recurring_schedule_input` – schedule type (daily/weekly)
- `text.simplechores_recurring_day_input` – day of week for weekly chores

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
  - `chore_type`: string (optional) - for reward progress tracking
  - `due`: datetime (optional)

- `simplechores.create_recurring_chore`
  - `kid`: child
  - `title`: string
  - `points`: integer
  - `schedule_type`: "daily" or "weekly"
  - `day_of_week`: integer (0-6, required for weekly)
  - `chore_type`: string (optional) - for reward progress tracking

- `simplechores.generate_recurring_chores`
  - `schedule_type`: "daily" or "weekly" (optional)

- `simplechores.approve_chore`
  - `approval_id`: pending approval ID

- `simplechores.reject_chore`
  - `approval_id`: pending approval ID
  - `reason`: string (optional)

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

- **Kids' balances**: tile cards for each `number.kid_points`.  
- **To-do cards**: per-kid chores lists (Todo Mode).  
- **Ad-hoc creator**: `input_text` + `number` + button to spawn a new chore.  
- **Rewards**: claim buttons with point costs.  
- **Parents' calendar**: built-in Calendar card.

### Button Mode Dashboard (Todo Disabled)

When `use_todo: false`, the dashboard uses button-based chore management:

#### Per-Child Chore Management
```yaml
type: entities
title: "Alice's Chores"
entities:
  - entity: number.simplechores_alice_points
    name: "Current Points"
  - entity: sensor.simplechores_alice_points_week
    name: "This Week"
  - entity: sensor.simplechores_alice_points_total
    name: "Total Earned"
  - type: divider
  - entity: text.simplechores_alice_chore_title
    name: "New Chore Title"
  - entity: number.simplechores_alice_chore_points
    name: "Point Value"
  - entity: button.simplechores_alice_create_chore
    name: "Create Chore"
  # Approval buttons appear here dynamically
```

#### Reward System (Both Modes)
```yaml
type: entities
title: "Rewards - Alice"
entities:
  # Point-based rewards
  - entity: button.simplechores_movie_night_reward_alice
    name: "Movie Night (20 pts)"
  - entity: button.simplechores_extra_allowance_reward_alice  
    name: "Extra Allowance (25 pts)"
  # Completion-based rewards with progress
  - entity: sensor.simplechores_trash_master_progress_alice
    name: "Trash Master Progress"
  - entity: button.simplechores_trash_master_reward_alice
    name: "Trash Master Badge"
  # Streak-based rewards with progress  
  - entity: sensor.simplechores_bed_streak_progress_alice
    name: "Perfect Week Progress"
  - entity: button.simplechores_bed_streak_reward_alice
    name: "Perfect Week - Bed Made"
```

## 🎯 Button Mode Workflows

### Working Without Todo Lists

When `use_todo: false`, SimpleChores operates in Button Mode with these workflows:

#### 1. Creating Chores
```yaml
# Manual chore creation via dashboard
1. Enter chore title in: text.simplechores_alice_chore_title
2. Set point value in: number.simplechores_alice_chore_points  
3. Click: button.simplechores_alice_create_chore
4. Approval button appears automatically

# Via automation/service
service: simplechores.create_adhoc_chore
data:
  kid: "alice"
  title: "Clean bedroom"
  points: 10
  chore_type: "room"  # Optional: for reward progress tracking
```

#### 2. Completing & Approving Chores
```yaml
# Direct service completion (bypasses todo workflow)
service: simplechores.complete_chore
data:
  chore_id: "unique-chore-id"

# Manual approval from dashboard
# Click the dynamically generated approval button:
# "Approve: Clean bedroom (Alice, 10pts)"

# Service-based approval
service: simplechores.approve_chore
data:
  approval_id: "approval-uuid"
```

#### 3. Automation Examples

**Create morning chores automatically:**
```yaml
automation:
  - alias: "Morning Chores - Alice"
    trigger:
      platform: time
      at: "07:00:00"
    action:
      - service: simplechores.create_adhoc_chore
        data:
          kid: "alice"
          title: "Make bed"
          points: 5
          chore_type: "bed"  # Tracks toward bed-making rewards
      - service: simplechores.create_adhoc_chore
        data:
          kid: "alice"  
          title: "Brush teeth"
          points: 2
          chore_type: "hygiene"
```

**Auto-approve low-point chores:**
```yaml
automation:
  - alias: "Auto-approve simple chores"
    trigger:
      platform: event
      event_type: simplechores_chore_completed
    condition:
      condition: template
      value_template: "{{ trigger.event.data.points <= 3 }}"
    action:
      service: simplechores.approve_chore
      data:
        approval_id: "{{ trigger.event.data.approval_id }}"
```

**Sensor-based chore completion:**
```yaml
automation:
  - alias: "Bed made sensor"
    trigger:
      platform: state
      entity_id: binary_sensor.alice_bed_sensor
      to: "on"
    action:
      service: simplechores.complete_chore
      data:
        chore_id: "daily-make-bed-alice"
```

#### 4. Advanced Button Mode Patterns

**Family chore rotation:**
```yaml
automation:
  - alias: "Rotate weekly chores"
    trigger:
      platform: time
      at: "00:00:00"
      weekday:
        - mon
    action:
      - service: simplechores.create_adhoc_chore
        data:
          kid: "{{ ['alice', 'bob'] | random }}"
          title: "Take out trash"
          points: 8
          chore_type: "trash"  # Tracks toward trash master reward
      - service: simplechores.create_adhoc_chore
        data:
          kid: "{{ ['alice', 'bob'] | random }}"
          title: "Load dishwasher"
          points: 6
          chore_type: "dishes"  # Tracks toward dish hero reward
```

**Conditional point bonuses:**
```yaml
automation:
  - alias: "Weekend bonus points"
    trigger:
      platform: event
      event_type: simplechores_chore_approved
    condition:
      condition: time
      weekday:
        - sat
        - sun
    action:
      service: simplechores.add_points
      data:
        kid: "{{ trigger.event.data.kid_id }}"
        amount: 2
        reason: "Weekend bonus"
```

#### 5. Monitoring & Management

**Check pending approvals:**
```yaml
# Template sensor to count pending approvals
sensor:
  - platform: template
    sensors:
      alice_pending_approvals:
        friendly_name: "Alice Pending Approvals"
        value_template: >
          {{ states | selectattr('entity_id', 'match', 'button.simplechores_approve_.*') | list | count }}

# Use the built-in approval status button
button.simplechores_approval_status_button  # Shows count in name, press to list all pending
```

**Reset rejected chores:**
```yaml
# Use the built-in reset button or service
button.simplechores_reset_rejected_button  # Resets all rejected chores to pending

# Or programmatically approve individual chores
service: simplechores.approve_chore
data:
  approval_id: "specific-approval-id"
```

---

## 🎁 Rewards System

SimpleChores supports multiple reward types to motivate kids with different goal structures:

### Point-Based Rewards (Traditional)
Classic rewards that cost points and optionally create calendar events:
```yaml
# Default point-based rewards
- Family Movie Night: 20 points
- Extra $5 Allowance: 25 points  
```

### Completion-Based Rewards  
Rewards earned by completing specific chore types a certain number of times:
```yaml
# Example completion-based rewards
- Trash Master Badge: Complete 10 trash chores
- Dish Washing Hero: Complete 15 dish chores
```

### Streak-Based Rewards
Rewards earned by completing chore types on consecutive days:
```yaml
# Example streak-based rewards  
- Perfect Week - Bed Made: Make bed every day for 7 days
- Super Clean Streak: Clean room every day for 14 days
```

### Reward Progress Tracking
- Progress sensors: `sensor.simplechores_<reward_id>_progress_<kid>`
- Automatic progress updates when chores with matching `chore_type` are completed
- Visual progress tracking in dashboards
- Achievement notifications via Home Assistant events

### Chore Types for Reward Tracking
When creating chores, use the `chore_type` parameter to track progress:
```yaml
# Common chore types that match default rewards
- "trash" → Trash Master Badge
- "bed" → Perfect Week - Bed Made  
- "dishes" → Dish Washing Hero
- "room" → Super Clean Streak
```

---

## 🔄 Migration Guide

### Upgrading from v1.3.x to v1.4.x

**Entity Naming Changes:**
The button entity naming pattern changed in v1.4.1 for auto-entities compatibility:

```yaml
# OLD pattern (v1.3.x and earlier):
button.simplechores_reward_movie_night_alice

# NEW pattern (v1.4.0+):
button.simplechores_movie_night_reward_alice
```

**Dashboard Updates Required:**
If you use auto-entities cards, update your filters:

```yaml
# OLD auto-entities filter:
include:
  - entity_id: "button.simplechores_reward_*_alice"

# NEW auto-entities filter:  
include:
  - entity_id: "button.simplechores_*_reward_alice"
```

**New Entities Added:**
- Approval/rejection buttons: `button.simplechores_approve_*`, `button.simplechores_reject_*`
- Progress sensors for completion/streak rewards: `sensor.simplechores_*_progress_*`
- Additional management buttons: `button.simplechores_approval_status_button`

**Breaking Changes:**
- Text input entities now start empty instead of with placeholder text
- Reward buttons may have different availability logic for completion-based rewards
- Service calls now include optional `chore_type` parameter

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
- [x] **Rewards system** – ✅ Implemented with point-based, completion-based, and streak-based rewards
- [x] **Dashboard input helpers** – ✅ Implemented with text inputs and action buttons
- [x] **Advanced rewards** – ✅ Implemented (completion tracking, streaks, progress sensors)
- [x] **Approval/rejection workflow** – ✅ Implemented with dedicated buttons and status tracking
- [x] **Button functionality fixes** – ✅ Fixed entity naming, validation, and error handling (v1.4.1)
- [ ] **Config UI for rewards** (currently uses default rewards, could add config flow step)
- [ ] **Ledger dashboard** (history of points earned/spent with reasons)
- [ ] **Mobile-friendly dashboard pack** (Mushroom UI optional)
- [ ] **Import tool** for KidsChores users
- [ ] **Custom reward definitions** via UI (currently requires code changes)

---

## 🔄 Updates & HACS Benefits

### For Users
- **Automatic updates**: Get notified when new versions are available
- **One-click installation**: No manual file copying required
- **Easy uninstall**: Remove cleanly through HACS interface
- **Version management**: Easily downgrade if needed

### For Development
This integration is HACS-ready, which provides several development benefits:
- **Faster iteration**: Most changes don't require Home Assistant restart
- **Integration reload**: Use `Developer Tools → YAML → Reload` for many changes
- **Service updates**: New services and entity changes load without restart
- **Better debugging**: Keep HA running while testing changes

### Reload Without Restart
After updating via HACS, you can often reload just the integration:
```yaml
# In Developer Tools → Services
service: homeassistant.reload_config_entry
data:
  entry_id: "your_simplechores_entry_id"
```

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

