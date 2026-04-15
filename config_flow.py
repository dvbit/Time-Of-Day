"""Config flow for Time of Day integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TimeSelector,
)

from .const import (
    CONF_NON_WORKDAY_TIME,
    CONF_PREACTIVATION_ENTITY,
    CONF_PREACTIVATION_WINDOW,
    CONF_WORKDAY_ENTITY,
    CONF_WORKDAY_TIME,
    DEFAULT_PREACTIVATION,
    DEFAULT_TIMES,
    DOMAIN,
    PERIOD_NAMES,
    PERIODS,
)


def _period_key(period: str, key: str) -> str:
    """Build a config key for a specific period."""
    return f"{period}_{key}"


def _parse_time_str(time_str: str) -> tuple[int, int]:
    """Parse HH:MM:SS or HH:MM to (hour, minute)."""
    parts = time_str.split(":")
    return (int(parts[0]), int(parts[1]))


def _validate_time_order(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate that period start times are in chronological order.

    Checks both workday and non-workday times independently.
    Returns a dict of errors (empty if valid).
    """
    errors: dict[str, str] = {}

    for time_key, label in (
        (CONF_WORKDAY_TIME, "workday"),
        (CONF_NON_WORKDAY_TIME, "non-workday"),
    ):
        times: list[tuple[str, tuple[int, int]]] = []
        for period in PERIODS:
            key = _period_key(period, time_key)
            val = user_input.get(key)
            if val:
                times.append((period, _parse_time_str(val)))

        for i in range(1, len(times)):
            prev_period, prev_t = times[i - 1]
            curr_period, curr_t = times[i]
            if curr_t <= prev_t:
                errors["base"] = "times_not_chronological"
                return errors

    return errors


def _build_period_schema(
    defaults: dict[str, Any],
) -> dict[vol.Marker, Any]:
    """Build the schema for all period configurations."""
    schema: dict[vol.Marker, Any] = {}

    for period in PERIODS:
        name = PERIOD_NAMES[period]

        workday_time_key = _period_key(period, CONF_WORKDAY_TIME)
        non_workday_time_key = _period_key(period, CONF_NON_WORKDAY_TIME)
        preact_window_key = _period_key(period, CONF_PREACTIVATION_WINDOW)
        preact_entity_key = _period_key(period, CONF_PREACTIVATION_ENTITY)

        schema[
            vol.Required(
                workday_time_key,
                default=defaults.get(
                    workday_time_key, DEFAULT_TIMES[period]["workday"]
                ),
            )
        ] = TimeSelector()

        schema[
            vol.Required(
                non_workday_time_key,
                default=defaults.get(
                    non_workday_time_key, DEFAULT_TIMES[period]["non_workday"]
                ),
            )
        ] = TimeSelector()

        schema[
            vol.Required(
                preact_window_key,
                default=defaults.get(
                    preact_window_key, DEFAULT_PREACTIVATION[period]
                ),
            )
        ] = NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=240,
                step=5,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement="minutes",
            )
        )

        schema[
            vol.Optional(
                preact_entity_key,
                description={"suggested_value": defaults.get(preact_entity_key)},
            )
        ] = EntitySelector(
            EntitySelectorConfig(
                domain=["binary_sensor", "input_boolean"],
                multiple=False,
            )
        )

    return schema


class TimeOfDayConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Time of Day."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        """Handle the initial step."""
        # Only allow one instance
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_time_order(user_input)
            if not errors:
                return self.async_create_entry(
                    title="Time of Day",
                    data={CONF_WORKDAY_ENTITY: user_input[CONF_WORKDAY_ENTITY]},
                    options={
                        k: v
                        for k, v in user_input.items()
                        if k != CONF_WORKDAY_ENTITY
                    },
                )

        schema: dict[vol.Marker, Any] = {
            vol.Required(CONF_WORKDAY_ENTITY): EntitySelector(
                EntitySelectorConfig(
                    domain=["binary_sensor", "input_boolean"],
                    multiple=False,
                )
            ),
        }
        schema.update(_build_period_schema(user_input or {}))

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return TimeOfDayOptionsFlow(config_entry)


class TimeOfDayOptionsFlow(OptionsFlow):
    """Handle options flow for Time of Day."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_time_order(user_input)
            if not errors:
                # Update the workday entity in data if changed
                new_data = dict(self._config_entry.data)
                if CONF_WORKDAY_ENTITY in user_input:
                    new_data[CONF_WORKDAY_ENTITY] = user_input.pop(
                        CONF_WORKDAY_ENTITY
                    )
                    self.hass.config_entries.async_update_entry(
                        self._config_entry, data=new_data
                    )

                return self.async_create_entry(title="", data=user_input)

        current = {**self._config_entry.data, **self._config_entry.options}
        if user_input:
            current.update(user_input)

        schema: dict[vol.Marker, Any] = {
            vol.Required(
                CONF_WORKDAY_ENTITY,
                default=current.get(CONF_WORKDAY_ENTITY),
            ): EntitySelector(
                EntitySelectorConfig(
                    domain=["binary_sensor", "input_boolean"],
                    multiple=False,
                )
            ),
        }
        schema.update(_build_period_schema(current))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=errors,
        )
