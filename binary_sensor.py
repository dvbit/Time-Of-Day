"""Binary sensor platform for Time of Day."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PERIOD_ICONS, PERIODS
from .coordinator import TimeOfDayCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Time of Day binary sensors."""
    coordinator: TimeOfDayCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = [
        TimeOfDayBinarySensor(coordinator, entry, period) for period in PERIODS
    ]
    entities.append(PreactivationWindowBinarySensor(coordinator, entry))
    async_add_entities(entities)


class TimeOfDayBinarySensor(CoordinatorEntity[TimeOfDayCoordinator], BinarySensorEntity):
    """Binary sensor that is ON when a specific time-of-day period is active."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TimeOfDayCoordinator,
        entry: ConfigEntry,
        period: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._period = period
        self._attr_unique_id = f"{entry.entry_id}_{period}"
        self._attr_translation_key = period
        self._attr_icon = PERIOD_ICONS[period]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Time of Day",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool:
        """Return True if this period is currently active."""
        return self.coordinator.active_period == self._period

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        start_time = self.coordinator.get_period_start_time(self._period)
        window = self.coordinator.get_preactivation_window(self._period)
        preact_entity = self.coordinator.get_preactivation_entity(self._period)

        attrs = {
            "start_time": start_time.strftime("%H:%M"),
            "preactivation_window_minutes": window,
            "workday": self.coordinator.is_workday(),
        }

        if preact_entity:
            attrs["preactivation_entity"] = preact_entity

        if self.is_on:
            attrs["preactivated"] = self.coordinator.was_preactivated

        return attrs


class PreactivationWindowBinarySensor(
    CoordinatorEntity[TimeOfDayCoordinator], BinarySensorEntity
):
    """Binary sensor that is ON when currently inside any pre-activation window."""

    _attr_has_entity_name = True
    _attr_translation_key = "preactivation_window"
    _attr_icon = "mdi:timer-alert-outline"

    def __init__(
        self,
        coordinator: TimeOfDayCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_preactivation_window"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Time of Day",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool:
        """Return True if currently in any pre-activation window."""
        return self.coordinator.is_in_preactivation_window()
