"""Offline collector tests. No system bus or hardware is opened."""

import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("cerbo_diagnostics", Path(__file__).parents[1] / "tools" / "cerbo_diagnostics.py")
diagnostics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostics)
SERVICE = "com.victronenergy.battery.test"


class DBusError(Exception):
    def __init__(self, name):
        self.name = "org.freedesktop.DBus.Error." + name

    def get_dbus_name(self):
        return self.name


class FakeBus:
    def __init__(self, items=None):
        self.items = items if items is not None else {"/Soc": {"Value": 50},
            "/Connected": {"Value": 1}, "/Dc/0/Voltage": {"Value": 52},
            "/Dc/0/Current": {"Value": -4}}
        self.calls = []
        self.owners = [":1.7", ":1.7"]
        self.names = [SERVICE]
        self.bulk_error = None
        self.discovery_error = None
        self.updates = [5, 5, 5]
        self.bluez_objects = {}

    def call_blocking(self, destination, path, interface, member, signature, args, timeout):
        self.calls.append((destination, path, interface, member, args, timeout))
        if member == "ListNames":
            if self.discovery_error:
                raise self.discovery_error
            return self.names
        if member == "GetNameOwner":
            owner = self.owners.pop(0) if len(self.owners) > 1 else self.owners[0]
            if isinstance(owner, Exception):
                raise owner
            return owner
        if member == "GetItems":
            if self.bulk_error:
                raise self.bulk_error
            return self.items
        if member == "GetValue":
            if path == "/UpdateIndex":
                return self.updates.pop(0) if len(self.updates) > 1 else self.updates[0]
            if path not in self.items:
                raise DBusError("UnknownObject")
            return self.items[path]["Value"]
        if member == "GetManagedObjects":
            return self.bluez_objects
        raise AssertionError("Unexpected D-Bus method: " + member)


class CollectorTests(unittest.TestCase):
    def read(self, bus):
        return diagnostics.read_device(bus, SERVICE, diagnostics.Budget(10))

    def test_bulk_scalar_missing_invalid_and_zero_are_distinct(self):
        bus = FakeBus({"/Soc": {"Value": []}, "/Dc/0/Current": {"Value": 0},
                       "/Dc/0/Power": {"Value": float("nan")},
                       "/ProductName": {"Value": "JK test"},
                       "/Secret": {"Value": "not allowlisted"}})
        result = self.read(bus)
        self.assertEqual(result["values"]["/Soc"]["status"], "invalid")
        self.assertEqual(result["values"]["/Dc/0/Voltage"]["status"], "missing")
        self.assertEqual(result["values"]["/Dc/0/Current"], {"status": "ok", "value": 0})
        self.assertEqual(result["values"]["/Dc/0/Power"]["status"], "invalid")
        self.assertNotIn("/Secret", result["values"])
        self.assertTrue(result["snapshot_consistent"])
        self.assertTrue(result["owner_consistent"])
        json.dumps(result, allow_nan=False)

    def test_read_calls_bind_unique_owner_with_timeouts(self):
        bus = FakeBus()
        self.read(bus)
        for destination, path, interface, member, args, timeout in bus.calls:
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, diagnostics.CALL_TIMEOUT)
            self.assertIn(member, ("GetNameOwner", "GetItems"))
            if interface == diagnostics.BUS_ITEM:
                self.assertEqual(destination, ":1.7")

    def test_owner_change_invalidates_snapshot(self):
        bus = FakeBus()
        bus.owners = [":1.7", ":1.8"]
        result = self.read(bus)
        self.assertFalse(result["owner_consistent"])
        self.assertEqual(result["owner_check_status"], "changed")
        self.assertFalse(result["snapshot_consistent"])

    def test_owner_lookup_failures_are_unknown_not_proven_owner_changes(self):
        for owners in ([DBusError("NoReply")], [":1.7", DBusError("NoReply")]):
            with self.subTest(owners=owners):
                bus = FakeBus()
                bus.owners = owners
                result = self.read(bus)
                self.assertFalse(result["owner_consistent"])
                self.assertEqual(result["owner_check_status"], "error")
                self.assertIsNone(result["snapshot_consistent"])

    def test_timeout_is_error_and_does_not_trigger_fallback(self):
        bus = FakeBus()
        bus.bulk_error = DBusError("NoReply")
        result = self.read(bus)
        self.assertEqual(result["error"], "org.freedesktop.DBus.Error.NoReply")
        self.assertEqual(result["values"], {})
        self.assertNotIn("GetValue", [c[3] for c in bus.calls])

    def test_legacy_fallback_coherence_and_missing_paths(self):
        bus = FakeBus()
        bus.bulk_error = DBusError("UnknownMethod")
        result = self.read(bus)
        self.assertEqual(result["read_method"], "GetValue")
        self.assertTrue(result["snapshot_consistent"])
        self.assertEqual(result["values"]["/Pv/0/Power"]["status"], "missing")
        bus.updates = [5, 6, 7]
        result = self.read(bus)
        self.assertFalse(result["snapshot_consistent"])

    def test_changed_connected_invalidates_fallback_even_without_update_index(self):
        bus = FakeBus()
        bus.bulk_error = DBusError("UnknownMethod")
        original = bus.call_blocking
        connected = [0, 1, 1]
        def without_index(destination, path, interface, member, signature, args, timeout):
            if member == "GetValue" and path == "/UpdateIndex":
                raise DBusError("UnknownObject")
            if member == "GetValue" and path == "/Connected":
                return connected.pop(0)
            return original(destination, path, interface, member, signature, args, timeout)
        bus.call_blocking = without_index
        result = self.read(bus)
        self.assertEqual(result["values"]["/UpdateIndex"]["status"], "missing")
        self.assertFalse(result["snapshot_consistent"])

    def test_changed_index_invalidates_fallback_even_without_connected(self):
        bus = FakeBus({"/Soc": {"Value": 50}})
        bus.bulk_error = DBusError("UnknownMethod")
        bus.updates = [5, 6, 7]
        result = self.read(bus)
        self.assertEqual(result["values"]["/Connected"]["status"], "missing")
        self.assertFalse(result["snapshot_consistent"])

    def test_budget_exhaustion_stops_bus_calls(self):
        now = [0.0]
        budget = diagnostics.Budget(1, clock=lambda: now[0])
        now[0] = 2.0
        bus = FakeBus()
        result = diagnostics.read_device(bus, SERVICE, budget)
        self.assertEqual(bus.calls, [])
        self.assertEqual(result["values"]["/Soc"]["status"], "error")
        self.assertFalse(result["owner_consistent"])

    def test_slow_fallback_stays_inside_global_budget(self):
        now = [0.0]
        bus = FakeBus()
        bus.bulk_error = DBusError("UnknownMethod")
        original = bus.call_blocking
        def slow_call(*args, **kwargs):
            now[0] += min(0.2, kwargs["timeout"])
            return original(*args, **kwargs)
        bus.call_blocking = slow_call
        result = diagnostics.read_device(bus, SERVICE, diagnostics.Budget(1.5, clock=lambda: now[0]))
        self.assertLessEqual(now[0], 1.5)
        self.assertLess(len(bus.calls), 15)
        self.assertEqual(result["values"]["/Ac/In/L3/P"]["status"], "error")
        self.assertTrue(result["owner_consistent"])

    def test_failed_discovery_does_not_claim_bluetooth_absent(self):
        bus = FakeBus()
        bus.discovery_error = DBusError("NoReply")
        result = diagnostics.collect_sample(bus, "session", 0,
            can_reader=lambda budget: {"status": "ok", "interfaces": []})
        self.assertFalse(result["discovery_success"])
        self.assertEqual(result["bluetooth"]["status"], "unknown")
        self.assertTrue(result["errors"])

    def test_malformed_discovery_is_failure(self):
        bus = FakeBus()
        bus.names = "bad reply"
        result = diagnostics.collect_sample(bus, "session", 0,
            can_reader=lambda budget: {"status": "ok", "interfaces": []})
        self.assertFalse(result["discovery_success"])
        self.assertEqual(result["bluetooth"]["status"], "unknown")

    def test_source_selection_names_remain_text_and_are_allowlisted(self):
        bus = FakeBus({"/ActiveBatteryService": {"Value": SERVICE},
                       "/Dc/Battery/VoltageService": {"Value": "com.victronenergy.vebus.test"}})
        result = self.read(bus)
        self.assertEqual(result["values"]["/ActiveBatteryService"], {"status": "ok", "value": SERVICE})

    def test_host_summary_reads_only_bounded_passive_files(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            (proc / "uptime").write_text("123.50 12.00")
            (proc / "loadavg").write_text("0.1 0.2 0.3 1/100 30")
            (proc / "meminfo").write_text("MemTotal: 10000 kB\nMemAvailable: 5000 kB\nCached: 50 kB\n")
            (proc / "version-test").write_text("vTEST")
            result = diagnostics.read_host(diagnostics.Budget(2), proc, proc / "version-test")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["uptime_seconds"], 123.5)
        self.assertEqual(result["MemAvailable_kib"], 5000)
        self.assertNotIn("Cached_kib", result)

    def test_discovery_cap_reports_truncation(self):
        bus = FakeBus()
        bus.names = ["com.victronenergy.battery.test%d" % n for n in range(40)]
        result = diagnostics.collect_sample(bus, "session", 0,
            can_reader=lambda budget: {"status": "ok", "interfaces": []})
        self.assertTrue(result["discovery_success"])
        self.assertTrue(result["discovery_truncated"])
        self.assertEqual(len(result["devices"]), diagnostics.MAX_SERVICES)

    def test_bluez_is_read_only_and_missing_properties_unknown(self):
        bus = FakeBus()
        bus.bluez_objects = {"/org/bluez/hci0": {"org.bluez.Adapter1": {"Powered": True}},
            "/org/bluez/hci0/dev_test": {"org.bluez.Device1": {"Connected": False,
                "Name": "JK", "RSSI": -75, "Adapter": "/org/bluez/hci0"}}}
        result = diagnostics.read_bluetooth(bus, ["org.bluez"], True, diagnostics.Budget(5))
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["devices"][0]["connected"])
        self.assertIsNone(result["devices"][0]["services_resolved"])
        self.assertEqual([c[3] for c in bus.calls],
                         ["GetNameOwner", "GetManagedObjects", "GetNameOwner"])

    def test_bluez_absent_is_not_activated(self):
        bus = FakeBus()
        result = diagnostics.read_bluetooth(bus, [], True, diagnostics.Budget(5))
        self.assertEqual(result["status"], "not_present")
        self.assertEqual(bus.calls, [])

    def test_can_uses_passive_sysfs_and_fixed_ip_arguments(self):
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            self.assertGreater(kwargs["timeout"], 0)
            self.assertNotIn("shell", kwargs)
            return subprocess.CompletedProcess(command, 0, "can state ERROR-ACTIVE", "")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, link_type in (("can0", "280"), ("eth0", "1")):
                (root / name / "statistics").mkdir(parents=True)
                (root / name / "type").write_text(link_type)
                (root / name / "operstate").write_text("up")
                for stat in diagnostics.CAN_STATS:
                    (root / name / "statistics" / stat).write_text("7")
            with patch.object(diagnostics.shutil, "which", return_value="/sbin/ip"):
                result = diagnostics.read_can(diagnostics.Budget(5), root, runner)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["interfaces"]), 1)
        self.assertEqual(result["interfaces"][0]["stats"]["rx_errors"], 7)
        self.assertEqual(calls, [["/sbin/ip", "-details", "-statistics", "link", "show", "dev", "can0"]])

    def test_can_detail_parser_maps_controller_history_in_header_order(self):
        detail = """2: vecan1: <NOARP,UP> mtu 16 state UNKNOWN
    link/can
    can state ERROR-PASSIVE (berr-counter tx 0 rx 0) restart-ms 100
      bitrate 500000 sample-point 0.875
      re-started bus-errors arbit-lost error-warn error-pass bus-off
      19 0 0 52 67 19
"""
        result = diagnostics.parse_can_detail(detail)
        self.assertEqual(result["state"], "ERROR-PASSIVE")
        self.assertEqual(result["berr_counter"], {"tx": 0, "rx": 0})
        self.assertEqual(result["restart_ms"], 100)
        self.assertEqual(result["bitrate"], 500000)
        self.assertEqual(result["counters"], {
            "restarted": 19, "bus_errors": 0, "arbitration_lost": 0,
            "error_warning": 52, "error_passive": 67, "bus_off": 19})

    def test_can_filter_is_compact_and_missing_target_is_unknown(self):
        detail = ("can state ERROR-ACTIVE (berr-counter tx 0 rx 0) restart-ms 100\n"
                  "re-started bus-errors arbit-lost error-warn error-pass bus-off\n"
                  "1 2 3 4 5 6\n")
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, detail, "")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("vecan0", "vecan1"):
                (root / name / "statistics").mkdir(parents=True)
                (root / name / "type").write_text("280")
                (root / name / "operstate").write_text("up")
                for stat in diagnostics.CAN_STATS:
                    (root / name / "statistics" / stat).write_text("7")
            with patch.object(diagnostics.shutil, "which", return_value="/sbin/ip"):
                result = diagnostics.read_can(diagnostics.Budget(5), root, runner,
                    selected_interface="vecan1", include_detail=False)
                missing = diagnostics.read_can(diagnostics.Budget(5), root, runner,
                    selected_interface="can9", include_detail=False)
        self.assertTrue(result["selected_interface_found"])
        self.assertEqual([item["name"] for item in result["interfaces"]], ["vecan1"])
        self.assertNotIn("detail", result["interfaces"][0])
        self.assertEqual(result["interfaces"][0]["controller"]["state"], "ERROR-ACTIVE")
        self.assertEqual(len(calls), 1)
        self.assertEqual(missing["status"], "unknown")
        self.assertEqual(missing["error"], "selected_interface_not_found_or_not_can")

    def test_can_deltas_report_growth_state_change_and_counter_reset(self):
        previous = {"interfaces": [{"name": "vecan1",
            "stats": {"rx_packets": 100, "tx_dropped": 70},
            "controller": {"state": "ERROR-ACTIVE",
                           "counters": {"bus_off": 19, "error_passive": 67}}}]}
        current = {"interfaces": [{"name": "vecan1",
            "stats": {"rx_packets": 130, "tx_dropped": 2},
            "controller": {"state": "ERROR-PASSIVE",
                           "counters": {"bus_off": 20, "error_passive": 70}}}]}
        diagnostics.add_can_deltas(current, previous)
        delta = current["interfaces"][0]["delta"]
        self.assertEqual(delta["stats"]["rx_packets"], 30)
        self.assertEqual(delta["controller_counters"], {"bus_off": 1, "error_passive": 3})
        self.assertEqual(delta["state_change"], {
            "previous": "ERROR-ACTIVE", "current": "ERROR-PASSIVE"})
        self.assertEqual(delta["status"], "counter_reset")
        self.assertEqual(delta["reset_detected"], ["stats.tx_dropped"])

    def test_can_only_collection_skips_dbus_and_raw_ip_text(self):
        calls = []
        def can_reader(budget, selected_interface, include_detail):
            calls.append((selected_interface, include_detail))
            return {"status": "ok", "interfaces": [{"name": selected_interface,
                "stats": {}, "controller": {"state": "ERROR-ACTIVE", "counters": {}}}]}
        result = diagnostics.collect_can_sample("session", 0, "vecan1",
            can_reader=can_reader, host_reader=lambda budget: {"status": "ok"})
        self.assertEqual(calls, [("vecan1", False)])
        self.assertEqual(result["scope"], "can")
        self.assertFalse(result["discovery_success"])
        self.assertEqual(result["devices"], [])
        self.assertEqual(result["bluetooth"]["status"], "not_collected")
        self.assertEqual(result["can"]["interfaces"][0]["delta"]["status"], "baseline")

    def test_can_only_cli_does_not_import_or_open_dbus(self):
        records = []
        def collector(session_id, started, selected_interface, previous_can=None):
            record = {"can": {"status": "ok", "interfaces": []},
                      "selected": selected_interface, "previous": previous_can}
            records.append(record)
            return record
        with patch.object(diagnostics, "collect_can_sample", side_effect=collector), \
             patch("sys.stdout", new_callable=io.StringIO) as output, \
             patch.dict(sys.modules, {"dbus": None}):
            code = diagnostics.main(["--scope", "can", "--interface", "vecan1",
                                     "--samples", "1"])
        self.assertEqual(code, 0)
        self.assertEqual(records[0]["selected"], "vecan1")
        self.assertEqual(json.loads(output.getvalue())["selected"], "vecan1")

    def test_optional_logs_are_bounded_and_command_failure_explicit(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, "x" * 20000, "")
        result = diagnostics.run_read_command(["dmesg"], diagnostics.Budget(3), 1024, runner)
        self.assertEqual(len(result["text"]), 1024)
        self.assertTrue(result["truncated"])

    def test_cli_help_and_invalid_bounds_work_without_dbus(self):
        with patch.dict(sys.modules, {"dbus": None}), patch("sys.stdout", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as outcome:
                diagnostics.main(["--help"])
            self.assertEqual(outcome.exception.code, 0)
        for args in (["--samples", "0"], ["--samples", "121"], ["--interval", "1"], ["--interval", "61"]):
            with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit) as outcome:
                diagnostics.main(args)
            self.assertEqual(outcome.exception.code, 2)
        for args in (["--scope", "can"],
                     ["--interface", "vecan1"],
                     ["--scope", "can", "--interface", "../../bad"],
                     ["--scope", "can", "--interface", "vecan1", "--logs"]):
            with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit) as outcome:
                diagnostics.main(args)
            self.assertEqual(outcome.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
