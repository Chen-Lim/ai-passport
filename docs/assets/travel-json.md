[简体中文](travel-json.zh_CN.md) · English

# eTicket JSON Contract

The authoritative [JSON Schema](../../main/travel_snapshot.schema.json) uses
Draft 2020-12 and protocol version 1. It describes complete itinerary snapshots
for the current ticket UI, with up to four train or flight trips. The
[sample snapshot](../../tests/fixtures/travel/snapshot.json) and
[empty snapshot](../../tests/fixtures/travel/empty.json) are simulated fixtures.

For source ticket columns, use the separate [flight/train import contracts](ticket-import.md).
Those schemas preserve full ticket records; this schema governs their compact UI projection.

## Input and display mapping

| Field | Required | Meaning and display |
| --- | --- | --- |
| `schema_version` | Yes | Exactly `1` |
| `timezone` | Yes | Exactly `Asia/Shanghai`; all labels use UTC+8 |
| `source` | Yes | `demo` uses the simulated-update footer prefix; `live` uses the standard update prefix |
| `revision` | Yes | Integer 1..4294967295, strictly increasing within a source stream |
| `updated_at` | Yes | UTC Unix seconds when the provider updated the snapshot; shown as last update |
| `expires_at` | Yes | UTC Unix seconds after which the snapshot is stale; must exceed `updated_at` |
| `trips` | Yes | Complete replacement list, 0..4 trips; `[]` clears it |
| `trips[].id` | Yes | Unique stable ASCII ID, up to 23 characters; include date and route in the identity |
| `kind` | Yes | `train` or `flight`, controlling transport label and gate caption |
| `service` | Yes | Large service-number label; see kind-specific patterns in the schema |
| `origin`, `destination` | Yes | Short display names, 1..4 supported characters each |
| `status` | Yes | Fixed status enum; mapping below |
| `planned_departure` | Yes | UTC Unix seconds, used for the date and planned time |
| `estimated_departure` | No | UTC seconds or `null`; when known, replaces planned time on home |
| `actual_departure` | No | UTC seconds or `null`, shown in details |
| `planned_arrival` | No | UTC seconds or `null`, shown in details; not before planned departure |
| `gate` | No | 1..7 ASCII letters/digits/hyphens, or `null` |
| `seat` | No | 1..7 characters from the seat alphabet defined by the schema, or `null` |

Optional fields omitted from JSON have the same meaning as `null`. Empty strings
are rejected: use `null` for an unknown gate or seat. The model adapter translates
unknown times to `TRAVEL_UNKNOWN_TIME` (`-1`) and unknown gate/seat to empty C
strings. JSON itself never uses `-1` as a time. Supported timestamps are
0..4102444799 seconds; millisecond timestamps and time strings are rejected.

The status enums map to existing localized labels:

| Enum | Meaning |
| --- | --- |
| `scheduled` | According to plan |
| `boarding` | Boarding in progress |
| `delayed` | Delayed |
| `departed` | Departed |
| `arrived` | Arrived |
| `cancelled` | Cancelled |
| `unknown` | Status unavailable |

Status is supplied explicitly by the data provider. Neither a departure timestamp
nor elapsed clock time fabricates a departure. Seat is displayed on the home card
and detail view.

## Text and layout compatibility

Version 1 is intentionally bounded by the current fonts and 192-pixel label
widths. Train service numbers accept up to two uppercase letters plus 1..5 digits,
three letters plus 1..4 digits, or a 6..7-digit number. `--` denotes an unspecified
train number. Flight numbers accept a two-character uppercase carrier code,
1..4 digits and an optional uppercase suffix, or three ICAO letters plus 1..4 digits.
Arbitrary long airline names are not service numbers.

Location labels accept only ASCII letters/digits and the Chinese alphabet
bundled in `travel_font_18`. The schema contains that exact alphabet. It supports
the current sample places, not arbitrary Chinese city or airport names. Send a
short ASCII location code for an unsupported place, or extend the font and
update the contract with a compatibility review. Four characters per location
allow both endpoints and the route separator to fit together. Gate and seat
limits reserve space for their existing captions.

## Validation and updates

```bash
python3 tools/validate_travel_json.py your-snapshot.json
python3 tools/validate_travel_json.py next.json --previous previous.json
```

The repository validator needs only Python's standard library and evaluates the
keywords used by this schema. Other consumers can use a Draft 2020-12 validator.
Standard JSON Schema alone cannot compare two properties or enforce uniqueness
of just `id` inside an object array. Apply these semantic checks as well:

- `expires_at > updated_at` and each trip ID is unique.
- A known planned arrival is not before planned departure.
- Compared with the previous accepted snapshot, revision strictly increases
  and update time never goes backwards. Changing `source` requires an explicit
  stream reset rather than silently mixing demo and live data.
- Raw JSON is at most 4096 UTF-8 bytes, including whitespace. Duplicate object
  keys, control characters, malformed UTF-8 and non-JSON numbers are rejected.

Do not send partial patches. A snapshot with one trip replaces the complete
list with that trip. A stale snapshot is still structurally valid: at
`now >= expires_at`, the UI keeps the cached card and marks it stale in the footer.
Rejected messages must retain the previous accepted snapshot.

Device clock validity, connectivity, selection, detail-page state and battery
readings are local state and are not payload fields. Provider update time must
not be treated as a trustworthy clock synchronization result.

## Render the JSON before device integration

After dependencies are available, use the real LVGL UI for a native preview:

```bash
python3 tools/render_travel_preview.py \
  --lvgl-source managed_components/lvgl__lvgl \
  --input tests/fixtures/travel/snapshot.json \
  --output build/json-preview
```

The renderer validates the JSON, maps it into the actual `travel_snapshot_t`,
and renders home/details for every trip. It checks selected fonts and label
bounds and writes PPM images. Preview time defaults to `updated_at`; use
`--now <UTC-seconds>` to inspect stale or elapsed-time behavior. This synthetic
preview clock is not a device clock synchronization mechanism.

## Current device boundary

The installed firmware still loads the built-in simulated scenarios. It has
no USB JSON command, BLE JSON service or network API receiver. This contract
and the native JSON renderer do not make that firmware accept external data.
The future receiver must validate and map a snapshot, set transport and clock
state independently, call `travel_state_apply()`, and update the UI under
`bsp_lvgl_lock()`. Choosing USB/BLE/Wi-Fi transport is separate from the schema.
