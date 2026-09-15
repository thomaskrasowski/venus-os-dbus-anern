"""Offline evidence semantics; no test contacts Cerbo or other hardware."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("power_diagnostics", ROOT / "tools" / "power_diagnostics.py")
diagnostics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostics)

BATTERY = "com.victronenergy.battery.example"


def observation(value, status="ok"):
    return {"status": status, "value": value}


def record(elapsed=0, index=1, connected=1, soc=55, owner=":1.1", **changes):
    sample = {"schema_version": 1, "type": "sample", "source": "cerbo", "session_id": "session1",
              "captured_at": "2026-09-14T12:00:00Z", "elapsed_seconds": elapsed,
              "collection_duration_seconds": 0.5, "discovery_success": True, "discovery_truncated": False,
              "devices": [{"service": BATTERY, "owner": owner, "owner_consistent": True,
                           "snapshot_consistent": True, "read_method": "GetItems", "values": {
                               "/Connected": observation(connected), "/UpdateIndex": observation(index),
                               "/Soc": observation(soc), "/Dc/0/Voltage": observation(51.2),
                               "/Dc/0/Current": observation(-12.0), "/Dc/0/Power": observation(-614.4)}}],
              "can": {"status": "not_collected"}, "bluetooth": {"status": "not_collected"}}
    sample.update(changes)
    return sample


def values(sample):
    return sample["devices"][0]["values"]


def last(records, **kwargs):
    return diagnostics.analyze(records, **kwargs)["devices"][0]["latest"]


class ObservationTests(unittest.TestCase):
    def test_zero_is_a_real_observation(self):
        sample = record(soc=0)
        values(sample)["/Dc/0/Current"] = observation(0)
        values(sample)["/Dc/0/Power"] = observation(0)
        result = last([sample])
        self.assertEqual(result["status"], "usable")
        self.assertEqual(result["values"]["soc"], 0)
        self.assertEqual(result["values"]["current"], 0)
        self.assertEqual(result["values"]["power"], 0)

    def test_missing_soc_keeps_voltage_current_and_qualifies_diagnosis(self):
        sample = record()
        values(sample)["/Soc"] = observation(None, "missing")
        report = diagnostics.analyze([sample])
        result = report["devices"][0]["latest"]
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["values"]["soc"])
        self.assertEqual(result["values"]["voltage"], 51.2)
        events = [e for e in report["events"] if e["kind"] == "soc_missing_with_voltage_current"]
        self.assertEqual(len(events), 1)
        self.assertIn("does not prove", events[0]["message"])

    def test_missing_voltage_or_current_is_partial(self):
        for path in ("/Dc/0/Voltage", "/Dc/0/Current"):
            sample = record()
            del values(sample)[path]
            self.assertEqual(last([sample])["status"], "partial")

    def test_invalid_measurements_are_not_zero(self):
        for invalid in (None, True, "55", [], float("nan"), float("inf"), -1, 101):
            with self.subTest(value=invalid):
                sample = record(soc=invalid)
                result = last([sample])
                self.assertIsNone(result["values"]["soc"])
                self.assertNotEqual(result["field_status"]["soc"], "ok")

    def test_error_is_not_missing_or_zero(self):
        sample = record()
        values(sample)["/Soc"] = observation(None, "error")
        result = last([sample])
        self.assertEqual(result["field_status"]["soc"], "error")
        self.assertIsNone(result["values"]["soc"])

    def test_disconnected_retained_values_are_withheld(self):
        result = last([record(connected=0)])
        self.assertEqual(result["status"], "disconnected")
        self.assertTrue(all(value is None for value in result["values"].values()))
        self.assertEqual(result["raw_values"]["/Soc"]["value"], 55)

    def test_owner_and_snapshot_incoherence_withholds_numbers(self):
        for field in ("owner_consistent", "snapshot_consistent"):
            sample = record()
            sample["devices"][0][field] = False
            result = last([sample])
            self.assertEqual(result["status"], "incoherent")
            self.assertTrue(all(value is None for value in result["values"].values()))

    def test_no_owner_is_unknown(self):
        self.assertEqual(last([record(owner=None)])["status"], "unknown")

    def test_no_telemetry_is_unknown_not_healthy(self):
        sample = record()
        sample["devices"][0]["service"] = "com.victronenergy.settings"
        sample["devices"][0]["values"] = {"/Connected": observation(1)}
        self.assertEqual(last([sample])["status"], "unknown")

    def test_no_bank_or_transport_inferred(self):
        report = diagnostics.analyze([record()])
        device = report["devices"][0]
        self.assertEqual(device["bank"], "unassigned")
        self.assertEqual(device["transport"], "unknown")

    def test_mapping_is_explicit_and_does_not_aggregate_banks(self):
        sample = record()
        second = copy.deepcopy(sample["devices"][0])
        second["service"] = BATTERY + "2"
        sample["devices"].append(second)
        mapping = {"devices": {BATTERY: {"bank": "battery1", "label": "JK 1", "transport": "bluetooth"},
                               BATTERY + "2": {"bank": "battery2", "transport": "can"}}}
        report = diagnostics.analyze([sample], mapping)
        self.assertEqual([d["bank"] for d in report["devices"]], ["battery1", "battery2"])
        self.assertEqual(len(report["devices"]), 2)
        self.assertNotIn("energy", report)

    def test_no_power_derived_from_voltage_and_current(self):
        sample = record()
        del values(sample)["/Dc/0/Power"]
        self.assertIsNone(last([sample])["values"]["power"])

    def test_grid_and_inverter_identical_path_have_different_meanings(self):
        for kind in ("grid", "inverter"):
            sample = record()
            sample["devices"][0]["service"] = "com.victronenergy." + kind + ".example"
            values(sample)["/Ac/L1/Power"] = observation(-300)
            result = last([sample])
            self.assertEqual(result["values"]["grid_l1_power"], -300 if kind == "grid" else None)
            self.assertEqual(result["values"]["ac_output_power"], -300 if kind == "inverter" else None)

    def test_invalid_raw_numbers_still_allow_strict_json_report(self):
        report = diagnostics.analyze([record(soc=float("nan"))])
        json.dumps(report, allow_nan=False)

    def test_system_measurements_keep_source_identity(self):
        sample = record()
        sample["devices"][0]["service"] = "com.victronenergy.system"
        sample["devices"][0]["values"] = {
            "/Dc/Battery/Voltage": observation(51.2), "/Dc/Battery/Current": observation(12),
            "/Dc/Battery/VoltageService": observation("com.victronenergy.inverter.anern2"),
            "/AutoSelectedBatteryService": observation(BATTERY)}
        report = diagnostics.analyze([sample])
        device = report["devices"][0]
        self.assertEqual(device["bank"], "unassigned")
        self.assertIn("sources may differ", device["label"])
        self.assertEqual(device["latest"]["values"]["voltage"], 51.2)
        self.assertFalse(any(event["kind"] == "soc_missing_with_voltage_current" for event in report["events"]))
        self.assertIn("/Dc/Battery/VoltageService", device["latest"]["metadata"]["source_paths"])
        self.assertIn("/AutoSelectedBatteryService", device["latest"]["metadata"]["source_paths"])

    def test_observer_discovery_failure_visible_without_any_device(self):
        sample = record(devices=[], discovery_success=False, errors=["D-Bus discovery: NoReply"],
                        host={"status": "partial", "load_average": [0.4, 0.3, 0.2]},
                        logs={"status": "ok", "text": "sample kernel message", "truncated": False})
        report = diagnostics.analyze([sample])
        self.assertEqual(report["devices"], [])
        observer = report["observer"][0]
        self.assertFalse(observer["discovery_success"])
        self.assertIn("NoReply", observer["errors"][0])
        self.assertEqual(observer["host"]["status"], "partial")
        self.assertEqual(observer["logs"]["text"], "sample kernel message")
        self.assertEqual(observer["collection_duration_seconds"], 0.5)

    def test_observer_json_safe_and_does_not_mutate_input(self):
        sample = record(host={"load_average": [float("nan")]})
        report = diagnostics.analyze([sample])
        json.dumps(report, allow_nan=False)
        self.assertIn("invalid_nonfinite", report["observer"][0]["host"]["load_average"][0])
        self.assertIsInstance(sample["host"]["load_average"][0], float)

    def test_can_only_sample_is_labelled_and_controller_details_are_preserved(self):
        sample = record(devices=[], scope="can", discovery_success=False,
            bluetooth={"status": "not_collected"}, can={"status": "ok", "interfaces": [{
                "name": "vecan1", "stats": {"tx_dropped": 71},
                "controller": {"state": "ERROR-PASSIVE", "bitrate": 500000,
                    "counters": {"bus_off": 19}},
                "delta": {"status": "baseline", "stats": {},
                    "controller_counters": {}, "reset_detected": []}}]})
        report = diagnostics.analyze([sample])
        self.assertEqual(report["observer"][0]["scope"], "can")
        interface = report["transport"]["can"][0]["snapshot"]["interfaces"][0]
        self.assertEqual(interface["controller"]["state"], "ERROR-PASSIVE")
        self.assertEqual(interface["controller"]["counters"]["bus_off"], 19)


class ContinuityTests(unittest.TestCase):
    def test_index_stalls_gap_numbers_and_resumes_on_change(self):
        report = diagnostics.analyze([record(0), record(20), record(40), record(45, index=2)])
        samples = report["devices"][0]["samples"]
        self.assertEqual([s["status"] for s in samples], ["usable", "usable", "stale", "usable"])
        self.assertIsNone(samples[2]["values"]["voltage"])
        self.assertEqual(samples[2]["field_status"]["voltage"], "withheld_stale")
        self.assertEqual(samples[3]["freshness"], "index_advanced")

    def test_unchanged_value_does_not_mean_stale_with_advancing_index(self):
        result = last([record(0), record(100, index=2)])
        self.assertEqual(result["status"], "usable")

    def test_changing_values_do_not_override_stalled_index(self):
        second = record(100, soc=60)
        self.assertEqual(last([record(), second])["status"], "stale")

    def test_unsupported_index_is_unverified(self):
        first, second = record(), record(100)
        for item in (first, second):
            del values(item)["/UpdateIndex"]
        result = last([first, second])
        self.assertEqual(result["status"], "usable")
        self.assertEqual(result["freshness"], "unverified")

    def test_owner_change_resets_stale_timer(self):
        report = diagnostics.analyze([record(), record(100, owner=":1.2")])
        self.assertEqual(report["devices"][0]["latest"]["status"], "usable")
        self.assertIn("owner_changed", [event["kind"] for event in report["events"]])
        self.assertNotEqual(report["devices"][0]["samples"][0]["segment"], report["devices"][0]["samples"][1]["segment"])

    def test_owner_lookup_failure_is_unknown_not_owner_change(self):
        for owner in (None, ":1.2"):
            sample = record(10, owner=owner)
            sample["devices"][0].update(owner_check_status="error", owner_consistent=False,
                                        snapshot_consistent=None)
            report = diagnostics.analyze([record(), sample])
            self.assertEqual(report["devices"][0]["latest"]["status"], "unknown")
            self.assertFalse(any(event["kind"] == "owner_changed" for event in report["events"]))

    def test_owner_null_without_new_status_is_unknown_and_no_change_event(self):
        sample = record(10, owner=None)
        sample["devices"][0]["owner_consistent"] = False
        report = diagnostics.analyze([record(), sample])
        self.assertEqual(report["devices"][0]["latest"]["status"], "unknown")
        self.assertFalse(any(event["kind"] == "owner_changed" for event in report["events"]))

    def test_owner_verification_error_does_not_replace_last_confirmed_owner(self):
        failed = record(10, owner=":1.2")
        failed["devices"][0].update(owner_check_status="error", owner_consistent=False,
                                    snapshot_consistent=None)
        report = diagnostics.analyze([record(), failed, record(20)])
        self.assertFalse(any(event["kind"] == "owner_changed" for event in report["events"]))

    def test_no_outage_inferred_before_first_service_observation(self):
        report = diagnostics.analyze([record(devices=[]), record(10)])
        self.assertEqual(report["devices"][0]["samples"][0]["status"], "unknown")

    def test_long_unobserved_period_breaks_chart(self):
        report = diagnostics.analyze([record(), record(100, index=2)])
        samples = report["devices"][0]["samples"]
        self.assertNotEqual(samples[0]["segment"], samples[1]["segment"])
        self.assertEqual(samples[1]["status"], "usable")

    def test_index_wrap_is_activity(self):
        self.assertEqual(last([record(index=255), record(100, index=0)])["status"], "usable")

    def test_complete_discovery_absence_and_return(self):
        report = diagnostics.analyze([record(), record(10, devices=[]), record(20)])
        self.assertEqual([s["status"] for s in report["devices"][0]["samples"]], ["usable", "missing", "usable"])
        self.assertIn("service_reappeared", [event["kind"] for event in report["events"]])

    def test_failed_or_truncated_discovery_is_unknown(self):
        for change in ({"discovery_success": False}, {"discovery_truncated": True}):
            result = last([record(), record(10, devices=[], **change)])
            self.assertEqual(result["status"], "unknown")

    def test_sessions_and_files_break_stale_timer_and_chart_lines(self):
        for change in ({"session_id": "session2"}, {"_capture_file": "new"}):
            report = diagnostics.analyze([record(100), record(0, **change)])
            samples = report["devices"][0]["samples"]
            self.assertEqual(samples[-1]["status"], "usable")
            self.assertNotEqual(samples[0]["segment"], samples[1]["segment"])
            self.assertEqual(report["summary"]["duration_seconds"], 0)

    def test_monotonic_reset_without_new_session_rejected(self):
        with self.assertRaisesRegex(diagnostics.CaptureError, "increase"):
            diagnostics.analyze([record(20), record(10)])

    def test_wallclock_change_does_not_change_duration(self):
        first = record(captured_at="2026-09-14T12:00:00Z")
        second = record(15, index=2, captured_at="2026-09-14T10:00:00Z")
        report = diagnostics.analyze([first, second])
        self.assertEqual(report["summary"]["duration_seconds"], 15)
        self.assertIn("clock_moved_backwards", [event["kind"] for event in report["events"]])


class TransportTests(unittest.TestCase):
    @staticmethod
    def can(errors):
        return {"status": "ok", "interfaces": [{"name": "can0", "stats": {"rx_errors": errors, "rx_packets": 100}}]}

    def test_counter_increase_and_reset_are_distinct(self):
        report = diagnostics.analyze([record(can=self.can(5)), record(10, can=self.can(7)), record(20, can=self.can(0))])
        events = [event for event in report["events"] if event["kind"].startswith("can_")]
        self.assertEqual([event["kind"] for event in events], ["can_counter_increase", "can_counter_reset"])
        self.assertTrue(all(event["device"] == "can:can0" for event in events))

    def test_counter_history_does_not_cross_sessions(self):
        report = diagnostics.analyze([record(can=self.can(5)), record(0, session_id="next", can=self.can(0))])
        self.assertFalse(any(event["kind"].startswith("can_") for event in report["events"]))

    def test_partial_can_snapshot_retains_valid_counter_evidence(self):
        first, second = self.can(5), self.can(7)
        first["status"] = second["status"] = "partial"
        report = diagnostics.analyze([record(can=first), record(10, can=second)])
        self.assertIn("can_counter_increase", [event["kind"] for event in report["events"]])

    def test_bluetooth_transition_does_not_assign_battery(self):
        bt = lambda connected: {"status": "ok", "devices": [{"path": "/org/bluez/hci0/dev_example", "connected": connected}]}
        report = diagnostics.analyze([record(bluetooth=bt(True)), record(10, bluetooth=bt(False))])
        event = next(event for event in report["events"] if event["kind"] == "bluetooth_connected_changed")
        self.assertTrue(event["device"].startswith("bluetooth:"))
        self.assertEqual(report["devices"][0]["transport"], "unknown")


class InputTests(unittest.TestCase):
    def test_loader_file_boundaries_and_no_final_newline(self):
        with tempfile.TemporaryDirectory() as directory:
            files = [Path(directory) / "one.jsonl", Path(directory) / "two.jsonl"]
            for path in files:
                path.write_text(json.dumps(record()), encoding="utf-8")
            records = diagnostics.load_records(files)
            self.assertNotEqual(records[0]["_capture_file"], records[1]["_capture_file"])
            self.assertEqual(diagnostics.analyze(records)["summary"]["sessions"], 2)

    def test_truncated_file_has_line_context(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.jsonl"
            path.write_text(json.dumps(record()) + '\n{"schema_version":', encoding="utf-8")
            with self.assertRaisesRegex(diagnostics.CaptureError, "capture.jsonl:2"):
                diagnostics.load_records([path])

    def test_duplicate_keys_and_nonfinite_json_rejected(self):
        for text in ('{"key":1,"key":2}', '{"value":NaN}', '{"value":Infinity}', '{"value":1e400}'):
            with self.assertRaises(diagnostics.CaptureError):
                diagnostics._parse_json(text)

    def test_collector_error_is_explained(self):
        with self.assertRaisesRegex(diagnostics.CaptureError, "local_system_bus_unavailable"):
            diagnostics.analyze([{"schema_version": 1, "type": "error", "error": "local_system_bus_unavailable"}])

    def test_invalid_schema_time_and_discovery_are_rejected(self):
        for change in ({"schema_version": 2}, {"captured_at": "2026-09-14T12:00:00"},
                       {"elapsed_seconds": float("nan")}, {"discovery_success": "yes"}):
            with self.assertRaises(diagnostics.CaptureError):
                diagnostics.analyze([record(**change)])

    def test_empty_input_and_invalid_mapping_rejected(self):
        with self.assertRaises(diagnostics.CaptureError):
            diagnostics.analyze([])
        with self.assertRaises(diagnostics.CaptureError):
            diagnostics.analyze([record()], {"devices": []})

    def test_duplicate_service_rejected(self):
        sample = record()
        sample["devices"].append(copy.deepcopy(sample["devices"][0]))
        with self.assertRaises(diagnostics.CaptureError):
            diagnostics.analyze([sample])


if __name__ == "__main__":
    unittest.main()
