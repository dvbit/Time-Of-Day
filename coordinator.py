"""Coordinator for the Time of Day integration."""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, State, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_NON_WORKDAY_TIME,
    CONF_PREACTIVATION_ENTITY,
    CONF_PREACTIVATION_WINDOW,
    CONF_WORKDAY_ENTITY,
    CONF_WORKDAY_TIME,
    DOMAIN,
    PERIOD_NAMES,
    PERIODS,
)

_LOGGER = logging.getLogger(__name__)


def _parse_time(time_str: str) -> time:
    """Parse a time string (HH:MM:SS or HH:MM) to a time object."""
    parts = time_str.split(":")
    return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)


def _period_key(period: str, key: str) -> str:
    """Build a config key for a specific period."""
    return f"{period}_{key}"


class TimeOfDayCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that manages which time-of-day period is active."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.entry = entry
        self._unsub_listeners: list[CALLBACK_TYPE] = []
        self._active_period: str | None = None
        self._preactivated: bool = False
        self._forced_period: str | None = None

    @property
    def active_period(self) -> str | None:
        """Return the currently active period."""
        return self._active_period

    @property
    def was_preactivated(self) -> bool:
        """Return whether the current period was pre-activated."""
        return self._preactivated

    def _get_config(self) -> dict[str, Any]:
        """Get merged config from entry data and options."""
        return {**self.entry.data, **self.entry.options}

    def is_workday(self) -> bool:
        """Check if today is a workday based on the configured entity."""
        config = self._get_config()
        workday_entity = config.get(CONF_WORKDAY_ENTITY)
        if not workday_entity:
            return True
        state = self.hass.states.get(workday_entity)
        if state is None:
            return True
        return state.state == "on"

    def get_period_start_time(self, period: str) -> time:
        """Get the start time for a period based on workday status."""
        config = self._get_config()
        workday = self.is_workday()
        key = CONF_WORKDAY_TIME if workday else CONF_NON_WORKDAY_TIME
        time_str = config.get(_period_key(period, key))
        if time_str:
            return _parse_time(time_str)
        # Fallback to defaults
        from .const import DEFAULT_TIMES

        day_type = "workday" if workday else "non_workday"
        return _parse_time(DEFAULT_TIMES[period][day_type])

    def get_preactivation_window(self, period: str) -> int:
        """Get the pre-activation window in minutes for a period."""
        config = self._get_config()
        return int(
            config.get(
                _period_key(period, CONF_PREACTIVATION_WINDOW), 0
            )
        )

    def get_preactivation_entity(self, period: str) -> str | None:
        """Get the pre-activation entity for a period."""
        config = self._get_config()
        return config.get(_period_key(period, CONF_PREACTIVATION_ENTITY))

    def _get_period_start_datetime(self, period: str, now: datetime) -> datetime:
        """Get the start datetime for a period on the current day."""
        t = self.get_period_start_time(period)
        return now.replace(hour=t.hour, minute=t.minute, second=t.second, microsecond=0)

    def _in_preactivation_window(self, period: str, now: datetime) -> bool:
        """Return True if `now` falls within the pre-activation window for a period.

        Only returns True for periods that have not yet started (upcoming periods).
        Does not check the pre-activation entity state.
        """
        window_minutes = self.get_preactivation_window(period)
        if window_minutes <= 0:
            return False

        start_t = self.get_period_start_time(period)
        current_time = now.time()

        # Pre-activation only applies to periods that haven't started yet
        if current_time >= start_t:
            return False

        window_start = (
            datetime.combine(now.date(), start_t) - timedelta(minutes=window_minutes)
        ).time()

        if window_start < start_t:
            return window_start <= current_time < start_t
        # Window crosses midnight
        return current_time >= window_start or current_time < start_t

    def _calculate_active_period(self, now: datetime | None = None) -> tuple[str, bool]:
        """Calculate which period should be active right now.

        Returns (period_name, was_preactivated).

        A period that was pre-activated or force-advanced is latched: it stays
        active until its natural start time passes, even if the pre-activation
        entity goes back to off.
        """
        if now is None:
            now = dt_util.now()

        current_time = now.time()
        workday = self.is_workday()

        # Build sorted list of (start_time, period) for today
        period_times: list[tuple[time, str]] = []
        for period in PERIODS:
            start = self.get_period_start_time(period)
            period_times.append((start, period))

        # Sort by time
        period_times.sort(key=lambda x: x[0])

        _LOGGER.debug(
            "Calculating active period: now=%s, workday=%s, periods=%s, latched=%s",
            current_time,
            workday,
            [(str(t), p) for t, p in period_times],
            self._forced_period,
        )

        # Determine the naturally active period (most recent start time passed)
        natural_active = None
        for start_t, period in period_times:
            if current_time >= start_t:
                natural_active = period

        if natural_active is None:
            # Before the first period of the day — use the last period (wraps)
            natural_active = period_times[-1][1]

        # If a period is latched (pre-activated or force-advanced), check if
        # natural time has caught up — if so, clear the latch.
        if self._forced_period:
            if self._forced_period == natural_active:
                # Natural time caught up to the latched period; clear latch
                _LOGGER.debug(
                    "Latched period %s now naturally active, clearing latch",
                    self._forced_period,
                )
                self._forced_period = None
            else:
                # Still latched — keep it active
                _LOGGER.debug(
                    "Latched period %s still active (natural would be %s)",
                    self._forced_period,
                    natural_active,
                )
                return (self._forced_period, self._preactivated)

        # Check pre-activation: find the next upcoming period and see if
        # we're in its pre-activation window and its entity is on.
        for _start_t, period in period_times:
            if not self._in_preactivation_window(period, now):
                continue

            preact_entity_id = self.get_preactivation_entity(period)
            if not preact_entity_id:
                continue

            state = self.hass.states.get(preact_entity_id)
            if state is not None and state.state == "on":
                _LOGGER.debug(
                    "Pre-activation triggered for %s (entity %s is on) — latching",
                    period, preact_entity_id,
                )
                # Latch so it persists even if entity goes back to off
                self._forced_period = period
                return (period, True)

        _LOGGER.debug("Active period determined: %s", natural_active)
        return (natural_active, False)

    @callback
    def recalculate(self, _now: datetime | None = None) -> None:
        """Recalculate the active period and notify listeners."""
        period, preactivated = self._calculate_active_period()
        if period != self._active_period:
            _LOGGER.info(
                "Period changed: %s -> %s (preactivated=%s)",
                self._active_period,
                period,
                preactivated,
            )
        self._active_period = period
        self._preactivated = preactivated
        self.async_set_updated_data(
            {
                "active_period": period,
                "preactivated": preactivated,
                "workday": self.is_workday(),
            }
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data (called by coordinator)."""
        period, preactivated = self._calculate_active_period()
        self._active_period = period
        self._preactivated = preactivated
        return {
            "active_period": period,
            "preactivated": preactivated,
            "workday": self.is_workday(),
        }

    def is_in_preactivation_window(self) -> bool:
        """Return True if the current time is within any period's pre-activation window."""
        now = dt_util.now()
        for period in PERIODS:
            if not self.get_preactivation_entity(period):
                continue
            if self._in_preactivation_window(period, now):
                return True
        return False

    @callback
    def advance_period(self) -> None:
        """Force-advance to the next period immediately."""
        next_period, _ = self.get_next_period()
        _LOGGER.info(
            "Advancing period: %s -> %s (forced)",
            self._active_period,
            next_period,
        )
        self._forced_period = next_period
        self._active_period = next_period
        self._preactivated = False
        self.async_set_updated_data(
            {
                "active_period": next_period,
                "preactivated": False,
                "workday": self.is_workday(),
            }
        )

    def setup_listeners(self) -> None:
        """Set up time-based and state-based listeners."""
        self._clear_listeners()

        # Listen for every minute to catch period transitions
        self._unsub_listeners.append(
            async_track_time_change(self.hass, self.recalculate, second=0)
        )

        # Listen for state changes on pre-activation entities
        preact_entities: list[str] = []
        for period in PERIODS:
            entity_id = self.get_preactivation_entity(period)
            if entity_id:
                preact_entities.append(entity_id)

        # Also listen to the workday entity
        config = self._get_config()
        workday_entity = config.get(CONF_WORKDAY_ENTITY)
        if workday_entity:
            preact_entities.append(workday_entity)

        if preact_entities:
            self._unsub_listeners.append(
                async_track_state_change_event(
                    self.hass,
                    preact_entities,
                    self._handle_state_change,
                )
            )

    @callback
    def _handle_state_change(self, event: Any) -> None:
        """Handle state change of a tracked entity."""
        self.recalculate()

    def _clear_listeners(self) -> None:
        """Remove all listeners."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

    def clear_forced_period(self) -> None:
        """Clear any latched forced/pre-activated period (e.g. when configuration changes)."""
        self._forced_period = None
        self._preactivated = False

    @callback
    def shutdown(self) -> None:
        """Clean up listeners."""
        self._clear_listeners()

    def get_next_period(self) -> tuple[str, time]:
        """Get the next period and its start time."""
        now = dt_util.now()
        current_time = now.time()

        period_times: list[tuple[time, str]] = []
        for period in PERIODS:
            start = self.get_period_start_time(period)
            period_times.append((start, period))

        period_times.sort(key=lambda x: x[0])

        for start_t, period in period_times:
            if start_t > current_time:
                return (period, start_t)

        # Wrap to the first period of the next day
        return (period_times[0][1], period_times[0][0])
