"""Document-based ticket validation, local-time conversion and lookup priorities."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import io
import json
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from validate_travel_json import ROOT, _structure, load_snapshot

MAX_FILE_BYTES = 1024 * 1024
MAX_RECORDS = 1000


def import_schema(kind: str) -> dict:
    if kind not in ("flight", "train"):
        raise ValueError("Unknown import kind")
    return json.loads((ROOT / f"main/import/{kind}.schema.json").read_text(encoding="utf-8"))


def blank(value) -> bool:
    return value is None or value == ""


def load_records(path: Path, kind=None) -> list[dict]:
    if path.suffix.lower() == ".csv":
        data = path.read_bytes()
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("Import file exceeds 1 MiB")
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
        fields = reader.fieldnames or []
        if not fields or len(fields) != len(set(fields)):
            raise ValueError("CSV headers must be present and unique")
        if kind is not None:
            schema = import_schema(kind)
            if set(fields) - set(schema["properties"]):
                raise ValueError("CSV contains undocumented headers")
            if set(schema["required"]) - set(fields):
                raise ValueError("CSV is missing required headers")
            for group in schema.get("allOf", []):
                if "anyOf" in group and not any(set(branch["required"]) <= set(fields) for branch in group["anyOf"]):
                    raise ValueError("CSV is missing identifier-code headers")
        records = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("CSV row width does not match the header")
            if any(value != "" for value in row.values()):
                records.append(row)
    else:
        value = load_snapshot(path, MAX_FILE_BYTES)
        records = value if isinstance(value, list) else [value]
    if len(records) > MAX_RECORDS:
        raise ValueError("Import batch exceeds 1000 records; split the file")
    return records


def validate_records(records: list, kind: str) -> list[str]:
    schema = import_schema(kind)
    errors = []
    if len(records) > MAX_RECORDS:
        return ["Import batch exceeds 1000 records"]
    for index, record in enumerate(records):
        path = f"records[{index}]"
        structural = _structure(record, schema, path, schema)
        errors.extend(structural)
        if structural:
            continue
        try:
            encoded = json.dumps(record, ensure_ascii=False).encode("utf-8")
            if len(encoded) > schema["x-max-record-utf8-bytes"]:
                errors.append(f"{path}: record exceeds 64 KiB")
        except UnicodeError:
            errors.append(f"{path}: invalid Unicode")
            continue
        for field, definition in schema["properties"].items():
            value = record.get(field)
            if blank(value):
                continue
            kinds = definition.get("type", [])
            if "number" in kinds or ("integer" in kinds and "pattern" in definition):
                try:
                    number = Decimal(str(value))
                    if not number.is_finite():
                        raise InvalidOperation
                    if "minimum" in definition and number < definition["minimum"]:
                        errors.append(f"{path}.{field}: below minimum")
                    if "maximum" in definition and number > definition["maximum"]:
                        errors.append(f"{path}.{field}: above maximum")
                except InvalidOperation:
                    errors.append(f"{path}.{field}: invalid numeric value")
        date_fields = ["departureTime", "arrivalTime"]
        if kind == "flight":
            date_fields += ["actualDepartureTime", "actualArrivalTime", "boardingTime"]
        pattern = "%Y-%m-%dT%H:%M" if kind == "flight" else "%Y-%m-%d %H:%M"
        for field in date_fields:
            if not blank(record.get(field)):
                try:
                    datetime.strptime(record[field], pattern)
                except ValueError:
                    errors.append(f"{path}.{field}: invalid local calendar date")
        if kind == "train":
            for field in ("departureTimeZone", "arrivalTimeZone"):
                try:
                    ZoneInfo(record[field])
                except (ZoneInfoNotFoundError, ValueError):
                    errors.append(f"{path}.{field}: unknown IANA timezone")
    return errors


def reference_candidates(record: dict, kind: str) -> dict:
    """Retain documented lookup order without claiming to resolve a catalog ID."""
    return {
        entity: [{"field": field, "value": record[field]} for field in fields
                 if field in record and not blank(record[field])]
        for entity, fields in import_schema(kind)["x-match-priority"].items()
    }


def local_to_utc(value, zone_name: str, kind: str, field: str, fold=None):
    if blank(value):
        return None
    if not isinstance(zone_name, str) or not zone_name:
        raise ValueError(f"{field}: an explicit IANA timezone is required")
    try:
        zone = ZoneInfo(zone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"{field}: invalid IANA timezone") from None
    pattern = "%Y-%m-%dT%H:%M" if kind == "flight" else "%Y-%m-%d %H:%M"
    local = datetime.strptime(value, pattern)
    candidates = {}
    for candidate_fold in (0, 1):
        aware = local.replace(tzinfo=zone, fold=candidate_fold)
        utc = aware.astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None) == local:
            candidates[candidate_fold] = int(utc.timestamp())
    if not candidates:
        raise ValueError(f"{field}: nonexistent local time during DST transition")
    if fold is not None:
        if isinstance(fold, bool) or fold not in (0, 1) or fold not in candidates:
            raise ValueError(f"{field}: fold must be 0 or 1 for a valid local time")
        return candidates[fold]
    if len(set(candidates.values())) > 1:
        raise ValueError(f"{field}: ambiguous local time; specify its fold in display context")
    return next(iter(candidates.values()))
