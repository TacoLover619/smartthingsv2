"""Support for sensors through the SmartThings cloud API."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from pysmartthings import Attribute, Capability
from pysmartthings.device import DeviceEntity

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfArea,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfMass,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DATA_BROKERS, DOMAIN
from .entity import SmartThingsEntity

import logging

_LOGGER = logging.getLogger(__name__)

# Constants for mapping capabilities
class Map(NamedTuple):
    """Tuple for mapping SmartThings capabilities to Home Assistant sensors."""

    attribute: str
    name: str
    default_unit: str | None
    device_class: SensorDeviceClass | None
    state_class: SensorStateClass | None
    entity_category: EntityCategory | None


CAPABILITY_TO_SENSORS: dict[str, list[Map]] = {
    Capability.temperature_measurement: [
        Map(
            Attribute.temperature,
            "Temperature Measurement",
            None,
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
            None,
        )
    ],
    Capability.refrigeration_setpoint: [
        Map(
            Attribute.refrigeration_setpoint,
            "Refrigeration Setpoint",
            None,
            SensorDeviceClass.TEMPERATURE,
            None,
            None,
        )
    ],
    # Add other mappings here...
}

UNITS = {
    "C": UnitOfTemperature.CELSIUS,
    "F": UnitOfTemperature.FAHRENHEIT,
    "lux": LIGHT_LUX,
}

# Sensor Entity Definitions
class SmartThingsSensor(SmartThingsEntity, SensorEntity):
    """Define a SmartThings Sensor."""

    def __init__(
        self,
        device: DeviceEntity,
        attribute: str,
        name: str,
        default_unit: str | None,
        device_class: SensorDeviceClass | None,
        state_class: str | None,
        entity_category: EntityCategory | None,
    ) -> None:
        """Initialize the class."""
        super().__init__(device)
        self._attribute = attribute
        self._attr_name = f"{device.label} {name}"
        self._attr_unique_id = f"{device.device_id}.{attribute}"
        self._attr_device_class = device_class
        self._default_unit = default_unit
        self._attr_state_class = state_class
        self._attr_entity_category = entity_category

        # Log attributes during initialization
        _LOGGER.debug(
            "Initializing sensor for device '%s' with attribute '%s'",
            device.label,
            attribute,
        )
        _LOGGER.debug("Device attributes: %s", device.status.attributes)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        value = self._device.status.attributes[self._attribute].value

        if self.device_class != SensorDeviceClass.TIMESTAMP:
            return value

        return dt_util.parse_datetime(value)

    @property
    def native_unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        unit = self._device.status.attributes[self._attribute].unit
        return UNITS.get(unit, unit) if unit else self._default_unit

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    entities: list[SensorEntity] = []
    for device in broker.devices.values():
        for capability in broker.get_assigned(device.device_id, "sensor"):
            if capability in CAPABILITY_TO_SENSORS:
                for mapping in CAPABILITY_TO_SENSORS[capability]:
                    entities.append(
                        SmartThingsSensor(
                            device,
                            mapping.attribute,
                            mapping.name,
                            mapping.default_unit,
                            mapping.device_class,
                            mapping.state_class,
                            mapping.entity_category,
                        )
                    )
            else:
                _LOGGER.warning(
                    "Capability '%s' is not supported by device '%s'",
                    capability,
                    device.label,
                )

    async_add_entities(entities)
