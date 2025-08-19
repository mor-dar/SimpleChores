# Chore Management Guide

SimpleChores provides multiple ways to manage chores depending on your setup and preferences. This guide covers all available methods.

## Overview

SimpleChores supports two main approaches:
1. **With Todo Lists**: Integrated todo list entities for each child (recommended)
2. **Without Todo Lists**: Button and sensor-based management

## Method 1: With Todo Lists (Recommended)

When todo lists are enabled in your configuration, each child gets their own todo list entity (`todo.<kid>_chores`).

### Creating Chores
- **Daily Recurring Chores**: Use the "Generate Daily Chores" button or set up automations
- **Manual Chores**: Add items directly to the todo list or use "Create Ad-Hoc Chore" buttons
- **From Calendar**: Import from calendar events (requires calendar configuration)

### Completing Chores
1. **Check off items** in the child's todo list
2. **Chores move to approval queue** automatically
3. **Parents approve/reject** using approval buttons
4. **Points awarded** upon approval

### Managing Approvals
- **View pending approvals**: Check approval buttons (show count when > 0)
- **Approve chores**: Click individual approval buttons or batch approve
- **Reject chores**: Use reject buttons (chores reset to pending)
- **Monitor progress**: Use weekly/total points sensors

## Method 2: Without Todo Lists

If you disable todo lists (`use_todo: false`) or prefer button-based management, use these entities:

### Core Entities Per Child

#### Points Management
- **`number.<kid>_points`**: Current points balance with +/- controls
- **`sensor.<kid>_points_week`**: Points earned this week
- **`sensor.<kid>_points_total`**: Total points earned

#### Chore Creation
- **`text.<kid>_chore_title`**: Input field for chore name
- **`number.<kid>_chore_points`**: Point value for the chore
- **`button.<kid>_create_chore`**: Creates the chore

#### Approval Management
- **Approval buttons**: One button per pending approval (dynamic)
- **Button text format**: "Approve: [Chore Name] ([Kid], [Points]pts)"
- **Reject buttons**: "Reject: [Chore Name]" (separate buttons)

### Creating Chores (Button Method)

1. **Set chore title**: Enter name in `text.<kid>_chore_title`
2. **Set point value**: Adjust `number.<kid>_chore_points`
3. **Create chore**: Press `button.<kid>_create_chore`
4. **Chore appears** in pending approval queue

### Completing Chores (Button Method)

Since there are no todo lists, chores are completed through:
- **Service calls**: `simplechores.complete_chore` with `chore_id`
- **Automations**: Triggered by external events
- **Manual approval**: Direct approval without prior completion

### Approval Workflow

1. **Monitor approvals**: Watch for approval buttons to appear
2. **Review chore details**: Button text shows chore, kid, and points
3. **Approve**: Click green approval button → points awarded
4. **Reject**: Click red reject button → chore reset to pending

### Service Calls

Use these services for advanced automation:

```yaml
# Complete a specific chore
service: simplechores.complete_chore
data:
  chore_id: "chore-uuid"  # or todo_uid for todo-based chores

# Create ad-hoc chore
service: simplechores.create_adhoc_chore
data:
  kid_id: "alice"
  title: "Clean room"
  points: 10

# Approve chore
service: simplechores.approve_chore
data:
  approval_id: "approval-uuid"

# Reject chore  
service: simplechores.reject_chore
data:
  approval_id: "approval-uuid"
  reason: "Not completed properly"

# Award/deduct points directly
service: simplechores.add_points
data:
  kid_id: "alice"
  points: 5
  reason: "Extra credit"

service: simplechores.remove_points
data:
  kid_id: "alice"
  points: 3
  reason: "Penalty"

# Claim rewards
service: simplechores.claim_reward
data:
  kid_id: "alice"
  reward_id: "movie_night"
```

## Dashboard Configuration

### With Todo Lists
```yaml
type: todo-list
entity: todo.alice_chores
title: "Alice's Chores"
```

### Without Todo Lists
```yaml
type: entities
title: "Alice's Chores"
entities:
  - entity: number.alice_points
    name: "Current Points"
  - entity: sensor.alice_points_week
    name: "This Week"
  - entity: text.alice_chore_title
    name: "New Chore"
  - entity: number.alice_chore_points
    name: "Points"
  - entity: button.alice_create_chore
    name: "Create Chore"
  # Approval buttons appear dynamically
```

## Automation Examples

### Daily Chore Creation
```yaml
automation:
  - alias: "Generate Daily Chores"
    trigger:
      platform: time
      at: "06:00:00"
    action:
      service: button.press
      entity_id: button.generate_daily_chores
```

### Chore Completion Trigger
```yaml
automation:
  - alias: "Complete Chore on Motion"
    trigger:
      platform: state
      entity_id: binary_sensor.room_motion
      to: "off"
      for: "00:05:00"
    action:
      service: simplechores.complete_chore
      data:
        chore_id: "daily-clean-room-alice"
```

### Auto-Approval for Small Chores
```yaml
automation:
  - alias: "Auto-approve small chores"
    trigger:
      platform: event
      event_type: simplechores_approval_created
    condition:
      condition: template
      value_template: "{{ trigger.event.data.points <= 2 }}"
    action:
      service: simplechores.approve_chore
      data:
        approval_id: "{{ trigger.event.data.approval_id }}"
```

## Troubleshooting

### Common Issues

**No approval buttons appear**:
- Check if chores were completed properly
- Verify points > 0 for the chore
- Look in Home Assistant logs for approval creation messages

**Points not awarded**:
- Ensure chores go through approval workflow
- Check for service call errors in logs
- Verify kid_id matches configuration

**Chores not persistent**:
- SimpleChores automatically saves state
- Check `.storage` directory for `simplechores.*` files
- Restart Home Assistant if state seems corrupted

### Debug Commands

Check pending approvals:
```yaml
service: button.press
entity_id: button.list_pending_approvals
```

Reset rejected chores:
```yaml
service: button.press  
entity_id: button.reset_rejected_chores
```

## Advanced Configuration

### Custom Rewards
Edit the coordinator to add custom rewards:
```python
default_rewards = {
    "movie_night": Reward(id="movie_night", title="Movie Night", cost=20),
    "extra_allowance": Reward(id="extra_allowance", title="Extra Allowance", cost=25),
    "custom_reward": Reward(id="custom_reward", title="Custom Reward", cost=15)
}
```

### Calendar Integration
For calendar-based chore creation, configure:
1. Calendar entity in Home Assistant
2. Automation to sync calendar events
3. RRULE support for recurring chores

### Multiple Kids
Each child gets their own set of entities:
- `number.alice_points`, `number.bob_points`
- `todo.alice_chores`, `todo.bob_chores`  
- Individual approval buttons per child
- Shared reward claiming system

## Migration from Todo to Button Mode

To disable todo lists and use button mode:

1. Update configuration: `use_todo: false`
2. Remove todo list cards from dashboards
3. Add button/sensor cards per child
4. Update any automations using todo entities
5. Restart Home Assistant

Existing approvals and points are preserved during the transition.