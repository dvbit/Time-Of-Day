"""The Time of Day integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, PLATFORMS, SERVICE_ADVANCE_PERIOD
from .coordinator import TimeOfDayCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Time of Day from a config entry."""
    coordinator = TimeOfDayCoordinator(hass, entry)

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Set up time and state listeners
    coordinator.setup_listeners()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Recalculate once listeners are up
    coordinator.recalculate()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register the advance_period service (once for all entries)
    if not hass.services.has_service(DOMAIN, SERVICE_ADVANCE_PERIOD):

        async def handle_advance_period(call: ServiceCall) -> None:
            """Handle the advance_period service call."""
            for coord in hass.data[DOMAIN].values():
                if isinstance(coord, TimeOfDayCoordinator):
                    coord.advance_period()

        hass.services.async_register(
            DOMAIN,
            SERVICE_ADVANCE_PERIOD,
            handle_advance_period,
            schema=vol.Schema({}),
        )

    # Re-setup listeners when options change
    entry.async_on_unload(
        entry.add_update_listener(_async_update_listener)
    )

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update."""
    coordinator: TimeOfDayCoordinator = hass.data[DOMAIN][entry.entry_id]
    # Clear any stale latch so the recalculation reflects the new config cleanly
    coordinator.clear_forced_period()
    coordinator.setup_listeners()
    coordinator.recalculate()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: TimeOfDayCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.shutdown()
    return unload_ok
