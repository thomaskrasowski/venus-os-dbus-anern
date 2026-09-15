#!/usr/bin/env python3
"""Owner-run, finite passive Cerbo diagnostics; JSONL on stdout, no target writes.

Run locally on the Cerbo only when the owner chooses to run it. This tool never
opens serial/CAN/BLE transports, publishes D-Bus objects, starts services, or
changes settings. D-Bus reads can still add load. Captures contain private names,
connections, Bluetooth object paths, and (with --logs) kernel messages.
"""

import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
from itertools import islice
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid


BUS_NAME = "org.freedesktop.DBus"
BUS_PATH = "/org/freedesktop/DBus"
BUS_ITEM = "com.victronenergy.BusItem"
SERVICE_PREFIXES = tuple("com.victronenergy." + name + "." for name in
                         ("battery", "inverter", "solarcharger", "grid", "vebus",
                          "multi", "acsystem"))
MAX_SERVICES = 32
MAX_INTERFACES = 16
SAMPLE_BUDGET = 15.0
CALL_TIMEOUT = 0.75
TEXT_PATHS = {"/ProductName", "/CustomName", "/Mgmt/Connection",
              "/Dc/Battery/BatteryService", "/Dc/Battery/VoltageService",
              "/ActiveBatteryService", "/AutoSelectedBatteryService"}
# Critical fields come first in a budget-limited legacy GetValue fallback.
PATHS = tuple(dict.fromkeys([
    "/Connected", "/Soc", "/Dc/0/Voltage", "/Dc/0/Current", "/Dc/0/Power",
    "/Dc/0/Temperature", "/Temperature", "/Ac/Out/L1/Power",
    "/UpdateIndex", "/ProductName", "/CustomName",
    "/DeviceInstance", "/Mgmt/Connection", "/State", "/ErrorCode",
    "/Info/MaxChargeVoltage", "/Info/MaxChargeCurrent", "/Info/MaxDischargeCurrent",
    "/Info/BatteryLowVoltage", "/Io/AllowToCharge", "/Io/AllowToDischarge",
    "/Alarms/LowVoltage", "/Alarms/HighVoltage", "/Alarms/LowSoc",
    "/Alarms/HighChargeCurrent", "/Alarms/HighDischargeCurrent",
    "/Alarms/LowTemperature", "/Alarms/HighTemperature", "/Alarms/BmsCable",
    "/System/MinCellVoltage", "/System/MaxCellVoltage",
    "/System/MinCellTemperature", "/System/MaxCellTemperature",
    "/System/NrOfModulesOnline", "/System/NrOfModulesOffline",
    "/Pv/0/Voltage", "/Pv/0/Current", "/Pv/0/Power", "/Yield/Power",
    "/Yield/User", "/Yield/System", "/Yield/Today", "/Yield/Yesterday",
    "/Ac/ActiveIn/ActiveInput", "/Ac/ActiveIn/Source",
    "/Dc/Battery/Soc", "/Dc/Battery/Voltage", "/Dc/Battery/Current",
    "/Dc/Battery/Power", "/Dc/Battery/BatteryService",
    "/Dc/Battery/VoltageService", "/ActiveBatteryService", "/AutoSelectedBatteryService",
    "/Dc/Pv/Power", "/Dc/System/Power",
] + [prefix + "/L" + str(phase) + "/" + field
     for prefix in ("/Ac/In", "/Ac/In/1", "/Ac/Out", "/Ac/ActiveIn")
     for phase in (1, 2, 3) for field in ("V", "I", "P", "F")]
  + [prefix + "/L" + str(phase) + "/" + field
     for prefix in ("/Ac", "/Ac/Grid", "/Ac/Consumption", "/Ac/PvOnGrid",
                    "/Ac/PvOnOutput")
     for phase in (1, 2, 3) for field in ("Voltage", "Current", "Power")]))
CAN_STATS = ("rx_packets", "tx_packets", "rx_bytes", "tx_bytes", "rx_errors",
             "tx_errors", "rx_dropped", "tx_dropped", "rx_over_errors")
MISSING_ERRORS = {"org.freedesktop.DBus.Error.UnknownObject",
                  "org.freedesktop.DBus.Error.UnknownMethod",
                  "org.freedesktop.DBus.Error.UnknownInterface"}


class BudgetExceeded(TimeoutError):
    pass


class Budget:
    def __init__(self, seconds, clock=time.monotonic):
        self.clock = clock
        self.end = clock() + seconds

    def timeout(self, maximum=CALL_TIMEOUT):
        remaining = self.end - self.clock()
        if remaining <= 0:
            raise BudgetExceeded("collection budget exhausted")
        return min(maximum, remaining)

    def child(self, seconds):
        child = Budget(seconds, self.clock)
        child.end = min(child.end, self.end)
        return child


def error_name(exc):
    """Keep failures concise; arbitrary remote error text is not needed."""
    getter = getattr(exc, "get_dbus_name", None)
    return str(getter())[:160] if getter else type(exc).__name__


def field(status, value=None, error=None):
    result = {"status": status, "value": value}
    if error:
        result["error"] = error
    return result


def normalize(path, value):
    if value is None or isinstance(value, (list, tuple, Mapping, bytes, bytearray)):
        return field("invalid", error="null_or_non_scalar")
    if path in TEXT_PATHS:
        if not isinstance(value, str):
            return field("invalid", error="non_text_metadata")
        return field("ok", str(value)[:256])
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return field("invalid", error="non_numeric_telemetry")
    if not math.isfinite(value):
        return field("invalid", error="non_finite_telemetry")
    if path in ("/Soc", "/Dc/Battery/Soc") and not 0 <= value <= 100:
        return field("invalid", error="soc_out_of_range")
    # Convert dbus-python scalar subclasses to plain Python primitives.
    return field("ok", float(value) if isinstance(value, float) else int(value))


def call(bus, destination, path, interface, member, signature, args, budget):
    # All telemetry destinations are unique owners, never activatable names.
    # call_blocking avoids proxy construction/introspection/name activation.
    return bus.call_blocking(destination, path, interface, member, signature,
                             args, timeout=budget.timeout())


def owner_of(bus, service, budget):
    owner = str(call(bus, BUS_NAME, BUS_PATH, BUS_NAME, "GetNameOwner", "s",
                     (service,), budget))
    if not owner.startswith(":"):
        raise ValueError("invalid unique D-Bus owner")
    return owner


def get_value(bus, owner, path, budget):
    try:
        return normalize(path, call(bus, owner, path, BUS_ITEM, "GetValue", "",
                                    (), budget))
    except Exception as exc:
        name = error_name(exc)
        return field("missing" if name in MISSING_ERRORS else "error", error=name)


def read_device(bus, service, budget):
    device = {"service": service, "owner": None, "owner_consistent": False,
              "owner_check_status": "error",
              "snapshot_consistent": None, "read_method": "none", "values": {}}
    try:
        owner = device["owner"] = owner_of(bus, service, budget)
    except Exception as exc:
        device["error"] = error_name(exc)
        device["values"] = {p: field("error", error=error_name(exc)) for p in PATHS}
        return device
    # Leave time to verify that the service still has the same owner after reads.
    reads = budget.child(max(0, budget.end - budget.clock() - 0.2))
    try:
        items = call(bus, owner, "/", BUS_ITEM, "GetItems", "", (), reads)
        if not isinstance(items, Mapping):
            raise ValueError("malformed GetItems response")
        device["read_method"] = "GetItems"
        for path in PATHS:
            item = items.get(path)
            if path not in items:
                result = field("missing")
            elif not isinstance(item, Mapping) or "Value" not in item:
                result = field("error", error="malformed_GetItems_entry")
            else:
                result = normalize(path, item["Value"])
            device["values"][path] = result
        # One service response, not a guarantee of fresh or simultaneous hardware data.
        device["snapshot_consistent"] = True
    except Exception as exc:
        name = error_name(exc)
        if name in MISSING_ERRORS:
            device["read_method"] = "GetValue"
            before = {p: get_value(bus, owner, p, reads)
                      for p in ("/UpdateIndex", "/Connected")}
            device["values"] = {p: get_value(bus, owner, p, reads) for p in PATHS}
            after = {p: get_value(bus, owner, p, reads) for p in before}
            comparable = [p for p in before if before[p]["status"] == "ok"
                          and after[p]["status"] == "ok"]
            if any(before[p]["value"] != after[p]["value"] for p in comparable):
                device["snapshot_consistent"] = False
            elif len(comparable) == len(before):
                device["snapshot_consistent"] = True
            device["values"].update(after)
        else:
            # A timeout is not evidence that a telemetry path is unsupported.
            device["values"] = {p: field("error", error=name) for p in PATHS}
    try:
        device["owner_consistent"] = owner == owner_of(bus, service, budget)
        device["owner_check_status"] = "ok" if device["owner_consistent"] else "changed"
    except Exception as exc:
        device["error"] = error_name(exc)
        device["snapshot_consistent"] = None
    if device["owner_check_status"] == "changed":
        device["snapshot_consistent"] = False
    return device


def read_small(path, limit=256):
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        return stream.read(limit).strip()


def read_host(budget, proc=Path("/proc"), version=Path("/opt/victronenergy/version")):
    """A small passive host snapshot; no process arguments or configuration dumps."""
    result = {"status": "ok", "errors": []}
    for name in ("uptime", "loadavg", "meminfo"):
        try:
            budget.timeout()
            text = read_small(proc / name, 2048)
            if name == "uptime":
                result["uptime_seconds"] = float(text.split()[0])
            elif name == "loadavg":
                result["load_average"] = [float(n) for n in text.split()[:3]]
            else:
                for line in text.splitlines():
                    parts = line.split()
                    if parts[0] in ("MemTotal:", "MemAvailable:", "MemFree:", "SwapFree:"):
                        result[parts[0].rstrip(":") + "_kib"] = int(parts[1])
        except (OSError, ValueError, IndexError, BudgetExceeded) as exc:
            result["errors"].append(name + ": " + error_name(exc))
    try:
        budget.timeout()
        result["venus_version"] = read_small(version, 128)
    except (OSError, BudgetExceeded) as exc:
        result["errors"].append("venus_version: " + error_name(exc))
    if result["errors"]:
        result["status"] = "partial"
    return result


def run_read_command(command, budget, limit=8192, runner=subprocess.run):
    """Fixed finite commands only; no shell, follow mode, or modifying flags."""
    result = runner(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8", errors="replace", check=False,
                    timeout=budget.timeout())
    if result.returncode:
        return {"status": "error", "error": "command_exit_" + str(result.returncode)}
    return {"status": "ok", "text": result.stdout[-limit:],
            "truncated": len(result.stdout) > limit}


def read_can(budget, sysfs=Path("/sys/class/net"), runner=subprocess.run):
    result = {"status": "ok", "interfaces": [], "truncated": False}
    try:
        candidates = list(islice(sysfs.iterdir(), 257))
        result["truncated"] = len(candidates) > 256
        ip = shutil.which("ip")
        for path in candidates[:256]:
            budget.timeout()
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,15}", path.name):
                continue
            try:
                if read_small(path / "type") != "280":
                    continue
                if len(result["interfaces"]) >= MAX_INTERFACES:
                    result["truncated"] = True
                    break
                interface = {"name": path.name, "stats": {}, "errors": []}
                result["interfaces"].append(interface)
                for name in CAN_STATS:
                    budget.timeout()
                    try:
                        value = int(read_small(path / "statistics" / name, 64))
                        if value < 0:
                            raise ValueError("negative counter")
                        interface["stats"][name] = value
                    except (OSError, ValueError) as exc:
                        interface["errors"].append(name + ": " + error_name(exc))
                interface["operstate"] = read_small(path / "operstate", 32)
                if ip:
                    try:
                        detail = run_read_command([ip, "-details", "-statistics", "link",
                                                   "show", "dev", path.name], budget,
                                                  runner=runner)
                        if detail["status"] == "ok":
                            interface["detail"] = detail["text"]
                            interface["detail_truncated"] = detail["truncated"]
                        else:
                            interface["errors"].append(detail["error"])
                    except (OSError, subprocess.SubprocessError, BudgetExceeded) as exc:
                        interface["errors"].append("ip: " + error_name(exc))
                else:
                    interface["errors"].append("ip_unavailable")
                if interface["errors"]:
                    result["status"] = "partial"
            except OSError as exc:
                result["status"] = "partial"
                result.setdefault("errors", []).append(path.name + ": " + error_name(exc))
    except Exception as exc:
        result["status"] = "error"
        result["error"] = error_name(exc)
    return result


def read_bluetooth(bus, names, discovery_success, budget):
    result = {"status": "unknown", "adapters": [], "devices": [], "truncated": False}
    if not discovery_success:
        result["error"] = "D-Bus discovery failed"
        return result
    if "org.bluez" not in names:
        result["status"] = "not_present"
        return result
    try:
        owner = owner_of(bus, "org.bluez", budget)
        objects = call(bus, owner, "/", "org.freedesktop.DBus.ObjectManager",
                       "GetManagedObjects", "", (), budget)
        if not isinstance(objects, Mapping):
            raise ValueError("malformed BlueZ response")
        result["truncated"] = len(objects) > 256
        for path, interfaces in islice(objects.items(), 256):
            if not isinstance(interfaces, Mapping):
                raise ValueError("malformed BlueZ interface map")
            adapter = interfaces.get("org.bluez.Adapter1")
            if isinstance(adapter, Mapping):
                result["adapters"].append({"path": str(path)[:256],
                    "powered": bool(adapter["Powered"]) if "Powered" in adapter else None})
            dev = interfaces.get("org.bluez.Device1")
            if isinstance(dev, Mapping):
                rssi = dev.get("RSSI")
                result["devices"].append({"path": str(path)[:256],
                    "name": str(dev.get("Name", dev.get("Alias", "")))[:256],
                    "adapter": str(dev.get("Adapter", ""))[:256],
                    "connected": bool(dev["Connected"]) if "Connected" in dev else None,
                    "services_resolved": bool(dev["ServicesResolved"])
                        if "ServicesResolved" in dev else None,
                    "rssi": int(rssi) if isinstance(rssi, int) else None})
        result["owner"] = owner
        result["owner_consistent"] = owner == owner_of(bus, "org.bluez", budget)
        result["status"] = "ok" if result["owner_consistent"] else "error"
        if not result["owner_consistent"]:
            result["error"] = "BlueZ owner changed during read"
    except Exception as exc:
        result["status"] = "error"
        result["error"] = error_name(exc)
    return result


def collect_sample(bus, session_id, started, clock=time.monotonic, can_reader=read_can,
                   include_logs=False, runner=subprocess.run, host_reader=read_host):
    sample_started = clock()
    budget = Budget(SAMPLE_BUDGET, clock)
    record = {"schema_version": 1, "type": "sample", "source": "cerbo",
              "session_id": session_id,
              "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
              "elapsed_seconds": round(sample_started - started, 6),
              "discovery_success": False, "discovery_truncated": False,
              "devices": [], "errors": []}
    names = []
    names_truncated = False
    try:
        raw_names = call(bus, BUS_NAME, BUS_PATH, BUS_NAME, "ListNames", "", (), budget)
        if not isinstance(raw_names, (list, tuple)) or any(not isinstance(n, str) for n in raw_names):
            raise ValueError("malformed ListNames reply")
        names_truncated = len(raw_names) > 4096
        names = [str(n) for n in raw_names[:4096]]
        record["discovery_success"] = True
        services = [n for n in names if n.startswith(SERVICE_PREFIXES)
                    or n == "com.victronenergy.system"]
        services.sort(key=lambda n: (not n.startswith("com.victronenergy.battery."), n))
        record["discovery_truncated"] = names_truncated or len(services) > MAX_SERVICES
        # Reserve budget for CAN and BlueZ even if a legacy service is slow.
        dbus_budget = budget.child(10)
        for service in services[:MAX_SERVICES]:
            record["devices"].append(read_device(bus, service, dbus_budget.child(1.5)))
    except Exception as exc:
        record["errors"].append("discovery: " + error_name(exc))
    record["can"] = can_reader(budget.child(2))
    record["bluetooth"] = read_bluetooth(bus, names,
        record["discovery_success"] and not names_truncated, budget.child(2))
    record["host"] = host_reader(budget.child(0.25))
    if include_logs:
        command = shutil.which("dmesg")
        if not command:
            record["logs"] = {"status": "unavailable", "error": "dmesg_unavailable"}
        else:
            try:
                record["logs"] = run_read_command([command], budget, limit=16384, runner=runner)
                record["logs"]["clock"] = "raw kernel clock; not aligned to captured_at"
            except (OSError, subprocess.SubprocessError, BudgetExceeded) as exc:
                record["logs"] = {"status": "error", "error": error_name(exc)}
    record["collection_duration_seconds"] = round(clock() - sample_started, 6)
    return record


def bounded_int(low, high):
    def parse(value):
        try:
            number = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("expected an integer") from exc
        if not low <= number <= high:
            raise argparse.ArgumentTypeError("must be between %d and %d" % (low, high))
        return number
    return parse


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--samples", type=bounded_int(1, 120), default=1,
                        help="finite sample count, 1..120 (default: 1)")
    parser.add_argument("--interval", type=bounded_int(2, 60), default=5,
                        help="seconds between sample starts, 2..60; no catch-up bursts (default: 5)")
    parser.add_argument("--logs", action="store_true",
                        help="include at most 16 KiB of private kernel log text in the first sample")
    args = parser.parse_args(argv)
    try:
        import dbus  # Venus dependency; --help and imports/tests work offline.
        # Force a local Unix system bus; never honor a remote D-Bus address.
        socket_path = "/run/dbus/system_bus_socket"
        if not Path(socket_path).exists():
            socket_path = "/var/run/dbus/system_bus_socket"
        bus = dbus.bus.BusConnection("unix:path=" + socket_path)
    except Exception as exc:
        print(json.dumps({"schema_version": 1, "type": "error", "source": "cerbo",
                          "error": "local_system_bus_unavailable", "detail": error_name(exc)}))
        return 1
    started = time.monotonic()
    session_id = str(uuid.uuid4())
    try:
        for index in range(args.samples):
            tick = time.monotonic()
            record = collect_sample(bus, session_id, started,
                                    include_logs=args.logs and index == 0)
            print(json.dumps(record, allow_nan=False, separators=(",", ":")), flush=True)
            if index + 1 < args.samples:
                time.sleep(max(0, args.interval - (time.monotonic() - tick)))
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        return 1
    finally:
        bus.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
