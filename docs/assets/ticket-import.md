[简体中文](ticket-import.zh_CN.md) · English

# Ticket Import Contracts

Use two independent single-record schemas:

- [Flight import](../../main/import/flight.schema.json), from the [flight field guide](https://thedafeige.feishu.cn/wiki/FZd6wOGRniIWytkDoh9cfy2gnmg), section 2, revision 1090.
- [Train import](../../main/import/train.schema.json), from the [train field guide](https://thedafeige.feishu.cn/wiki/Xr1Gwz6g7iDCIKk10w5cGDrTnVd), section 2, revision 1668.

They retain original camelCase column names. Flight import covers all 46 table
fields and the six exported ID fields described in the notes. Train import
covers all 38 table fields and all 75 listed railway operators. Different
required/empty rules, local-time syntax and enums make separate contracts useful.
The [display snapshot](../../main/travel_snapshot.schema.json) remains the compact
UI protocol; conversion produces that protocol rather than replacing it with
all ticket metadata.

## Required values and empty cells

Flight records require `flightNo`, `departureTime` and `arrivalTime`, plus a
nonempty value in each pair:

- `airlineIata` or `airlineIcao`;
- `departureIata` or `departureIcao`;
- `arrivalIata` or `arrivalIcao`.

The unused alternative can be omitted, `null` or an empty string. The optional
exported IDs retain the documented matching priority; they do not remove the
guide's explicit code-pair requirement. IATA airline codes have two characters,
airport IATA codes three, airline ICAO codes three and airport ICAO codes four.

Train records require these nonempty values:

`departureStation`, `departureRegionCode`, `arrivalStation`, `arrivalRegionCode`,
`departureTime`, `departureTimeZone`, `arrivalTimeZone`, `seatType`.

The yellow columns are also required properties, but accept `null` or `""`:

`railwayOperator`, `trainNo`, `arrivalTime`, `carNo`, `seatNo`.

This supports historical tickets with unknown arrival, unspecified train numbers,
and unreserved/no-seat journeys. Region/currency codes retain their documented
two-/three-character forms. Text fields have no display-font or four-character
limit at import time. Car, seat and ticket numbers remain strings, retaining
leading zeros. Opaque exported IDs and sequence numbers accept strings or
integers because the guides do not specify a JSON representation.

## Time and numeric handling

- Flights use local `yyyy-MM-ddTHH:mm` strings. Arrival and actual-arrival times
  use the arrival airport's timezone; departure, actual-departure and boarding
  times use the departure airport's timezone.
- Trains use local `yyyy-MM-dd HH:mm` strings and their explicit
  `departureTimeZone`/`arrivalTimeZone` fields.
- Calendar dates and known IANA zones are checked. Flight projection requires
  explicit zones in a separate context file because the flight guide has no
  timezone columns. No zone is inferred from a country, airline or airport code.
- UTC chronology is checked after conversion. DST gaps are rejected; ambiguous
  repeated local times require an explicit `fold` of 0 or 1 in context.
- Numbers can be typed JSON numbers or CSV-style numeric strings. Costs,
  points and distance use a nonnegative validation policy; longitude is within
  -180..180 and latitude -90..90. Integer points reject fractional values.

The schema records documented enum defaults; ordinary JSON Schema validation
does not insert them. Conversion reports their effective values in metadata.
Examples include flight `serviceStatus=normal`, `barcodeFormat=qr`,
`reimburseStatus=no`, and train `propulsionType=unknown`, `qrCodeFormat=qr`.
Train reimbursement accepts `yes` or empty, while flight reimbursement also
accepts `no`. Enum spelling and case are preserved, including `dynamicUrl`,
`eLoco`, `afterChangingStation` and `origRefunded`.

## Validate JSON or CSV

```bash
python3 tools/validate_travel_json.py --kind flight tests/fixtures/travel/import-flight.json
python3 tools/validate_travel_json.py --kind train tests/fixtures/travel/import-train.json
python3 tools/validate_travel_json.py --kind train tickets.csv
```

Each schema describes one record. The CLI also accepts an array of homogeneous
records or UTF-8 CSV with matching headers, including an optional BOM. It rejects
duplicate headers/JSON keys, malformed rows, unknown columns and invalid values.
Import files are bounded to 1 MiB and 1000 rows, with 64 KiB per decoded record;
these are local tooling budgets, not limits asserted by the external guides.

## Convert to the current UI

```bash
python3 tools/import_travel_json.py tests/fixtures/travel/import-flight.json \
  --kind flight --context tests/fixtures/travel/flight-context.json \
  --source demo --updated-at 1790049600 \
  --output build/imported-flight.json --metadata-output build/imported-flight-metadata.json

python3 tools/import_travel_json.py tests/fixtures/travel/import-train.json \
  --kind train --source demo --updated-at 1794873600 \
  --output build/imported-train.json

python3 tools/render_travel_preview.py --lvgl-source managed_components/lvgl__lvgl \
  --input build/imported-flight.json --output build/import-preview
```

Conversion defaults to source `live`, revision 1, import receipt time as
`updated_at`, and a 300-second expiry. This is import freshness, not proof that
a real-time provider checked the service. Set `--revision`, `--updated-at` and
`--expires-at` explicitly when merging provider updates. More than four imported
records require an explicit zero-based selection, such as `--indexes 0,2,4`;
conversion never silently drops the remainder.

| Import field | Display result |
| --- | --- |
| `flightNo` / `trainNo` | Service number; a blank train number shows `--` |
| Airport IATA/ICAO / station name | Route labels |
| `departureTime` | `planned_departure` after timezone conversion |
| `arrivalTime` | `planned_arrival`; blank train arrival becomes `null` |
| `actualDepartureTime` | `actual_departure` |
| `departureGate` / `ticketGate` | Gate; terminals and waiting rooms are not substituted |
| `seatNo`, train `carNo` | Seat, retaining car-number leading zeros |
| Flight `serviceStatus=cancelled` | `cancelled` |
| Other ticket records | `unknown` unless explicit runtime status is supplied in context |

`boardingTime` is not an estimated departure. `actualArrivalTime` does not
overwrite planned arrival. Codeshare carrier/flight, stopovers, ticket changes,
passenger, pricing, equipment, QR/barcode and other source fields remain in the
original input and optional metadata output. Refunds and exchanges describe the
ticket, and do not turn a running train or flight into a cancelled service.
`returned` and `diverted` are retained with a warning because the current UI has
no dedicated state for them. Conversion never fetches barcode/dynamic URLs.

## Display context and metadata

The [flight context example](../../tests/fixtures/travel/flight-context.json)
provides departure and arrival IANA zones. A `records` array can override short
UI labels by original input index:

```json
{
  "departureTimeZone": "Asia/Shanghai",
  "arrivalTimeZone": "Asia/Shanghai",
  "records": [
    { "origin": "BJW", "destination": "HKW", "service": "G108" }
  ]
}
```

These short labels are display aliases, not an assertion that they are catalog
station codes. Context can supply `id`, `origin`, `destination`, `service`,
`gate`, `seat`, `status`, and per-flight timezones. It cannot replace a train's
documented timezone or present a cancelled flight as active. A per-record
`folds` object uses source time-field names, for example
`{"departureTime":0,"arrivalTime":1}` for a repeated DST hour.

Display labels are then checked against the current font, lengths and service
patterns. Long/unsupported source names require explicit short labels or future
font/UI work. The device still displays all converted times in UTC+8.

Metadata retains source records, converted UTC times, effective defaults and
ordered lookup candidates: airline/airports use ID before ICAO before IATA,
codeshare carriers ID before IATA, stopovers ID before code and aircraft ID
before ICAO before name. No catalog lookup is performed, so ID/code consistency
and existence are not claimed. Metadata can contain passenger and ticket/QR
information; keep it local and out of commits. Only the compact snapshot is
intended for the device.

Train and flight records are validated separately. Their projected trip lists
can then share one display snapshot, keeping the total at most four and using
one coherent revision/update/expiry envelope.

The device's external JSON receiver remains unimplemented. These tools validate,
convert and preview imports locally; they do not transmit to the USB device or
import into the external ticket app.
