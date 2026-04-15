"""Sensor platform for Time of Day."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PERIOD_ICONS
from .coordinator import TimeOfDayCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Time of Day sensor."""
    coordinator: TimeOfDayCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TimeOfDaySensor(coordinator, entry)])


class TimeOfDaySensor(CoordinatorEntity[TimeOfDayCoordinator], SensorEntity):
    """Sensor showing the currently active time-of-day period."""

    _attr_has_entity_name = True
    _attr_translation_key = "active_period"
    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        coordinator: TimeOfDayCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_active_period"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Time of Day",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> str | None:
        """Return the key of the active period."""
        return self.coordinator.active_period

    @property
    def icon(self) -> str:
        """Return a dynamic icon based on the active period."""
        period = self.coordinator.active_period
        if period and period in PERIOD_ICONS:
            return PERIOD_ICONS[period]
        return "mdi:clock-outline"

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        period = self.coordinator.active_period
        attrs = {
            "workday": self.coordinator.is_workday(),
            "preactivated": self.coordinator.was_preactivated,
        }

        if period:
            start_time = self.coordinator.get_period_start_time(period)
            attrs["start_time"] = start_time.strftime("%H:%M")

        next_period, next_time = self.coordinator.get_next_period()
        attrs["next_period"] = next_period
        attrs["next_period_start_time"] = next_time.strftime("%H:%M")

        return attrs
