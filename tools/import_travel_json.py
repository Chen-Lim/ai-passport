#!/usr/bin/env python3
"""Convert validated flight/train imports to the existing display snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

from ticket_import import blank, import_schema, load_records, local_to_utc, reference_candidates, validate_records
from validate_travel_json import load_snapshot, validate_snapshot


def project_records(records, kind: str, context=None, *, source="live", revision=1,
                    updated_at=None, expires_at=None, indexes=None):
    errors = validate_records(records, kind)
    if errors:
        raise ValueError("; ".join(errors))
    context = {} if context is None else context
    if not isinstance(context, dict) or set(context) - {"departureTimeZone", "arrivalTimeZone", "records"}:
        raise ValueError("Display context has unknown fields or is not an object")
    overrides = context.get("records", [])
    if not isinstance(overrides, list) or len(overrides) > len(records):
        raise ValueError("Context records must correspond to the original input indexes")
    indexes = list(range(len(records))) if indexes is None else indexes
    if not isinstance(indexes, list) or any(type(index) is not int for index in indexes):
        raise ValueError("Display indexes must be integers")
    if len(indexes) > 4:
        raise ValueError("Display accepts at most four trips; explicitly select indexes")
    if len(indexes) != len(set(indexes)) or any(i < 0 or i >= len(records) for i in indexes):
        raise ValueError("Display indexes must be unique and within the input batch")
    updated_at = int(time.time()) if updated_at is None else updated_at
    expires_at = updated_at + 300 if expires_at is None else expires_at
    snapshot = {"schema_version": 1, "timezone": "Asia/Shanghai", "source": source,
                "revision": revision, "updated_at": updated_at, "expires_at": expires_at, "trips": []}
    metadata = {"kind": kind, "records": records, "display_indexes": indexes,
                "lookup_candidates": [], "utc_times": [], "effective_defaults": [], "warnings": []}
    schema = import_schema(kind)
    allowed = {"origin", "destination", "service", "seat", "gate", "status", "id",
               "departureTimeZone", "arrivalTimeZone", "folds"}
    for index in indexes:
        record = records[index]
        override = overrides[index] if index < len(overrides) else {}
        if not isinstance(override, dict) or set(override) - allowed:
            raise ValueError(f"Context records[{index}]: unknown fields or invalid object")
        if kind == "train":
            departure_zone, arrival_zone = record["departureTimeZone"], record["arrivalTimeZone"]
            for field in ("departureTimeZone", "arrivalTimeZone"):
                supplied = override.get(field, context.get(field))
                if supplied is not None and supplied != record[field]:
                    raise ValueError(f"records[{index}].{field}: context cannot replace the documented timezone")
        else:
            departure_zone = override.get("departureTimeZone", context.get("departureTimeZone"))
            arrival_zone = override.get("arrivalTimeZone", context.get("arrivalTimeZone"))
            if not departure_zone or not arrival_zone:
                raise ValueError("Flight local times require departureTimeZone and arrivalTimeZone in display context")
        folds = override.get("folds", {})
        time_fields = ["departureTime", "arrivalTime"]
        if kind == "flight":
            time_fields += ["actualDepartureTime", "actualArrivalTime", "boardingTime"]
        if not isinstance(folds, dict) or set(folds) - set(time_fields):
            raise ValueError(f"Context records[{index}].folds: unsupported time field")
        utc = {field: local_to_utc(record.get(field), arrival_zone if field in ("arrivalTime", "actualArrivalTime")
                                  else departure_zone, kind, field, folds.get(field)) for field in time_fields}
        if utc["arrivalTime"] is not None and utc["arrivalTime"] < utc["departureTime"]:
            raise ValueError(f"records[{index}].arrivalTime: before departure after timezone conversion")
        if utc.get("actualArrivalTime") is not None and utc.get("actualDepartureTime") is not None:
            if utc["actualArrivalTime"] < utc["actualDepartureTime"]:
                raise ValueError(f"records[{index}].actualArrivalTime: before actual departure")
        if kind == "flight":
            origin = record.get("departureIata") or record["departureIcao"]
            destination = record.get("arrivalIata") or record["arrivalIcao"]
            service = record["flightNo"].strip().upper()
            gate = record.get("departureGate") or None
            seat = record.get("seatNo") or None
            service_status = record.get("serviceStatus") or "normal"
            status = "cancelled" if service_status == "cancelled" else "unknown"
            if service_status in ("returned", "diverted"):
                metadata["warnings"].append(f"records[{index}].serviceStatus: preserved in metadata; current UI has no dedicated state")
            identity = [kind, record.get("airlineId"), record.get("airlineIcao"), record.get("airlineIata"),
                        record["flightNo"], record["departureTime"], origin, destination, record.get("passengerName")]
        else:
            origin, destination = record["departureStation"], record["arrivalStation"]
            service = (record.get("trainNo") or "--").strip().upper()
            gate = record.get("ticketGate") or None
            car, number = record.get("carNo") or "", record.get("seatNo") or ""
            seat = f"{car}车 {number}".strip() if car else number or None
            status = "unknown"
            identity = [kind, record.get("railwayOperator"), record.get("trainNo"), record["departureTime"],
                        origin, destination, record.get("passengerName"), record.get("passengerType")]
        digest = hashlib.sha256(json.dumps(identity, ensure_ascii=True).encode("utf-8")).hexdigest()
        trip = {"id": f"{kind[0]}-{digest[:20]}", "kind": kind, "service": service,
                "origin": origin, "destination": destination, "status": status,
                "planned_departure": utc["departureTime"], "planned_arrival": utc["arrivalTime"],
                "estimated_departure": None, "actual_departure": utc.get("actualDepartureTime"),
                "gate": gate, "seat": seat.strip().upper() if seat else None}
        for field in ("origin", "destination", "service", "seat", "gate", "status", "id"):
            if field in override:
                trip[field] = override[field]
        if kind == "flight" and service_status == "cancelled" and trip["status"] != "cancelled":
            raise ValueError(f"records[{index}].serviceStatus: cancelled flight cannot be presented as active")
        snapshot["trips"].append(trip)
        metadata["lookup_candidates"].append({"index": index, "candidates": reference_candidates(record, kind)})
        metadata["utc_times"].append({"index": index, "times": utc})
        metadata["effective_defaults"].append({"index": index, "values": {
            field: definition["default"] if blank(record.get(field)) else record[field]
            for field, definition in schema["properties"].items() if "default" in definition}})
    errors = validate_snapshot(snapshot)
    if errors:
        raise ValueError("Display projection rejected: " + "; ".join(errors) + ". Use context for display-label overrides when needed.")
    return snapshot, metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--kind", choices=("flight", "train"), required=True)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--metadata-output", type=Path)
    parser.add_argument("--source", choices=("demo", "live"), default="live")
    parser.add_argument("--revision", type=int, default=1)
    parser.add_argument("--updated-at", type=int)
    parser.add_argument("--expires-at", type=int)
    parser.add_argument("--indexes", help="comma-separated, zero-based input indexes; at most four")
    args = parser.parse_args()
    try:
        inputs = {args.input.resolve()}
        if args.context:
            inputs.add(args.context.resolve())
        outputs = [path.resolve() for path in (args.output, args.metadata_output) if path]
        if inputs.intersection(outputs) or len(outputs) != len(set(outputs)):
            raise ValueError("Output paths must differ from the input, context and each other")
        records = load_records(args.input, args.kind)
        context = load_snapshot(args.context, 65536) if args.context else None
        indexes = [int(index) for index in args.indexes.split(",")] if args.indexes is not None else None
        snapshot, metadata = project_records(records, args.kind, context, source=args.source,
                                             revision=args.revision, updated_at=args.updated_at,
                                             expires_at=args.expires_at, indexes=indexes)
        for message in metadata["warnings"]:
            print(message, file=sys.stderr)
        text = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        if args.metadata_output:
            args.metadata_output.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, UnicodeError, OverflowError, RecursionError) as error:
        print(f"Ticket import failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
