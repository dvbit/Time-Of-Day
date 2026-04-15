"""Button platform for Time of Day."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TimeOfDayCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Time of Day button."""
    coordinator: TimeOfDayCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AdvancePeriodButton(coordinator, entry)])


class AdvancePeriodButton(CoordinatorEntity[TimeOfDayCoordinator], ButtonEntity):
    """Button to advance to the next time-of-day period."""

    _attr_has_entity_name = True
    _attr_translation_key = "advance_period"
    _attr_icon = "mdi:skip-next"

    def __init__(
        self,
        coordinator: TimeOfDayCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_advance_period"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Time of Day",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        self.coordinator.advance_period()
