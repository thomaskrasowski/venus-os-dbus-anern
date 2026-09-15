"""Offline fixed-scope snapshot tests; no Cerbo or live D-Bus access."""

import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("cerbo_config_snapshot",
    Path(__file__).parents[1] / "tools" / "cerbo_config_snapshot.py")
snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snapshot)


class DBusError(Exception):
    def __init__(self, name):
        self.name = "org.freedesktop.DBus.Error." + name

    def get_dbus_name(self):
        return self.name


class FakeBus:
    def __init__(self, names=None):
        self.names = names if names is not None else ["com.victronenergy.system",
            "com.victronenergy.settings", "com.victronenergy.battery.test"]
        self.calls = []
        self.discovery_error = None
        self.owner_error = None
        self.owners = [":1.42"]

    def call_blocking(self, name, path, interface, member, signature, args, timeout):
        self.calls.append((name, path, interface, member, args, timeout))
        if member == "ListNames":
            if self.discovery_error:
                raise self.discovery_error
            return self.names
        if member == "GetNameOwner":
            if self.owner_error:
                raise self.owner_error
            return self.owners.pop(0) if len(self.owners) > 1 else self.owners[0]
        if member == "GetValue":
            return 0
        raise AssertionError("Unapproved method " + member)


class SnapshotTests(unittest.TestCase):
    def make_reader(self, root):
        return snapshot.Reader(snapshot.Budget(), Path(root))

    def write(self, root, path, text):
        target = Path(root) / path.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def test_config_allowlist_never_exports_unknown_keys_or_comments(self):
        text = """[DEFAULT]
BLUETOOTH_BMS = Jkbms_Ble AA:BB:CC:00:00:11
BLUETOOTH_USE_POLLING = True ; owner comment
PASSWORD = top-secret-password
API_TOKEN = secret-token
UNRELATED_HOST = sensitive-router
# another secret comment
CAN_PORT = vecan1
MAX_BATTERY_CHARGE_CURRENT = 100
"""
        result = snapshot.parse_config(text)
        self.assertEqual({r["key"] for r in result}, {"BLUETOOTH_BMS", "BLUETOOTH_USE_POLLING", "CAN_PORT", "MAX_BATTERY_CHARGE_CURRENT"})
        rendered = json.dumps(result)
        for secret in ("top-secret-password", "secret-token", "sensitive-router", "owner comment", "another secret"):
            self.assertNotIn(secret, rendered)
        self.assertIn("Jkbms_Ble", rendered)

    def test_config_report_contains_parsed_values_not_whole_file(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "/data/etc/dbus-serialbattery/config.ini", "BLUETOOTH_BMS = Jkbms_Ble AA:00\nPASSWORD = hidden-value\n")
            result = snapshot.config_snapshot(self.make_reader(root), snapshot.Budget())
        self.assertNotIn("hidden-value", json.dumps(result))
        self.assertNotIn("text", result["files"][0])
        self.assertEqual(result["files"][0]["settings"][0]["key"], "BLUETOOTH_BMS")

    def test_reader_bounds_tail_and_redacts_sensitive_lines(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "/log", "x" * 10000 + "\nfinal-line")
            result = self.make_reader(root).read("/log", 100, tail=True)
            self.assertTrue(result["truncated"])
            self.assertLessEqual(result["retained_bytes"], 100)
            self.assertTrue(result["text"].endswith("final-line"))
            self.write(root, "/run", "exec driver Jkbms_Ble\nexport API_TOKEN=hidden-value\n")
            result = self.make_reader(root).read("/run")
            self.assertIn("exec driver Jkbms_Ble", result["text"])
            self.assertNotIn("hidden-value", result["text"])

    def test_reader_rejects_non_regular_file_and_expired_budget(self):
        with tempfile.TemporaryDirectory() as root:
            reader = self.make_reader(root)
            result = reader.read("/")
            self.assertEqual(result["status"], "unknown")
            reader.budget.end = -1
            result = reader.read("/anywhere")
            self.assertEqual(result["error"], "TimeoutError")

    def test_total_file_byte_limit_is_not_exceeded(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "/large", "x" * 1000)
            reader = self.make_reader(root)
            reader.bytes = snapshot.MAX_FILE_BYTES - 10
            result = reader.read("/large", 100)
            self.assertEqual(reader.bytes, snapshot.MAX_FILE_BYTES)
            self.assertEqual(result["retained_bytes"], 10)
            self.assertTrue(result["truncated"])
            self.assertEqual(reader.read("/large")["error"], "TimeoutError")

    def test_subprocess_large_output_keeps_bounded_tail(self):
        result = snapshot.command([sys.executable, "-c", "import sys;sys.stdout.write('x'*200000+'TAIL')"], snapshot.Budget(3), limit=100)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["retained_bytes"], 100)
        self.assertTrue(result["truncated"])
        self.assertTrue(result["text"].endswith("TAIL"))

    def test_subprocess_timeout_kills_only_created_process(self):
        began = time.monotonic()
        result = snapshot.command([sys.executable, "-c", "import time;time.sleep(30)"], snapshot.Budget(0.15), limit=100)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "command_timeout")
        self.assertLess(time.monotonic() - began, 3)

    def test_subprocess_interrupt_cleans_up_owned_child(self):
        class Process:
            stdout = io.BytesIO(b"")
            returncode = None
            killed = False
            def wait(self, timeout):
                if not self.killed:
                    raise KeyboardInterrupt()
                return self.returncode
            def kill(self):
                self.killed = True
                self.returncode = -9
            def poll(self):
                return self.returncode
        proc = Process()
        with self.assertRaises(KeyboardInterrupt):
            snapshot.command(["owned-worker"], snapshot.Budget(), popen=lambda *a, **kw: proc)
        self.assertTrue(proc.killed)
        self.assertTrue(proc.stdout.closed)

    def test_hung_dbus_worker_returns_unknown_inside_parent_deadline(self):
        def hung_worker(argv, budget, **kwargs):
            return snapshot.command([sys.executable, "-c", "import time;time.sleep(30)"], budget, **kwargs)
        began = time.monotonic()
        result = snapshot.dbus_worker_snapshot(None, snapshot.Budget(0.15), runner=hung_worker)
        self.assertFalse(result["discovery_success"])
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["error"], "command_timeout")
        self.assertLess(time.monotonic() - began, 3)

    def test_dbus_worker_rejects_truncated_and_invalid_json(self):
        for output, truncated, error in (("not-json", False, "dbus_worker_invalid_json"),
                ('{"discovery_success":true,"services":[]}', True, "dbus_worker_output_truncated")):
            with self.subTest(error=error):
                def runner(argv, budget, **kwargs):
                    self.assertFalse(kwargs["sanitize"])
                    self.assertEqual(argv[-1], "--dbus-worker")
                    return {"status": "ok", "text": output, "truncated": truncated}
                result = snapshot.dbus_worker_snapshot(None, snapshot.Budget(), runner)
                self.assertEqual(result["error"], error)
                self.assertFalse(result["discovery_success"])

    def test_valid_worker_json_preserves_names_containing_marker_words(self):
        report = {"discovery_success": True, "services": [{"service": "battery.token_device"}]}
        def runner(argv, budget, **kwargs):
            self.assertFalse(kwargs["sanitize"])
            return {"status": "ok", "text": json.dumps(report), "truncated": False}
        self.assertEqual(snapshot.dbus_worker_snapshot(None, snapshot.Budget(), runner), report)

    def test_missing_command_is_explicit(self):
        with patch.object(snapshot.shutil, "which", return_value=None):
            result = snapshot.executable_command("opkg", ["list-installed"], snapshot.Budget())
        self.assertEqual(result["status"], "unavailable")

    def test_services_are_discovered_without_running_their_scripts(self):
        calls = []
        def runner(argv, budget, limit=0):
            calls.append(argv)
            return {"status": "ok", "text": "up", "truncated": False}
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "/service/dbus-blebattery.0/run", "exec /opt/victronenergy/dbus-serialbattery/dbus-serialbattery.py Jkbms_Ble AA:BB\n")
            self.write(root, "/service/dbus-blebattery.0/log/run", "exec multilog /var/log/dbus-blebattery.0\n")
            self.write(root, "/var/log/dbus-blebattery.0/current", "JK connection example")
            self.write(root, "/service/unrelated-secret-service/run", "secret-payload")
            for name in ("can-bus-bms", "vesmart-server", "dbus-ble-sensors"):
                self.write(root, "/service/" + name + "/run", "exec optional-command")
            with patch.object(snapshot.shutil, "which", return_value="svstat"):
                result = snapshot.service_snapshot(self.make_reader(root), snapshot.Budget(), runner)
        self.assertTrue(result["discovery_success"])
        self.assertEqual({s["name"] for s in result["services"]}, {"dbus-blebattery.0", "can-bus-bms", "vesmart-server", "dbus-ble-sensors"})
        self.assertNotIn("secret-payload", json.dumps(result))
        self.assertTrue(all(c[0] == "svstat" and len(c) == 2 for c in calls))

    def test_missing_service_directory_is_unknown_discovery(self):
        with tempfile.TemporaryDirectory() as root:
            result = snapshot.service_snapshot(self.make_reader(root), snapshot.Budget())
        self.assertFalse(result["discovery_success"])
        self.assertTrue(result["error"])

    def test_can_reads_passive_stats_and_fixed_ip_command(self):
        calls = []
        def runner(argv, budget, limit=0):
            calls.append(argv)
            return {"status": "ok", "text": "can state ERROR-ACTIVE", "truncated": False}
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "/sys/class/net/vecan1/type", "280\n")
            self.write(root, "/sys/class/net/eth0/type", "1\n")
            with patch.object(snapshot.shutil, "which", return_value="ip"):
                result = snapshot.can_snapshot(self.make_reader(root), snapshot.Budget(), runner)
        self.assertEqual([i["name"] for i in result["interfaces"]], ["vecan1"])
        self.assertEqual(calls, [["ip", "-details", "-statistics", "link", "show", "dev", "vecan1"]])

    def test_package_and_process_filters_include_known_components(self):
        text = "can-bus-bms - 1\nvesmart-server - 2\nbluetoothd - 3\nunrelated-account - private\n"
        def runner(argv, budget, limit=0):
            return {"status": "ok", "text": text, "truncated": False}
        with patch.object(snapshot.shutil, "which", side_effect=lambda n: n):
            packages = snapshot.packages_snapshot(None, snapshot.Budget(), runner)
            processes = snapshot.process_snapshot(None, snapshot.Budget(), runner)
        self.assertEqual(len(packages["packages"]), 3)
        self.assertEqual(len(processes["processes"]), 3)
        self.assertNotIn("private", json.dumps([packages, processes]))

    def test_kernel_match_keeps_surrounding_context_only(self):
        lines = ["ordinary line %d" % n for n in range(30)]
        lines[15] = "irq 23 nobody cared spi"
        def runner(argv, budget, limit=0):
            return {"status": "ok", "text": "\n".join(lines), "truncated": False}
        with patch.object(snapshot.shutil, "which", return_value="dmesg"):
            result = snapshot.kernel_snapshot(None, snapshot.Budget(), runner)
        self.assertEqual(len(result["context"]), 9)
        self.assertEqual(result["context"][0]["tail_line"], 12)
        self.assertNotIn("ordinary line 0", json.dumps(result))

    def test_dbus_never_bulk_reads_settings_or_activates_services(self):
        bus = FakeBus()
        with tempfile.TemporaryDirectory() as root:
            result = snapshot.dbus_snapshot(self.make_reader(root), snapshot.Budget(10), bus)
        self.assertTrue(result["discovery_success"])
        settings = next(s for s in result["services"] if s["service"] == "com.victronenergy.settings")
        self.assertEqual(set(settings["values"]), set(snapshot.SETTINGS_PATHS))
        self.assertIn("/Settings/SystemSetup/CanBmsSense", settings["values"])
        self.assertTrue(all(c[3] in ("ListNames", "GetNameOwner", "GetValue") for c in bus.calls))
        for name, path, interface, member, args, timeout in bus.calls:
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 0.4)
            if member == "GetValue":
                self.assertTrue(name.startswith(":"))

    def test_dbus_owner_failures_do_not_claim_battery_absence(self):
        bus = FakeBus(["com.victronenergy.battery.test"])
        bus.owner_error = DBusError("NoReply")
        with tempfile.TemporaryDirectory() as root:
            result = snapshot.dbus_snapshot(self.make_reader(root), snapshot.Budget(), bus)
        self.assertTrue(result["discovery_success"])
        self.assertEqual(result["services"][0]["owner_check_status"], "error")
        self.assertIsNone(result["services"][0]["owner"])
        self.assertEqual(result["services"][0]["values"], {})
        self.assertNotIn("GetValue", [c[3] for c in bus.calls])

    def test_dbus_dependency_failure_is_explicit_unknown(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(sys.modules, {"dbus": None}):
            result = snapshot.dbus_snapshot(self.make_reader(root), snapshot.Budget())
        self.assertFalse(result["discovery_success"])
        self.assertIn("error", result)

    def test_owner_changed_is_preserved_and_section_is_incomplete(self):
        bus = FakeBus(["com.victronenergy.system"])
        bus.owners = [":1.42", ":1.43"]
        with tempfile.TemporaryDirectory() as root:
            result = snapshot.dbus_snapshot(self.make_reader(root), snapshot.Budget(), bus)
        self.assertEqual(result["services"][0]["owner_check_status"], "changed")
        self.assertTrue(snapshot.has_incomplete(result))

    def test_limit_flags_make_section_partial(self):
        for flag in ("truncated", "context_truncated", "logs_limit_reached"):
            with self.subTest(flag=flag):
                self.assertTrue(snapshot.has_incomplete({"nested": [{flag: True}]}))
        self.assertFalse(snapshot.has_incomplete({"values": {"/Soc": {"status": "invalid", "value": None}}}))

    def test_section_budget_exhaustion_blocks_file_and_bus_reads(self):
        now = [0.0]
        budget = snapshot.Budget(1, clock=lambda: now[0])
        bus = FakeBus()
        with tempfile.TemporaryDirectory() as root:
            reader = snapshot.Reader(budget, Path(root))
            self.write(root, "/proc/uptime", "100.0 20.0")
            now[0] = 2.0
            file_result = reader.read("/proc/uptime")
            bus_result = snapshot.dbus_snapshot(reader, budget, bus)
        self.assertEqual(file_result["error"], "TimeoutError")
        self.assertEqual(reader.files, 0)
        self.assertFalse(bus_result["discovery_success"])
        self.assertEqual(bus.calls, [])

    def test_full_snapshot_has_section_times_and_partial_status(self):
        with tempfile.TemporaryDirectory() as root, patch.object(snapshot.shutil, "which", return_value=None), \
                patch.object(snapshot, "process_snapshot", return_value={"status": "ok", "truncated": True}):
            result = snapshot.make_snapshot(Path(root), bus=FakeBus([]))
        self.assertEqual(result["type"], "config_snapshot")
        self.assertEqual(result["sections"]["host"]["status"], "partial")
        self.assertEqual(result["sections"]["processes"]["status"], "partial")
        self.assertEqual(result["sections"]["packages"]["status"], "unavailable")
        for section in result["sections"].values():
            self.assertIn("captured_at", section)
            self.assertIn("elapsed_seconds", section)
        self.assertLessEqual(result["file_bytes_read"], snapshot.MAX_FILE_BYTES)
        json.dumps(result, allow_nan=False)

    def test_help_does_not_touch_live_system(self):
        with patch.object(snapshot, "make_snapshot", side_effect=AssertionError("must not run")), patch("sys.stdout", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as outcome:
                snapshot.main(["--help"])
        self.assertEqual(outcome.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
