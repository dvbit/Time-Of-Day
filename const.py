"""Constants for the Time of Day integration."""

from homeassistant.const import Platform

DOMAIN = "time_of_day"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]

SERVICE_ADVANCE_PERIOD = "advance_period"

# Periods in chronological order
PERIOD_MORNING = "morning"
PERIOD_AFTERNOON = "afternoon"
PERIOD_EVENING = "evening"
PERIOD_NIGHT = "night"

PERIODS = [PERIOD_MORNING, PERIOD_AFTERNOON, PERIOD_EVENING, PERIOD_NIGHT]

PERIOD_NAMES = {
    PERIOD_MORNING: "Morning",
    PERIOD_AFTERNOON: "Afternoon",
    PERIOD_EVENING: "Evening",
    PERIOD_NIGHT: "Night",
}

PERIOD_ICONS = {
    PERIOD_MORNING: "mdi:weather-sunset-up",
    PERIOD_AFTERNOON: "mdi:weather-sunny",
    PERIOD_EVENING: "mdi:weather-sunset-down",
    PERIOD_NIGHT: "mdi:weather-night",
}

# Config keys
CONF_WORKDAY_ENTITY = "workday_entity"

# Per-period config keys (prefixed with period name)
CONF_WORKDAY_TIME = "workday_time"
CONF_NON_WORKDAY_TIME = "non_workday_time"
CONF_PREACTIVATION_WINDOW = "preactivation_window"
CONF_PREACTIVATION_ENTITY = "preactivation_entity"

# Default start times
DEFAULT_TIMES = {
    PERIOD_MORNING: {"workday": "07:00:00", "non_workday": "08:30:00"},
    PERIOD_AFTERNOON: {"workday": "12:00:00", "non_workday": "12:00:00"},
    PERIOD_EVENING: {"workday": "18:00:00", "non_workday": "18:00:00"},
    PERIOD_NIGHT: {"workday": "22:00:00", "non_workday": "23:00:00"},
}

# Default pre-activation windows (minutes)
DEFAULT_PREACTIVATION = {
    PERIOD_MORNING: 60,
    PERIOD_AFTERNOON: 0,
    PERIOD_EVENING: 0,
    PERIOD_NIGHT: 0,
}
