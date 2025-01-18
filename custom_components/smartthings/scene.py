"""Support for scenes through the SmartThings cloud API."""

from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_BROKERS, DOMAIN

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add scenes for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    async_add_entities(SmartThingsScene(scene) for scene in broker.scenes.values())
    _LOGGER.debug("Setup scenes for SmartThings integration")


class SmartThingsScene(Scene):
    """Define a SmartThings scene."""

    def __init__(self, scene):
        """Initialize the scene."""
        self._scene = scene
        self._attr_name = scene.name
        self._attr_unique_id = scene.scene_id
        _LOGGER.debug("Initialized scene: %s with ID: %s", scene.name, scene.scene_id)

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        _LOGGER.debug("Activating scene: %s with parameters: %s", self._scene.name, kwargs)
        await self._scene.execute()

    @property
    def extra_state_attributes(self):
        """Get attributes about the state."""
        attributes = {
            "icon": self._scene.icon,
            "color": self._scene.color,
            "location_id": self._scene.location_id,
        }
        _LOGGER.debug("Extra state attributes for scene %s: %s", self._scene.name, attributes)
        return attributes
