# Time of Day


A Home Assistant custom integration that divides the day into four named periods — **Morning**, **Afternoon**, **Evening**, and **Night** — and exposes them as entities you can use in automations and dashboards.

Key features:

- Different start times for **workdays** vs. **non-workdays** (driven by any binary sensor)
- **Pre-activation**: a period can be triggered early when a designated entity turns ON within a configurable time window before the scheduled start
- **Latch behaviour**: once a period is pre-activated or force-advanced it stays active until its natural start time passes, even if the trigger entity turns back OFF
- A **button** and a **service** to manually skip to the next period



## Time of Day – Functional Description

This package divides each day into four consecutive periods: **Morning**, **Afternoon**, **Evening**, and **Night**. Only one period is active at any given time, tracked by a dedicated binary sensor for each period and summarised in a single text sensor (`sensor.time_of_day`) that exposes the name of the currently active period.

### Working day vs non-working day

All time thresholds are defined separately for working days and non-working days, allowing schedules to shift on weekends and holidays. The distinction between the two day types is determined by an external boolean input (e.g. a Home Assistant workday sensor or a custom helper).

### How a period becomes active

Each period has two activation mechanisms, and whichever fires first wins:

1. **Preactivation** – Each period defines a boolean condition (configured externally in Home Assistant) that represents real-world signals associated with that time of day — for example, the coffee machine switching on, the alarm being disarmed, or the first light being turned on. If that condition becomes true during the period's *preactivation window* (a configurable time interval ending at the period's latest-start time), the period activates immediately.

2. **Latest-start time** – If the preactivation condition never triggers, the period activates automatically at its configured latest-start time. This is a hard deadline that guarantees a transition regardless of activity signals.

### Preactivation window

The preactivation window opens at most as far back as the previous period's latest-start time, and can be narrowed down to zero (disabling early activation entirely for that period). This prevents a signal that is ambiguous — one that could belong to either period — from triggering the wrong transition.

### Example

Morning is configured with a latest-start of **08:30** and a preactivation window of **60 minutes** (opening at 07:30). The preactivation condition is true if the coffee machine or toaster activates, or the alarm panel is disarmed. If any of those events occur between 07:30 and 08:30, Morning activates immediately.

---

## Table of contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Entities](#entities)
5. [Service](#service)
6. [Pre-activation in depth](#pre-activation-in-depth)
7. [Latch behaviour](#latch-behaviour)
8. [Examples](#examples)

---

## Requirements

- Home Assistant 2024.1 or later
- A workday binary sensor (e.g. the built-in [Workday](https://www.home-assistant.io/integrations/workday/) integration) — optional but recommended

---

## Installation

### HACS (recommended)

1. Open HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add this repository URL and select category **Integration**
3. Install **Time of Day** and restart Home Assistant

### Manual

1. Copy the `custom_components/time_of_day/` folder into your `<config>/custom_components/` directory
2. Restart Home Assistant

---

## Configuration

Go to **Settings → Devices & Services → Add Integration** and search for **Time of Day**. Only one instance is allowed.

### Step 1 — Workday sensor

| Field | Description |
|---|---|
| **Workday sensor** | A `binary_sensor` or `input_boolean` that is `on` on workdays and `off` on non-workdays (e.g. weekends, public holidays). If left blank every day is treated as a workday. |

### Step 2 — Period settings

The same fields are repeated for each of the four periods.

| Field | Key | Default | Description |
|---|---|---|---|
| **Start (workday)** | `{period}_workday_time` | see below | Time this period starts on workday days (HH:MM) |
| **Start (non-workday)** | `{period}_non_workday_time` | see below | Time this period starts on non-workday days |
| **Pre-activation window** | `{period}_preactivation_window` | `0` (disabled) | Minutes before the scheduled start time during which the pre-activation entity can trigger early activation. Range 0–240. |
| **Pre-activation entity** | `{period}_preactivation_entity` | — | `binary_sensor` or `input_boolean` that triggers early activation when turned ON inside the window. Optional. |

#### Default start times

| Period | Workday | Non-workday |
|---|---|---|
| Morning | 07:00 | 08:30 |
| Afternoon | 12:00 | 12:00 |
| Evening | 18:00 | 18:00 |
| Night | 22:00 | 23:00 |

> **Constraint**: start times must be strictly ascending — Morning < Afternoon < Evening < Night — for both workday and non-workday schedules. The UI will reject the form otherwise.

All settings are editable at any time via **Settings → Devices & Services → Time of Day → Configure**.

---

## Entities

All entities belong to a single **Time of Day** device.

### Sensor — `sensor.time_of_day_active_period`

Shows the name of the currently active period.

| State | Meaning |
|---|---|
| `Morning` | Morning is active |
| `Afternoon` | Afternoon is active |
| `Evening` | Evening is active |
| `Night` | Night is active |

**Attributes**

| Attribute | Type | Description |
|---|---|---|
| `workday` | boolean | Whether today is a workday |
| `preactivated` | boolean | Whether the current period was triggered by pre-activation (or force-advanced) |
| `start_time` | `HH:MM` | Scheduled start time of the current period |
| `next_period` | string | Name of the upcoming period |
| `next_period_start_time` | `HH:MM` | Scheduled start time of the upcoming period |

---

### Binary sensors — one per period

| Entity | ID suffix | Icon |
|---|---|---|
| Morning | `binary_sensor.time_of_day_morning` | `mdi:weather-sunset-up` |
| Afternoon | `binary_sensor.time_of_day_afternoon` | `mdi:weather-sunny` |
| Evening | `binary_sensor.time_of_day_evening` | `mdi:weather-sunset-down` |
| Night | `binary_sensor.time_of_day_night` | `mdi:weather-night` |

Each sensor is `on` while its period is the active one and `off` otherwise.

**Attributes**

| Attribute | Type | Description |
|---|---|---|
| `start_time` | `HH:MM` | Scheduled start time for today |
| `preactivation_window_minutes` | int | Configured pre-activation window (0 = disabled) |
| `preactivation_entity` | string | Entity ID of the pre-activation trigger (if configured) |
| `workday` | boolean | Whether today is a workday |
| `preactivated` | boolean | Present and `true` only while this period is active AND it was pre-activated or force-advanced |

---

### Binary sensor — `binary_sensor.time_of_day_pre_activation_window`

`on` when the current time falls inside **any** period's pre-activation window, regardless of whether the trigger entity is on or not. Useful as a condition in automations ("are we in a window right now?").

---

### Button — `button.time_of_day_advance_period`

Pressing it immediately advances to the next period. Equivalent to calling the `time_of_day.advance_period` service. The advanced period is latched until its natural start time passes.

---

## Service

### `time_of_day.advance_period`

Skips to the next period immediately. No parameters.

```yaml
service: time_of_day.advance_period
```

The forced period behaves exactly like a pre-activated one: it stays active until its natural scheduled time arrives, then the latch is cleared automatically.

---

## Pre-activation in depth

Pre-activation lets a period start early when an external condition (the pre-activation entity) is met within a look-ahead window.

### How the window is calculated

Given a period with:
- scheduled start time `T`
- pre-activation window `W` minutes

The window is the half-open interval **[T − W, T)**.

Example — Morning at 07:00 with a 60-minute window:

```
06:00 ──────────────── 07:00
  ↑                      ↑
window opens          window closes / Morning starts naturally
```

### Triggering conditions

All three must be true simultaneously:
1. The current time is inside the window `[T − W, T)`
2. The pre-activation entity is `on`
3. The period has not yet started naturally

When all three are met, the period activates immediately and is **latched** (see below).

### What does NOT trigger pre-activation

- The entity was already `on` before the window opened — the coordinator checks the entity state at each minute tick and on every state change, so it will catch it at the first evaluation inside the window.
- The window is 0 (default) — pre-activation is disabled for that period.
- No pre-activation entity is configured.

---

## Latch behaviour

A period becomes **latched** in two situations:

| Situation | How |
|---|---|
| Pre-activated | The pre-activation entity turned ON inside the window |
| Force-advanced | The button was pressed or the service was called |

While latched, the coordinator ignores both the natural period schedule **and** the state of the pre-activation entity. The latched period stays active until the natural scheduled time for that period passes — at which point the latch is cleared and normal scheduling resumes.

This means:
- Turning the pre-activation entity back OFF will **not** revert to the previous period.
- Pressing "Advance Period" twice in quick succession will latch the second-next period.

---

## Examples

### Automation: adjust lights when the period changes

```yaml
automation:
  alias: "Lights follow time of day"
  trigger:
    - platform: state
      entity_id: sensor.time_of_day_active_period
  action:
    - choose:
        - conditions:
            - condition: state
              entity_id: sensor.time_of_day_active_period
              state: Morning
          sequence:
            - service: scene.turn_on
              target:
                entity_id: scene.morning_lights
        - conditions:
            - condition: state
              entity_id: sensor.time_of_day_active_period
              state: Evening
          sequence:
            - service: scene.turn_on
              target:
                entity_id: scene.evening_lights
        - conditions:
            - condition: state
              entity_id: sensor.time_of_day_active_period
              state: Night
          sequence:
            - service: scene.turn_on
              target:
                entity_id: scene.night_lights
```

---

### Automation: different thermostat setpoints per period

```yaml
automation:
  alias: "Thermostat follows time of day"
  trigger:
    - platform: state
      entity_id: sensor.time_of_day_active_period
  variables:
    setpoints:
      Morning: 21
      Afternoon: 20
      Evening: 22
      Night: 18
  action:
    - service: climate.set_temperature
      target:
        entity_id: climate.living_room
      data:
        temperature: "{{ setpoints[trigger.to_state.state] | default(20) }}"
```

---

### Automation: pre-activate Morning when the alarm goes off

Configure Morning with a 60-minute pre-activation window and set the pre-activation entity to `input_boolean.alarm_triggered`.

Then trigger that boolean from your alarm automation:

```yaml
automation:
  alias: "Alarm triggers early Morning"
  trigger:
    - platform: state
      entity_id: binary_sensor.phone_alarm_ringing
      to: "on"
  action:
    - service: input_boolean.turn_on
      target:
        entity_id: input_boolean.alarm_triggered
```

When the alarm fires between 06:00 and 07:00 (the pre-activation window), the Morning period activates immediately instead of waiting until 07:00.

---

### Automation: skip a period manually with a dashboard button

The button entity can be added directly to a Lovelace card:

```yaml
type: button
entity: button.time_of_day_advance_period
name: Skip to next period
show_state: false
```

Or call the service from an automation:

```yaml
automation:
  alias: "Skip to Evening when movie starts"
  trigger:
    - platform: state
      entity_id: media_player.living_room_tv
      to: playing
  condition:
    - condition: state
      entity_id: sensor.time_of_day_active_period
      state: Afternoon
  action:
    - service: time_of_day.advance_period
```

---

### Template: time until next period

```yaml
template:
  - sensor:
      - name: "Time until next period"
        state: >
          {% set now_h = now().hour %}
          {% set now_m = now().minute %}
          {% set next = state_attr('sensor.time_of_day_active_period', 'next_period_start_time') %}
          {% if next %}
            {% set parts = next.split(':') %}
            {% set next_h = parts[0] | int %}
            {% set next_m = parts[1] | int %}
            {% set diff = (next_h * 60 + next_m) - (now_h * 60 + now_m) %}
            {% set diff = diff if diff > 0 else diff + 1440 %}
            {{ (diff // 60) ~ 'h ' ~ (diff % 60) ~ 'm' }}
          {% else %}
            unknown
          {% endif %}
```

---

### Condition: only run during Evening on workdays

```yaml
condition:
  - condition: state
    entity_id: binary_sensor.time_of_day_evening
    state: "on"
  - condition: template
    value_template: "{{ state_attr('sensor.time_of_day_active_period', 'workday') == true }}"
```

---

### Notification when pre-activation window opens

```yaml
automation:
  alias: "Notify when pre-activation window opens"
  trigger:
    - platform: state
      entity_id: binary_sensor.time_of_day_pre_activation_window
      to: "on"
  action:
    - service: notify.mobile_app
      data:
        message: >
          Pre-activation window is now open.
          Next period: {{ state_attr('sensor.time_of_day_active_period', 'next_period') }}
          at {{ state_attr('sensor.time_of_day_active_period', 'next_period_start_time') }}.
```
