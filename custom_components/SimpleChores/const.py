"""Constants for the SimpleChores integration."""
DOMAIN = "simplechores"
PLATFORMS = ["number", "todo", "sensor", "text", "button"]

CONF_KIDS = "kids"
CONF_USE_TODO = "use_todo"
CONF_PARENTS_CALENDAR = "parents_calendar"

STORAGE_VERSION = 2
STORAGE_KEY = f"{DOMAIN}_ledger"

# Services
SERVICE_ADD_POINTS = "add_points"
SERVICE_REMOVE_POINTS = "remove_points"
SERVICE_CREATE_ADHOC = "create_adhoc_chore"
SERVICE_COMPLETE_CHORE = "complete_chore"
SERVICE_CLAIM_REWARD = "claim_reward"
SERVICE_LOG_PARENT_CHORE = "log_parent_chore"
SERVICE_CREATE_RECURRING = "create_recurring_chore"
SERVICE_APPROVE_CHORE = "approve_chore"
SERVICE_REJECT_CHORE = "reject_chore"
SERVICE_GENERATE_RECURRING = "generate_recurring_chores"
