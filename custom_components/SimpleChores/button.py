"""Button entities for SimpleChores integration."""
from __future__ import annotations
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .coordinator import SimpleChoresCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add_entities: AddEntitiesCallback):
    coordinator: SimpleChoresCoordinator = hass.data[DOMAIN][entry.entry_id]
    kids_csv = entry.data.get("kids", "alex,emma")
    kids = [k.strip() for k in kids_csv.split(",") if k.strip()]
    
    entities = []
    # Create chore button
    entities.append(SimpleChoresCreateChoreButton(coordinator, hass))
    
    # Reward buttons - use kids from config since coordinator.model.kids might be empty during setup
    for reward in coordinator.get_rewards():
        for kid_id in kids:
            entities.append(SimpleChoresRewardButton(coordinator, reward.id, kid_id, hass))
    
    add_entities(entities, True)

class SimpleChoresCreateChoreButton(ButtonEntity):
    _attr_icon = "mdi:plus-circle"

    def __init__(self, coord: SimpleChoresCoordinator, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._attr_unique_id = f"{DOMAIN}_create_chore_button"
        self._attr_name = "Create Chore"

    async def async_press(self) -> None:
        # Get values from input helpers
        title_entity = self._hass.states.get(f"text.simplechores_chore_title_input")
        points_entity = self._hass.states.get(f"text.simplechores_chore_points_input") 
        kid_entity = self._hass.states.get(f"text.simplechores_chore_kid_input")
        
        if not all([title_entity, points_entity, kid_entity]):
            return
            
        title = title_entity.state
        try:
            points = int(points_entity.state)
        except (ValueError, TypeError):
            points = 5
        kid = kid_entity.state
        
        if title and kid:
            # Create chore via service
            await self._hass.services.async_call(
                DOMAIN, "create_adhoc_chore",
                {"kid": kid, "title": title, "points": points}
            )

class SimpleChoresRewardButton(ButtonEntity):
    _attr_icon = "mdi:gift"

    def __init__(self, coord: SimpleChoresCoordinator, reward_id: str, kid_id: str, hass: HomeAssistant):
        self._coord = coord
        self._hass = hass
        self._reward_id = reward_id
        self._kid_id = kid_id
        reward = coord.get_reward(reward_id)
        self._attr_unique_id = f"{DOMAIN}_reward_{reward_id}_{kid_id}"
        if reward:
            self._attr_name = f"{reward.title} ({kid_id.capitalize()}) - {reward.cost}pts"
        else:
            self._attr_name = f"Unknown Reward ({kid_id.capitalize()})"

    @property
    def available(self) -> bool:
        """Check if reward is available and kid has enough points."""
        reward = self._coord.get_reward(self._reward_id)
        if not reward:
            return False
        kid_points = self._coord.get_points(self._kid_id)
        return kid_points >= reward.cost

    async def async_press(self) -> None:
        reward = self._coord.get_reward(self._reward_id)
        kid_points = self._coord.get_points(self._kid_id)
        
        if reward and kid_points >= reward.cost:
            await self._hass.services.async_call(
                DOMAIN, "claim_reward",
                {"kid": self._kid_id, "reward_id": self._reward_id}
            )