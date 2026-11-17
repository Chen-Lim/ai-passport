#!/usr/bin/env python3
"""Regression tests for the two documented ticket import contracts."""

import copy
import csv
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from ticket_import import import_schema, load_records, local_to_utc, reference_candidates, validate_records  # noqa: E402
from import_travel_json import project_records  # noqa: E402
from validate_travel_json import validate_snapshot  # noqa: E402


class TicketImportTest(unittest.TestCase):
    def setUp(self):
        self.flight = json.loads((ROOT / "tests/fixtures/travel/import-flight.json").read_text())
        self.train = json.loads((ROOT / "tests/fixtures/travel/import-train.json").read_text())
        self.context = {"departureTimeZone": "Asia/Shanghai", "arrivalTimeZone": "Asia/Shanghai"}

    def project(self, records, kind, context=None, **kwargs):
        return project_records(records, kind, context, source="demo", updated_at=1794873600, **kwargs)

    def test_all_source_fields_and_export_ids_are_present(self):
        flight, train = import_schema("flight"), import_schema("train")
        self.assertEqual(len(flight["x-source-fields"]), 46)
        self.assertEqual(len(flight["properties"]), 52)
        self.assertEqual(set(flight["properties"])-set(flight["x-source-fields"]),
                         {"airlineId", "operatingAirlineId", "departureAirportId", "arrivalAirportId", "stopoverAirportIds", "aircraftTypeId"})
        self.assertEqual(len(train["x-source-fields"]), 38)
        self.assertEqual(set(train["properties"]), set(train["x-source-fields"]))
        self.assertEqual(set(train["x-required-allow-empty"]), {"railwayOperator", "trainNo", "arrivalTime", "carNo", "seatNo"})
        self.assertTrue(set(train["x-required-allow-empty"]).issubset(train["required"]))

    def test_flight_required_code_alternatives(self):
        self.assertEqual(validate_records([self.flight], "flight"), [])
        for left, right in [("airlineIata", "airlineIcao"), ("departureIata", "departureIcao"), ("arrivalIata", "arrivalIcao")]:
            value = copy.deepcopy(self.flight)
            value[left] = None
            self.assertEqual(validate_records([value], "flight"), [])
            value[right] = ""
            self.assertTrue(validate_records([value], "flight"))
        value = copy.deepcopy(self.flight)
        value.update(airlineId="opaque", airlineIata=None, airlineIcao=None)
        self.assertTrue(validate_records([value], "flight"))

    def test_yellow_fields_are_required_but_allow_null_or_empty(self):
        fields = import_schema("train")["x-required-allow-empty"]
        for empty in (None, ""):
            value = copy.deepcopy(self.train)
            for field in fields:
                value[field] = empty
            self.assertEqual(validate_records([value], "train"), [])
            snapshot, _ = self.project([value], "train")
            self.assertEqual(snapshot["trips"][0]["service"], "--")
            self.assertIsNone(snapshot["trips"][0]["planned_arrival"])
            self.assertIsNone(snapshot["trips"][0]["seat"])
        for field in fields:
            value = copy.deepcopy(self.train)
            value.pop(field)
            self.assertTrue(validate_records([value], "train"), field)
        value = copy.deepcopy(self.train)
        value["departureStation"] = ""
        self.assertTrue(validate_records([value], "train"))

    def test_time_formats_and_calendar_validity(self):
        value = copy.deepcopy(self.flight)
        value["departureTime"] = "2026-09-22 13:10"
        self.assertTrue(validate_records([value], "flight"))
        value["departureTime"] = "2026-02-30T13:10"
        self.assertTrue(validate_records([value], "flight"))
        value = copy.deepcopy(self.train)
        value["departureTime"] = "2026-11-17T09:15"
        self.assertTrue(validate_records([value], "train"))
        value = copy.deepcopy(self.train)
        value["departureTimeZone"] = "Area/NotAZone"
        self.assertTrue(validate_records([value], "train"))

    def test_all_railway_operators_and_exact_enum_case(self):
        schema = import_schema("train")
        operators = [op for op in schema["properties"]["railwayOperator"]["enum"] if op]
        self.assertEqual(len(operators), 75)
        for op in operators:
            self.train["railwayOperator"] = op
            self.assertEqual(validate_records([self.train], "train"), [])
        self.train["railwayOperator"] = "CR"
        self.assertTrue(validate_records([self.train], "train"))
        self.train["railwayOperator"] = "cr"
        for propulsion in ("hdmu", "bemu", "eLoco", "dLoco", "sLoco"):
            self.train["propulsionType"] = propulsion
            self.assertEqual(validate_records([self.train], "train"), [])
        self.train["propulsionType"] = "eloco"
        self.assertTrue(validate_records([self.train], "train"))

    def test_numeric_csv_cells_and_coordinates(self):
        self.flight.update(priceCashAmount="650.5", redeemedPoints="2000", earnedPoints=0)
        self.assertEqual(validate_records([self.flight], "flight"), [])
        self.flight["priceCashAmount"] = "-1"
        self.assertTrue(validate_records([self.flight], "flight"))
        self.flight["priceCashAmount"] = 650.5
        self.flight["redeemedPoints"] = "2.5"
        self.assertTrue(validate_records([self.flight], "flight"))
        self.train["departureStationLng"] = "181"
        self.assertTrue(validate_records([self.train], "train"))
        self.train["departureStationLng"] = "-0.1253"
        self.train["arrivalStationLat"] = "51.53"
        self.assertEqual(validate_records([self.train], "train"), [])

    def test_catalog_priority_is_retained_without_resolving_ids(self):
        self.flight.update(airlineId=0, departureAirportId="airport-id", aircraftTypeId=1,
                           aircraftTypeIcao="B737", aircraftTypeName="Boeing 737-700",
                           operatingAirlineId="carrier-id", operatingAirlineIata="MU", stopoverAirportIds="1;2")
        refs = reference_candidates(self.flight, "flight")
        self.assertEqual([p["field"] for p in refs["airline"]], ["airlineId", "airlineIcao", "airlineIata"])
        self.assertEqual(refs["airline"][0]["value"], 0)
        self.assertEqual([p["field"] for p in refs["aircraftType"]], ["aircraftTypeId", "aircraftTypeIcao", "aircraftTypeName"])
        self.assertEqual([p["field"] for p in refs["stopoverAirports"]], ["stopoverAirportIds", "stopoverAirports"])

    def test_cross_timezone_conversion_and_no_timezone_guessing(self):
        self.flight.update(departureIata="JFK", departureIcao="KJFK", arrivalIata="LHR", arrivalIcao="EGLL",
                           departureTime="2026-09-22T10:00", arrivalTime="2026-09-22T20:00")
        with self.assertRaises(ValueError):
            self.project([self.flight], "flight")
        snapshot, _ = self.project([self.flight], "flight", {"departureTimeZone":"America/New_York", "arrivalTimeZone":"Europe/London"})
        trip = snapshot["trips"][0]
        self.assertEqual(trip["planned_arrival"]-trip["planned_departure"], 5*3600)
        self.assertEqual(validate_snapshot(snapshot), [])
        self.flight["arrivalTime"] = "2026-09-22T14:00"
        with self.assertRaisesRegex(ValueError, "before departure"):
            self.project([self.flight], "flight", {"departureTimeZone":"America/New_York", "arrivalTimeZone":"Europe/London"})

    def test_dst_ambiguity_and_nonexistent_wall_time(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            local_to_utc("2026-11-01T01:30", "America/New_York", "flight", "departureTime")
        first = local_to_utc("2026-11-01T01:30", "America/New_York", "flight", "departureTime", 0)
        second = local_to_utc("2026-11-01T01:30", "America/New_York", "flight", "departureTime", 1)
        self.assertEqual(second-first, 3600)
        with self.assertRaisesRegex(ValueError, "nonexistent"):
            local_to_utc("2026-03-08T02:30", "America/New_York", "flight", "departureTime")

    def test_refunds_are_not_service_cancellations_and_no_status_inference(self):
        self.flight.update(changeFlag="origRefunded", actualDepartureTime="2026-09-22T13:20",
                           actualArrivalTime="2026-09-22T15:30", boardingTime="2026-09-22T12:40",
                           operatingFlightNo="MU754", departureTerminal="T1")
        snapshot, meta = self.project([self.flight], "flight", self.context)
        trip = snapshot["trips"][0]
        self.assertEqual(trip["status"], "unknown")
        self.assertEqual(trip["service"], "CA790")
        self.assertIsNone(trip["estimated_departure"])
        self.assertNotEqual(trip["planned_arrival"], meta["utc_times"][0]["times"]["actualArrivalTime"])
        self.flight["serviceStatus"] = "cancelled"
        self.assertEqual(self.project([self.flight], "flight", self.context)[0]["trips"][0]["status"], "cancelled")
        self.train["changeFlag"] = "refunded"
        self.assertEqual(self.project([self.train], "train")[0]["trips"][0]["status"], "unknown")

    def test_full_metadata_and_unsupported_service_states_are_preserved(self):
        self.flight.update(passengerName="Test Passenger", eTicketNo="0000000000000", barcode="TEST-CODE", serviceStatus="diverted")
        original = copy.deepcopy(self.flight)
        snapshot, meta = self.project([self.flight], "flight", self.context)
        self.assertEqual(meta["records"][0], original)
        self.assertNotIn("passengerName", snapshot["trips"][0])
        self.assertEqual(meta["effective_defaults"][0]["values"]["barcodeFormat"], "qr")
        self.assertTrue(meta["warnings"])

    def test_import_names_are_not_limited_by_the_screen_font(self):
        self.train.update(departureStation="北京西", arrivalStation="香港西九龙", arrivalRegionCode="HK")
        self.assertEqual(validate_records([self.train], "train"), [])
        with self.assertRaisesRegex(ValueError, "Display projection rejected"):
            self.project([self.train], "train")
        snapshot, meta = self.project([self.train], "train", {"records":[{"origin":"BJW","destination":"HKW"}]})
        self.assertEqual(snapshot["trips"][0]["origin"], "BJW")
        self.assertEqual(meta["records"][0]["arrivalStation"], "香港西九龙")

    def test_csv_bom_leading_zeros_and_duplicate_headers(self):
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(self.train))
        writer.writeheader(); writer.writerow(self.train)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"tickets.csv"
            path.write_bytes(b'\xef\xbb\xbf' + buffer.getvalue().encode('utf-8'))
            records = load_records(path)
            self.assertEqual(records[0]["carNo"], "08")
            self.assertEqual(records[0]["trainsetNumbers"], self.train["trainsetNumbers"])
            self.assertEqual(validate_records(records, "train"), [])
            path.write_text("trainNo,trainNo\nG1,G2\n")
            with self.assertRaises(ValueError):load_records(path)
            path.write_text("unknownHeader\n")
            with self.assertRaises(ValueError):load_records(path, "train")

    def test_converter_never_overwrites_source_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"tickets.json"
            original = json.dumps(self.train, ensure_ascii=False)
            path.write_text(original)
            result = subprocess.run([sys.executable, str(ROOT/"tools/import_travel_json.py"), str(path),
                                     "--kind", "train", "--output", str(path)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_text(), original)

    def test_explicit_selection_and_station_timezone_override(self):
        records = [copy.deepcopy(self.train) for _ in range(5)]
        for i, record in enumerate(records):record["trainNo"] = f"G{i+1}"
        with self.assertRaises(ValueError):self.project(records, "train")
        self.assertEqual(len(self.project(records, "train", indexes=[0,4])[0]["trips"]), 2)
        with self.assertRaises(ValueError):self.project([self.train], "train", {"departureTimeZone":"Asia/Tokyo"})


if __name__ == "__main__":
    unittest.main()
