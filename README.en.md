[简体中文](README.md) · English

# Travel Pocket

A Chinese train and flight itinerary card application for FoloToy AI Passport.

**This version is an offline interaction prototype. All tickets are simulated;
it does not provide actual train or flight status.** Every screen labels the
source as simulated and not live. The sample date is 2026-11-17; a simulated
UTC+8 clock starts at 08:00 and advances with device uptime. Sample services,
gates and seats must not be used for travel.

## Screens and controls

- Home: service number, route, status, planned or estimated departure, gate and countdown.
- Details: planned, estimated and actual departure, planned arrival and seat. Times use UTC+8.
- Short UP/DOWN: switch tickets. Short OK: open or close details.
- Long OK in details: return home. Long OK at home: cycle normal, delayed, cancelled, offline, stale and empty scenarios.
- A double click acts as one short click. There are no simultaneous-button combinations.
- Dim after 30 idle seconds and turn off the backlight after 60. The first action while dark only wakes the screen.

Stale data has no countdown. Passing a scheduled departure never fabricates an
actual departure. The offline scenario keeps its simulated cards with an
explicit warning. Missing fields have an unavailable label. Long OK at home
continues scenario selection from stale or empty data. Unavailable battery
readings appear as `--%`.

## Boundaries

[`main/travel_app.c`](main/travel_app.c) is the firmware entry point and loads
an independent ticket interface. Baseline test sources remain for reference
and regression tests; they are not linked into the application and no app
navigation leads to the test menu. Hardware uses `components/bsp`. BSP, pin
definitions and the default partition layout are unchanged.
Radios are disabled. Tickets and scenarios live in RAM and reset on reboot.

An 18 px Noto Sans SC subset covers all fixed UI and sample ticket text. Runtime
checks use the font selected by each widget. Unsupported text gets an explicit
replacement message; arbitrary Chinese place names are not supported. Source,
license and regeneration are documented in [`assets/README.md`](assets/README.md).

[`tools/render_travel_preview.py`](tools/render_travel_preview.py) uses local LVGL 9.5.0
sources with CMake and Ninja to check native rendering. It verifies widget fonts
and text bounds across all simulated scenarios and writes PPM previews. This
does not replace device screen acceptance.

Live operation requires a selected provider, coverage/field/latency/quota and
authentication contracts, and a chosen network transport. Provisioning, time
synchronization, HTTPS, bounded JSON, retries, credential management and durable
caching are not implemented. The state model already separates source, update
and expiry times, and planned/estimated/actual departure.

Source records use separate [flight](main/import/flight.schema.json) and
[train](main/import/train.schema.json) import schemas with the documented column
names and required-field rules. JSON/CSV validation and conversion are described
in the [ticket import guide](docs/assets/ticket-import.md). The compact
[display snapshot schema](main/travel_snapshot.schema.json), font/length limits
and rendering are covered by the [JSON integration guide](docs/assets/travel-json.md).
The current device firmware still has no external JSON receiver.

## Build and acceptance

Activate ESP-IDF 5.5.3 and run:

```bash
./tools/validate.sh --static
./tools/validate.sh
```

The complete gate produces `build/FoloToy-AI-Passport-full.bin` for flashing
at `0x0` and retains matching ELF/MAP artifacts. A merged flash can reset
existing NVS data. Confirm data impact under the [firmware-layout policy](docs/development/engineering/firmware-layout.md)
and obtain user approval before flashing. Reading back the old firmware is
not a prerequisite.

On hardware, inspect both ticket types, Chinese and mixed characters, all six
scenarios, details/return, repeated navigation, dim/off/wake behavior, startup
logs, minimum heap and actual power draw. Build and glyph coverage checks do
not establish rendering or battery life.

Development rules are in [`AGENTS.md`](AGENTS.md).
