"""Support for climate devices through the SmartThings cloud API."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
import logging
from typing import Any

from pysmartthings import Attribute, Capability

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_BROKERS, DOMAIN
from .entity import SmartThingsEntity

_LOGGER = logging.getLogger(__name__)

ATTR_OPERATION_STATE = "operation_state"

# Mode mappings
MODE_TO_STATE = {
    "auto": HVACMode.HEAT_COOL,
    "cool": HVACMode.COOL,
    "eco": HVACMode.AUTO,
    "rush hour": HVACMode.AUTO,
    "emergency heat": HVACMode.HEAT,
    "heat": HVACMode.HEAT,
    "off": HVACMode.OFF,
}
STATE_TO_MODE = {v: k for k, v in MODE_TO_STATE.items()}

OPERATING_STATE_TO_ACTION = {
    "cooling": HVACAction.COOLING,
    "fan only": HVACAction.FAN,
    "heating": HVACAction.HEATING,
    "idle": HVACAction.IDLE,
    "pending cool": HVACAction.COOLING,
    "pending heat": HVACAction.HEATING,
}

UNIT_MAP = {"C": UnitOfTemperature.CELSIUS, "F": UnitOfTemperature.FAHRENHEIT}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add climate entities for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    entities: list[ClimateEntity] = []
    for device in broker.devices.values():
        if broker.any_assigned(device.device_id, CLIMATE_DOMAIN):
            entities.append(SmartThingsClimate(device))
            _LOGGER.debug("Added climate device: %s", device.label)
    async_add_entities(entities)


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    supported = [
        Capability.thermostat,
        Capability.temperature_measurement,
        Capability.thermostat_mode,
    ]
    return [cap for cap in supported if cap in capabilities]


class SmartThingsClimate(SmartThingsEntity, ClimateEntity):
    """Define a SmartThings climate entity."""

    def __init__(self, device):
        """Initialize the class."""
        super().__init__(device)
        self._hvac_mode = None
        self._hvac_modes = []
        _LOGGER.debug("Initialized climate device: %s", device.label)

    async def async_update(self) -> None:
        """Update the attributes of the climate device."""
        try:
            self._hvac_mode = MODE_TO_STATE.get(self._device.status.thermostat_mode)
            _LOGGER.debug(
                "Updated HVAC mode for device %s: %s",
                self._device.label,
                self._hvac_mode,
            )

            modes = set()
            supported_modes = self._device.status.supported_thermostat_modes
            if isinstance(supported_modes, Iterable):
                for mode in supported_modes:
                    if (state := MODE_TO_STATE.get(mode)) is not None:
                        modes.add(state)
                    else:
                        _LOGGER.debug(
                            "Unsupported HVAC mode for %s: %s",
                            self._device.label,
                            mode,
                        )
            self._hvac_modes = list(modes)
            _LOGGER.debug(
                "Supported HVAC modes for device %s: %s",
                self._device.label,
                self._hvac_modes,
            )
        except Exception as e:
            _LOGGER.error("Error updating climate device %s: %s", self._device.label, e)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        temperature = self._device.status.temperature
        _LOGGER.debug("Current temperature for %s: %s", self._device.label, temperature)
        return temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available operation modes."""
        return self._hvac_modes
