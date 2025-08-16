# SimpleChores – Simple Chore & Reward Management for Home Assistant

**SimpleChores** is a lightweight Home Assistant custom integration for managing kids’ chores, points, and rewards – without the overhead of heavy templates or complicated dashboards.

It’s designed for simplicity, transparency, and family-friendly dashboards.  
Each child gets a points balance, chores can be recurring or ad-hoc, and parents’ chores can be added to a calendar to model teamwork.

---

## ✨ Features

- **Per-kid points balance**  
  Each child has a `number` entity (`number.alex_points`, `number.emma_points`) with easy add/remove buttons.

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

1. Copy this repository into `config/custom_components/kidpoints/`.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration → KidPoints**.
4. Follow the config flow to:
   - Add children’s names.
   - Pick whether to use Local To-do lists.
   - Select a calendar for parents’ chores (Local or Google, RW enabled).

---

## ⚙️ Entities

### Numbers
- `number.<kid>_points` – current points balance per child.

### To-do lists (optional)
- `todo.<kid>_chores` – if enabled, integration exposes a To-do list entity per child.

### Sensors (planned)
- `sensor.<kid>_points_week`
- `sensor.<kid>_points_total`

---

## 🛠️ Services

All services are under the `kidpoints` domain:

- `kidpoints.add_points`
  - `kid`: child name/id  
  - `amount`: integer  
  - `reason` (optional)

- `kidpoints.remove_points`
  - Same fields as `add_points`.

- `kidpoints.create_adhoc_chore`
  - `kid`: child  
  - `title`: string  
  - `points`: integer  
  - `due`: datetime (optional)

- `kidpoints.complete_chore`
  - `kid`: child  
  - `chore_id`: To-do item ID

- `kidpoints.claim_reward`
  - `kid`: child  
  - `reward_id`: defined in config  
  - Deducts cost, logs event, and (optionally) creates a calendar entry.

- `kidpoints.log_parent_chore`
  - `title`: string  
  - `start`, `end`: datetime  
  - `all_day`: bool

---

## 📅 Recurring chores

Two supported patterns:

### A. Schedule → To-do
Use HA’s **Schedule helper**.  
Example: “Every day 7–8 PM” triggers a KidPoints automation to add chores.

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
- Platforms: `number/`, `todo/`, `sensor/`  
- Services: registered via `async_register`  
- Storage: HA `Store` API for ledger/history

Scaffold created with [cookiecutter-homeassistant-custom-component](https://github.com/oncleben31/cookiecutter-homeassistant-custom-component).

---

## 🚀 Roadmap / TODO

- [ ] **Config UI for rewards** (currently defined in YAML/JSON)
- [ ] **Weekly/monthly summary sensors** (`points_this_week`, etc.)
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

