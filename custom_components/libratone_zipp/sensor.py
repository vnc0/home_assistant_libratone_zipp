"""Battery, Wi-Fi signal, firmware and serial number sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SCAN_INTERVAL, LibratoneZippEntity  # noqa: F401  (SCAN_INTERVAL is read by HA)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    zipp = hass.data[DOMAIN][entry.entry_id]
    name = entry.data.get(CONF_NAME, "Libratone Zipp")
    async_add_entities(
        [
            ZippBatterySensor(zipp, name),
            ZippSignalSensor(zipp, name),
            ZippFirmwareSensor(zipp, name),
            ZippSerialSensor(zipp, name),
        ]
    )


class ZippBatterySensor(LibratoneZippEntity, SensorEntity):
    _key = "battery"
    _attr_name = "Battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return self._zipp.battery_percent


class ZippSignalSensor(LibratoneZippEntity, SensorEntity):
    _key = "wifi_signal"
    _attr_name = "Wi-Fi signal"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        return self._zipp.wifi_rssi

    @property
    def extra_state_attributes(self):
        return {"quality_percent": self._zipp.wifi_quality_percent}


class ZippFirmwareSensor(LibratoneZippEntity, SensorEntity):
    _key = "firmware"
    _attr_name = "Firmware"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        return self._zipp.version


class ZippSerialSensor(LibratoneZippEntity, SensorEntity):
    _key = "serial_number"
    _attr_name = "Serial number"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    @property
    def native_value(self):
        return self._zipp.serialnumber
