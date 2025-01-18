"""Support for lights through the SmartThings cloud API."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from pysmartthings import Capability

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    brightness_supported,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_BROKERS, DOMAIN
from .entity import SmartThingsEntity

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add lights for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    async_add_entities(
        [
            SmartThingsLight(device)
            for device in broker.devices.values()
            if broker.any_assigned(device.device_id, "light")
        ],
        True,
    )
    _LOGGER.debug("Setup lights for SmartThings integration")


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    supported = [
        Capability.switch,
        Capability.switch_level,
        Capability.color_control,
        Capability.color_temperature,
    ]
    if Capability.switch not in capabilities:
        return None
    return supported if any(cap in capabilities for cap in supported[1:]) else None


class SmartThingsLight(SmartThingsEntity, LightEntity):
    """Define a SmartThings Light."""

    def __init__(self, device):
        """Initialize a SmartThings Light."""
        super().__init__(device)
        self._attr_supported_color_modes = self._determine_color_modes()
        self._attr_supported_features = self._determine_features()
        _LOGGER.debug("Initialized light device: %s", device.label)

    def _determine_color_modes(self):
        color_modes = set()
        if Capability.color_temperature in self._device.capabilities:
            color_modes.add(ColorMode.COLOR_TEMP)
        if Capability.color_control in self._device.capabilities:
            color_modes.add(ColorMode.HS)
        if not color_modes and Capability.switch_level in self._device.capabilities:
            color_modes.add(ColorMode.BRIGHTNESS)
        if not color_modes:
            color_modes.add(ColorMode.ONOFF)
        _LOGGER.debug("Supported color modes for light %s: %s", self._device.label, color_modes)
        return color_modes

    def _determine_features(self) -> LightEntityFeature:
        features = LightEntityFeature(0)
        if Capability.switch_level in self._device.capabilities:
            features |= LightEntityFeature.TRANSITION
        _LOGGER.debug("Supported features for light %s: %s", self._device.label, features)
        return features

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        tasks = []
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            tasks.append(self.async_set_color_temp(kwargs[ATTR_COLOR_TEMP_KELVIN]))
        if ATTR_HS_COLOR in kwargs:
            tasks.append(self.async_set_color(kwargs[ATTR_HS_COLOR]))
        if tasks:
            await asyncio.gather(*tasks)
        if ATTR_BRIGHTNESS in kwargs:
            await self.async_set_level(kwargs[ATTR_BRIGHTNESS], kwargs.get(ATTR_TRANSITION, 0))
        else:
            await self._device.switch_on(set_status=True)
        _LOGGER.debug("Turned on light %s with parameters: %s", self._device.label, kwargs)
        self.async_schedule_update_ha_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if ATTR_TRANSITION in kwargs:
            await self.async_set_level(0, int(kwargs[ATTR_TRANSITION]))
        else:
            await self._device.switch_off(set_status=True)
        _LOGGER.debug("Turned off light %s with parameters: %s", self._device.label, kwargs)
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Update entity attributes when the device status has changed."""
        if brightness_supported(self._attr_supported_color_modes):
            self._attr_brightness = int(self._device.status.level / 100 * 255)
        if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            self._attr_color_temp_kelvin = self._device.status.color_temperature
        if ColorMode.HS in self._attr_supported_color_modes:
            self._attr_hs_color = (
                self._device.status.hue / 100 * 360,
                self._device.status.saturation,
            )
        _LOGGER.debug(
            "Updated light %s attributes: Brightness=%s, ColorTemp=%s, HSColor=%s",
            self._device.label,
            self._attr_brightness,
            self._attr_color_temp_kelvin,
            self._attr_hs_color,
        )

    async def async_set_color(self, hs_color):
        hue = hs_color[0] / 360 * 100
        saturation = max(min(hs_color[1], 100), 0.0)
        await self._device.set_color(hue, saturation, set_status=True)

    async def async_set_color_temp(self, value: int):
        kelvin = max(min(value, 30000), 1)
        await self._device.set_color_temperature(kelvin, set_status=True)

    async def async_set_level(self, brightness: int, transition: int):
        level = max(min(brightness / 255 * 100, 100), 1)
        await self._device.set_level(level, duration=transition, set_status=True)
