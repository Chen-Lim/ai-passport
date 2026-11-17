#!/usr/bin/env python3
"""Validate the repository's display snapshots or documented ticket imports.

Uses only the standard library. The structural evaluator supports the keywords
used by the repository's schemas, not arbitrary third-party schemas.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "main/travel_snapshot.schema.json").read_text(encoding="utf-8"))


def _type_matches(value, kind: str) -> bool:
    return {
        "object": lambda: isinstance(value, dict),
        "array": lambda: isinstance(value, list),
        "string": lambda: isinstance(value, str),
        "integer": lambda: (isinstance(value, int) and not isinstance(value, bool))
                           or (isinstance(value, float) and math.isfinite(value) and value.is_integer()),
        "number": lambda: isinstance(value, (int, float)) and not isinstance(value, bool)
                          and (not isinstance(value, float) or math.isfinite(value)),
        "null": lambda: value is None,
    }[kind]()


def _structure(value, schema: dict, path: str, root_schema=None) -> list[str]:
    root_schema = root_schema if root_schema is not None else SCHEMA
    errors = []
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            raise ValueError("Only repository-local definition references are supported")
        return _structure(value, root_schema["$defs"][ref.split("/")[-1]], path, root_schema)
    if "type" in schema:
        kinds = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_matches(value, kind) for kind in kinds):
            return [f"{path}: expected {' or '.join(kinds)}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: incorrect protocol constant")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: not a supported enum value")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}.{name}: required")
        if schema.get("additionalProperties") is False:
            for name in value.keys() - properties.keys():
                errors.append(f"{path}.{name}: unknown field")
        for name, child in properties.items():
            if name in value:
                errors.extend(_structure(value[name], child, f"{path}.{name}", root_schema))
    if isinstance(value, list):
        if len(value) > schema.get("maxItems", len(value)):
            errors.append(f"{path}: too many itineraries")
        if "items" in schema:
            for index, item in enumerate(value):
                errors.extend(_structure(item, schema["items"], f"{path}[{index}]", root_schema))
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", len(value)):
            errors.append(f"{path}: display text length is out of range")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: unsupported characters or service format")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            errors.append(f"{path}: numeric value out of range")
    for child in schema.get("allOf", []):
        errors.extend(_structure(value, child, path, root_schema))
    if "anyOf" in schema and not any(not _structure(value, child, path, root_schema) for child in schema["anyOf"]):
        errors.append(f"{path}: {schema.get('title', 'none of the permitted alternatives matched')}")
    if "not" in schema and not _structure(value, schema["not"], path, root_schema):
        errors.append(f"{path}: control characters are not allowed")
    if "if" in schema:
        branch = "then" if not _structure(value, schema["if"], path, root_schema) else "else"
        if branch in schema:
            errors.extend(_structure(value, schema[branch], path, root_schema))
    return errors


def validate_snapshot(value, previous=None) -> list[str]:
    errors = _structure(value, SCHEMA, "$")
    if errors:
        return errors
    if value["expires_at"] <= value["updated_at"]:
        errors.append("$.expires_at: must be greater than updated_at")
    ids = set()
    for index, trip in enumerate(value["trips"]):
        path = f"$.trips[{index}]"
        if trip["id"] in ids:
            errors.append(f"{path}.id: duplicate itinerary ID")
        ids.add(trip["id"])
        arrival = trip.get("planned_arrival")
        if arrival is not None and arrival < trip["planned_departure"]:
            errors.append(f"{path}.planned_arrival: before planned_departure")
        for field, capacity in (("id", 23), ("service", 15), ("origin", 39), ("destination", 39), ("gate", 23), ("seat", 23)):
            text = trip.get(field)
            if text is not None and len(text.encode("utf-8")) > capacity:
                errors.append(f"{path}.{field}: exceeds firmware UTF-8 byte capacity")
    if previous is not None:
        if validate_snapshot(previous):
            return errors + ["previous snapshot is invalid"]
        if value["source"] != previous["source"]:
            errors.append("$.source: changing the source requires an explicit stream reset")
        if value["revision"] <= previous["revision"]:
            errors.append("$.revision: must strictly increase")
        if value["updated_at"] < previous["updated_at"]:
            errors.append("$.updated_at: must not move backwards")
    return errors


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"Non-JSON numeric constant: {value}")


def load_snapshot(path: Path, max_bytes=None):
    max_bytes = SCHEMA["x-max-utf8-bytes"] if max_bytes is None else max_bytes
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise ValueError(f"JSON message exceeds {max_bytes} UTF-8 bytes")
    return json.loads(data.decode("utf-8"), object_pairs_hook=_object, parse_constant=_constant)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--kind", choices=("snapshot", "flight", "train"), default="snapshot")
    parser.add_argument("--previous", type=Path, help="also enforce update ordering against this snapshot")
    args = parser.parse_args()
    try:
        if args.kind != "snapshot":
            if args.previous:
                raise ValueError("--previous applies only to display snapshots")
            from ticket_import import load_records, validate_records
            records = load_records(args.input, args.kind)
            errors = validate_records(records, args.kind)
            if errors:
                for error in errors:
                    print(error, file=sys.stderr)
                return 1
            print(f"Ticket import: PASS ({len(records)} {args.kind} records)")
            return 0
        value = load_snapshot(args.input)
        previous = load_snapshot(args.previous) if args.previous else None
        errors = validate_snapshot(value, previous)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
    except (OSError, ValueError, UnicodeError, RecursionError) as error:
        print(f"Invalid travel JSON: {error}", file=sys.stderr)
        return 1
    print(f"Travel JSON: PASS ({len(value['trips'])} itineraries, source={value['source']}, revision={value['revision']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
