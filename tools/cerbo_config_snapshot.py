#!/usr/bin/env python3
"""One owner-run read-only Cerbo configuration/diagnostic snapshot to stdout.

Uses a fixed scope and finite budgets. No SSH, serial/CAN/Bluetooth connection,
settings changes, service actions, environment export, or output files. Existing
service scripts/logs and Bluetooth addresses can be private: review before sharing.
The owner may redirect stdout to a file. Missing evidence remains unknown.
"""

import sys
sys.dont_write_bytecode = True

import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
from itertools import islice
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import threading
import time


TOTAL_SECONDS = 30.0
MAX_FILES = 160
MAX_FILE_BYTES = 1024 * 1024
MAX_SERVICES = 16
MAX_CAN = 8
SERVICE_NAMES = ("dbus-blebattery", "dbus-serialbattery", "dbus-canbattery",
                 "dbus-systemcalc-py", "dbus-anern-inverter2", "vecan-dbus",
                 "dbus-cand", "bluetooth", "bluetoothd", "can-bus-bms",
                 "vesmart-server", "dbus-ble-sensors")
CONFIG_DIRS = ("/data/etc/dbus-serialbattery", "/opt/victronenergy/dbus-serialbattery",
               "/data/apps/dbus-serialbattery", "/data/dbus-serialbattery")
CONFIG_KEYS = frozenset((
    "BLUETOOTH_BMS", "BLUETOOTH_USE_POLLING", "BLUETOOTH_FORCE_RESET_BLE_STACK",
    "BLUETOOTH_USE_USB", "CAN_PORT", "BATTERY_TYPE", "BATTERY_ADDRESSES",
    "SERIAL_STARTER_ENABLED", "POLL_INTERVAL", "LOGGING", "BMS_CABLE_ALARM",
    "BLOCK_ON_DISCONNECT", "BLOCK_ON_DISCONNECT_TIMEOUT_MINUTES",
    "BLOCK_ON_DISCONNECT_VOLTAGE_MIN", "BLOCK_ON_DISCONNECT_VOLTAGE_MAX",
    "EXTERNAL_SENSOR_DBUS_DEVICE", "EXTERNAL_SENSOR_DBUS_PATH_CURRENT",
    "EXTERNAL_SENSOR_DBUS_PATH_SOC", "SOC_CALCULATION", "CVCM_ENABLE",
    "CCCM_CV_ENABLE", "DCCM_CV_ENABLE", "CCCM_T_ENABLE", "DCCM_T_ENABLE",
    "CCCM_SOC_ENABLE", "DCCM_SOC_ENABLE", "MAX_BATTERY_CHARGE_CURRENT",
    "MAX_BATTERY_DISCHARGE_CURRENT", "MIN_CELL_VOLTAGE", "MAX_CELL_VOLTAGE",
    "FLOAT_CELL_VOLTAGE", "SOC_RESET_CELL_VOLTAGE", "SOC_RESET_AFTER_DAYS",
    "CHARGE_MODE", "CUSTOM_NAME", "BATTERY_CAPACITY", "CELL_COUNT"))
SYSTEM_PATHS = ("/ActiveBatteryService", "/AutoSelectedBatteryService",
    "/Dc/Battery/BatteryService", "/Dc/Battery/VoltageService", "/Dc/Battery/Soc",
    "/Dc/Battery/Voltage", "/Dc/Battery/Current", "/Dc/Battery/Power",
    "/ActiveBmsService", "/ActiveBmsInstance", "/Control/Dvcc",
    "/Control/BmsParameters", "/Control/SolarChargeVoltage", "/Control/SolarChargeCurrent",
    "/Control/EffectiveChargeVoltage", "/Control/MaxChargeCurrent",
    "/Dc/Battery/ChargeVoltage", "/Dvcc/Alarms/MultipleBatteries",
    "/Dc/Battery/TemperatureService", "/Control/BatteryVoltageSense",
    "/Control/SolarChargerVoltageSense", "/Control/BatteryCurrentSense",
    "/Control/SolarChargerTemperatureSense")
SETTINGS_PATHS = ("/Settings/SystemSetup/BmsInstance", "/Settings/Services/Bol",
    "/Settings/SystemSetup/BatteryService", "/Settings/SystemSetup/MaxChargeCurrent",
    "/Settings/SystemSetup/MaxChargeVoltage", "/Settings/SystemSetup/DvccControlAllMultis",
    "/Settings/SystemSetup/SharedVoltageSense", "/Settings/SystemSetup/SharedTemperatureSense",
    "/Settings/SystemSetup/BatteryCurrentSense", "/Settings/SystemSetup/TemperatureService",
    "/Settings/SystemSetup/CanBmsSense")
DEVICE_PATHS = ("/ProductName", "/CustomName", "/DeviceInstance", "/Mgmt/Connection",
    "/Mgmt/ProcessName", "/FirmwareVersion", "/HardwareVersion", "/Connected", "/Soc", "/Dc/0/Voltage", "/Dc/0/Current",
    "/Info/MaxChargeVoltage", "/Info/MaxChargeCurrent", "/Info/MaxDischargeCurrent",
    "/Io/AllowToCharge", "/Io/AllowToDischarge", "/Alarms/BmsCable")
BUS_NAME = "org.freedesktop.DBus"
BUS_PATH = "/org/freedesktop/DBus"
SECRET_LINE = re.compile(r"(?i)(password|passwd|secret|token|credential|api[_-]?key|authorization|private[_ -]?key)")
RELEVANT = re.compile(r"(?i)(victron|venus|vesmart|vecan|serialbattery|bluez|bluetooth|bleak|bluepy|can[-_]?bus|socketcan|dbus|linux|kernel|python3)")
PROCESS_MATCH = re.compile(r"(?i)(bluetooth|bluez|blebattery|ble-sensors|vesmart|serialbattery|jkbms|can-bus-bms|dbus-canbattery|dbus-cand|vecan-dbus|systemcalc|anern)")
KERNEL_MATCH = re.compile(r"(?i)(irq|interrupt|spi|mcp25|can[0-9]|vecan|bus.off|bluetooth|hci[0-9]|blebattery|serialbattery)")


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def error_name(exc):
    getter = getattr(exc, "get_dbus_name", None)
    return str(getter())[:160] if getter else type(exc).__name__


class Budget:
    def __init__(self, seconds=TOTAL_SECONDS, clock=time.monotonic):
        self.clock = clock
        self.end = clock() + seconds

    def remaining(self, cap=None):
        left = self.end - self.clock()
        if left <= 0:
            raise TimeoutError("snapshot operation budget exhausted")
        return min(left, cap) if cap is not None else left

    def child(self, seconds):
        result = Budget(seconds, self.clock)
        result.end = min(result.end, self.end)
        return result


def redact(text):
    """Best effort for known credential markers; reports still remain private."""
    lines = ["[redacted sensitive line]" if SECRET_LINE.search(line) else line
             for line in text.splitlines()]
    return re.sub(r"(https?://)[^\s/@:]+:[^\s/@]+@", r"\1[redacted]@", "\n".join(lines))


class Reader:
    def __init__(self, budget, root=Path("/")):
        self.budget = budget
        self.root = Path(root)
        self.files = 0
        self.bytes = 0

    def path(self, absolute):
        return self.root / absolute.lstrip("/")

    def read(self, absolute, limit=8192, tail=False, sanitize=True):
        result = {"path": absolute, "status": "unknown"}
        try:
            self.budget.remaining()
            if self.files >= MAX_FILES or self.bytes >= MAX_FILE_BYTES:
                raise TimeoutError("file read limit reached")
            self.files += 1
            path = self.path(absolute)
            result["resolved_path"] = str(path.resolve())
            # Reject device nodes/FIFOs instead of risking transport access or a blocking read.
            info = path.stat()
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("only regular/proc/sysfs files may be read")
            remaining = MAX_FILE_BYTES - self.bytes
            limit = min(limit, remaining)
            read_size = min(limit + 1, remaining)
            skipped = False
            with path.open("rb") as stream:
                if tail and info.st_size > limit:
                    skipped = stream.seek(-limit, os.SEEK_END) > 0
                raw = stream.read(read_size)
            self.bytes += len(raw)
            # sysfs commonly advertises a page-sized st_size for tiny values.
            # Head truncation depends on an actual extra byte, not that metadata.
            boundary = read_size <= limit and len(raw) == read_size
            result["truncated"] = skipped or len(raw) > limit or boundary
            if boundary:
                # The global cap prevented the extra-byte EOF check. Preserve
                # uncertainty even if the file might end exactly at this point.
                result["byte_budget_boundary_reached"] = True
            raw = raw[-limit:] if tail else raw[:limit]
            text = raw.decode("utf-8", "replace")
            result.update(status="ok", text=redact(text) if sanitize else text,
                          retained_bytes=len(raw), tail=tail)
        except FileNotFoundError:
            result.update(status="missing", error="FileNotFoundError")
        except Exception as exc:
            result["error"] = error_name(exc)
        return result


def command(argv, budget, limit=16384, popen=subprocess.Popen, timeout_cap=2, sanitize=True):
    """Drain only our finite subprocess, retaining a bounded output tail in memory."""
    result = {"command": argv, "status": "unknown", "truncated": False}
    proc = None
    thread = None
    retained = bytearray()
    total = [0]
    drain_error = []
    lock = threading.Lock()
    try:
        timeout = budget.remaining(timeout_cap)
        proc = popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, shell=False, close_fds=True)
        def drain():
            try:
                while True:
                    block = proc.stdout.read(4096)
                    if not block:
                        break
                    with lock:
                        total[0] += len(block)
                        retained.extend(block)
                        if len(retained) > limit:
                            del retained[:-limit]
            except (OSError, ValueError) as exc:
                drain_error.append(error_name(exc))
        thread = threading.Thread(target=drain, daemon=True)
        thread.start()
        try:
            proc.wait(timeout=timeout)
            result["status"] = "ok" if proc.returncode == 0 else "error"
        except subprocess.TimeoutExpired:
            # Never signal services or processes we did not create.
            proc.kill()
            proc.wait(timeout=0.25)
            result.update(status="error", error="command_timeout")
        thread.join(timeout=0.25)
        if thread.is_alive():
            result.update(status="error", error="output_drain_incomplete")
        else:
            proc.stdout.close()
        with lock:
            text = bytes(retained).decode("utf-8", "replace")
            result.update(text=redact(text) if sanitize else text,
                          truncated=total[0] > limit, output_bytes=total[0],
                          retained_bytes=len(retained), returncode=proc.returncode)
        if drain_error:
            result.update(status="error", error=drain_error[0])
    except BaseException as exc:
        result["error"] = error_name(exc)
        if proc is not None and proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                pass
        if thread is not None:
            thread.join(timeout=0.25)
            if not thread.is_alive():
                proc.stdout.close()
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
    return result


def executable_command(name, args, budget, limit=16384, runner=command):
    executable = shutil.which(name)
    if not executable:
        return {"status": "unavailable", "error": name + "_unavailable"}
    return runner([executable] + list(args), budget, limit=limit)


def host_snapshot(reader, budget):
    files = ("/proc/uptime", "/proc/version", "/proc/loadavg", "/proc/meminfo",
             "/proc/interrupts", "/proc/pressure/cpu", "/proc/pressure/memory",
             "/proc/pressure/io", "/opt/victronenergy/version")
    return {"files": [reader.read(path, 32768 if path == "/proc/interrupts" else 8192)
                      for path in files]}


def service_match(name):
    return any(name == prefix or name.startswith(prefix + ".") or name.startswith(prefix + "-")
               for prefix in SERVICE_NAMES)


def service_snapshot(reader, budget, runner=command):
    result = {"discovery_success": False, "services": [], "truncated": False}
    try:
        budget.remaining()
        entries = list(islice(reader.path("/service").iterdir(), 257))
        matches = sorted(p.name for p in entries[:256] if service_match(p.name))
        result.update(discovery_success=True, truncated=len(entries) > 256 or len(matches) > MAX_SERVICES)
    except Exception as exc:
        result["error"] = error_name(exc)
        return result
    log_paths = set()
    for name in matches[:MAX_SERVICES]:
        path = "/service/" + name
        entry = {"name": name, "path": path, "resolved_path": str(reader.path(path).resolve()),
                 "run": reader.read(path + "/run"), "log_run": reader.read(path + "/log/run")}
        entry["supervisor"] = executable_command("svstat", [str(reader.path(path))], budget,
                                                  limit=2048, runner=runner)
        # Only known log roots and relevant service directory names; never follow arbitrary
        # shell instructions or execute any discovered run script.
        candidates = ["/var/log/" + name + "/current", "/data/log/" + name + "/current"]
        log_text = entry["log_run"].get("text", "")
        for match in re.findall(r"/(?:var|data)/log/[A-Za-z0-9_.-]+(?:/current)?", log_text):
            directory = match[:-8] if match.endswith("/current") else match
            if service_match(directory.rsplit("/", 1)[-1]):
                candidates.append(directory + "/current")
        entry["logs"] = []
        for candidate in dict.fromkeys(candidates):
            if candidate in log_paths or len(log_paths) >= 32:
                continue
            log_paths.add(candidate)
            entry["logs"].append(reader.read(candidate, 16384, tail=True))
        result["services"].append(entry)
    result["logs_limit_reached"] = len(log_paths) >= 32
    return result


def parse_config(text):
    result = []
    section = "DEFAULT"
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = redact(line[1:-1])[:128]
            continue
        match = re.match(r"([A-Za-z0-9_]+)\s*=\s*(.*)", line)
        if not match or match.group(1).upper() not in CONFIG_KEYS:
            continue
        value = re.split(r"\s[;#]", match.group(2), maxsplit=1)[0].strip()
        result.append({"section": section, "key": match.group(1).upper(),
                       "value": redact(value)[:512]})
    return result


def config_snapshot(reader, budget):
    result = {"files": [], "allowlisted_keys": sorted(CONFIG_KEYS),
              "note": "Configured/default text only; no claim that a running process loaded these files."}
    for directory in CONFIG_DIRS:
        for name in ("config.ini", "config.default.ini"):
            item = reader.read(directory + "/" + name, 65536, sanitize=False)
            text = item.pop("text", "")
            if item["status"] == "ok":
                item["settings"] = parse_config(text)
            result["files"].append(item)
    return result


def can_snapshot(reader, budget, runner=command):
    result = {"discovery_success": False, "interfaces": [], "truncated": False}
    try:
        budget.remaining()
        entries = list(islice(reader.path("/sys/class/net").iterdir(), 257))
        result.update(discovery_success=True, truncated=len(entries) > 256)
        for path in entries[:256]:
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,15}", path.name):
                continue
            base = "/sys/class/net/" + path.name
            kind = reader.read(base + "/type", 32)
            if kind["status"] != "ok":
                result.setdefault("errors", []).append({"path": base + "/type", "error": kind.get("error")})
                continue
            if kind.get("text", "").strip() != "280":
                continue
            if len(result["interfaces"]) >= MAX_CAN:
                result["truncated"] = True
                break
            item = {"name": path.name, "device_path": str(reader.path(base + "/device").resolve()),
                    "driver_path": str(reader.path(base + "/device/driver").resolve()),
                    "driver_present": reader.path(base + "/device/driver").exists(),
                    "files": [reader.read(base + suffix, 2048) for suffix in (
                        "/operstate", "/device/modalias", "/device/uevent",
                        "/statistics/rx_packets", "/statistics/tx_packets",
                        "/statistics/rx_errors", "/statistics/tx_errors",
                        "/statistics/rx_dropped", "/statistics/tx_dropped")]}
            item["link"] = executable_command("ip", ["-details", "-statistics", "link", "show", "dev", path.name],
                                               budget, runner=runner)
            result["interfaces"].append(item)
    except Exception as exc:
        result["error"] = error_name(exc)
    return result


def packages_snapshot(reader, budget, runner=command):
    result = executable_command("opkg", ["list-installed"], budget, limit=131072, runner=runner)
    text = result.pop("text", "")
    result["packages"] = [line[:512] for line in text.splitlines() if RELEVANT.search(line)][:256]
    result["scope"] = "Relevant packages from bounded output tail; omitted packages are not proven absent."
    return result


def process_snapshot(reader, budget, runner=command):
    result = executable_command("ps", [], budget, limit=65536, runner=runner)
    text = result.pop("text", "")
    result["processes"] = [line[:1024] for line in text.splitlines() if PROCESS_MATCH.search(line)][:128]
    result["scope"] = "Relevant rows from BusyBox-compatible ps; process arguments can be truncated by ps. No environment read."
    return result


def kernel_snapshot(reader, budget, runner=command):
    result = executable_command("dmesg", [], budget, limit=65536, runner=runner)
    lines = result.pop("text", "").splitlines()
    selected = set()
    for index, line in enumerate(lines):
        if KERNEL_MATCH.search(line):
            selected.update(range(max(0, index - 4), min(len(lines), index + 5)))
    indices = sorted(selected)[-240:]
    result["context_truncated"] = len(selected) > 240
    result["context"] = [{"tail_line": n + 1, "text": lines[n][:1024]} for n in indices]
    result["clock"] = "Raw kernel clock; not aligned to report UTC. Search covers retained tail only."
    return result


def scalar(value):
    if value is None or isinstance(value, (list, tuple, Mapping, bytes, bytearray)):
        return {"status": "invalid", "value": None}
    if isinstance(value, str):
        return {"status": "ok", "value": redact(str(value))[:512]}
    if isinstance(value, (int, float)) and math.isfinite(value):
        return {"status": "ok", "value": float(value) if isinstance(value, float) else int(value)}
    return {"status": "invalid", "value": None}


def dbus_call(bus, name, path, interface, member, signature, args, budget):
    return bus.call_blocking(name, path, interface, member, signature, args,
                             timeout=budget.remaining(0.4))


def dbus_owner(bus, service, budget):
    value = str(dbus_call(bus, BUS_NAME, BUS_PATH, BUS_NAME, "GetNameOwner", "s", (service,), budget))
    if not value.startswith(":"):
        raise ValueError("invalid unique owner")
    return value


def dbus_snapshot(reader, budget, bus=None):
    result = {"discovery_success": False, "services": [], "truncated": False,
              "note": "/Control/MaxChargeCurrent is a control flag, not amperes. Read-only values do not approve settings."}
    opened = False
    try:
        budget.remaining()
        if bus is None:
            # A standalone script imports no sibling helpers and writes no project pycache.
            sys.dont_write_bytecode = True
            import dbus
            socket_path = "/run/dbus/system_bus_socket"
            if not reader.path(socket_path).exists():
                socket_path = "/var/run/dbus/system_bus_socket"
            bus = dbus.bus.BusConnection("unix:path=" + socket_path)
            opened = True
        names = dbus_call(bus, BUS_NAME, BUS_PATH, BUS_NAME, "ListNames", "", (), budget)
        if not isinstance(names, (list, tuple)) or any(not isinstance(n, str) for n in names):
            raise ValueError("invalid discovery reply")
        result["discovery_success"] = True
        selected = [n for n in names if n in ("com.victronenergy.system", "com.victronenergy.settings")
                    or n.startswith(("com.victronenergy.battery.", "com.victronenergy.solarcharger."))]
        selected.sort(key=lambda n: (n != "com.victronenergy.system", n != "com.victronenergy.settings", n))
        result["truncated"] = len(selected) > 12
        result["discovered_names"] = [str(n) for n in selected[:12]]
        for name in selected[:12]:
            item = {"service": str(name), "owner": None, "owner_check_status": "error", "values": {}}
            result["services"].append(item)
            paths = SYSTEM_PATHS if name == "com.victronenergy.system" else SETTINGS_PATHS if name == "com.victronenergy.settings" else DEVICE_PATHS
            try:
                service_budget = budget.child(3 if name in ("com.victronenergy.system", "com.victronenergy.settings") else 1.5)
                owner = item["owner"] = dbus_owner(bus, name, service_budget)
                reads = service_budget.child(max(0, service_budget.remaining() - 0.15))
                for path in paths:
                    try:
                        item["values"][path] = scalar(dbus_call(bus, owner, path,
                            "com.victronenergy.BusItem", "GetValue", "", (), reads))
                    except Exception as exc:
                        error = error_name(exc)
                        status = "missing" if error.rsplit(".", 1)[-1] in ("UnknownObject", "UnknownMethod", "UnknownInterface") else "error"
                        item["values"][path] = {"status": status, "value": None, "error": error}
                after = dbus_owner(bus, name, service_budget)
                item["owner_check_status"] = "ok" if owner == after else "changed"
            except Exception as exc:
                item["error"] = error_name(exc)
    except Exception as exc:
        result["error"] = error_name(exc)
    finally:
        if opened:
            bus.close()
    return result


def dbus_worker_snapshot(reader, budget, runner=command):
    """Bound import, system-bus authentication and all reads in our own child."""
    result = runner([sys.executable, "-B", str(Path(__file__).resolve()), "--dbus-worker"],
                    budget, limit=131072, timeout_cap=10, sanitize=False)
    failure = {"discovery_success": False, "services": [], "status": "unknown",
               "worker_status": result.get("status"), "truncated": bool(result.get("truncated"))}
    if result.get("status") != "ok":
        failure["error"] = result.get("error", "dbus_worker_failed")
        return failure
    if result.get("truncated"):
        failure["error"] = "dbus_worker_output_truncated"
        return failure
    try:
        data = json.loads(result.get("text", ""))
        if not isinstance(data, dict) or not isinstance(data.get("discovery_success"), bool) or not isinstance(data.get("services"), list):
            raise ValueError("invalid worker structure")
        return data
    except (ValueError, TypeError):
        failure["error"] = "dbus_worker_invalid_json"
        return failure


def make_snapshot(root=Path("/"), runner=command, bus=None, clock=time.monotonic):
    start = clock()
    budget = Budget(clock=clock)
    reader = Reader(budget, root)
    report = {"schema_version": 1, "type": "config_snapshot", "source": "cerbo",
              "captured_at": utc_now(), "budget_seconds": TOTAL_SECONDS, "sections": {},
              "privacy": "Private diagnostic report: device names, Bluetooth addresses, paths and log context. Credential redaction is best effort.",
              "limits": {"max_files": MAX_FILES, "max_file_bytes": MAX_FILE_BYTES,
                         "max_services": MAX_SERVICES, "max_can_interfaces": MAX_CAN}}
    # Give every evidence source a finite share, with configuration before optional commands.
    sections = (("host", 2, lambda b: host_snapshot(reader, b)),
                ("serialbattery_config", 2, lambda b: config_snapshot(reader, b)),
                ("can", 4, lambda b: can_snapshot(reader, b, runner)),
                ("services", 6, lambda b: service_snapshot(reader, b, runner)),
                ("processes", 1.5, lambda b: process_snapshot(reader, b, runner)),
                ("dbus", 10, lambda b: dbus_snapshot(reader, b, bus) if bus is not None
                 else dbus_worker_snapshot(reader, b, runner)),
                ("packages", 2, lambda b: packages_snapshot(reader, b, runner)),
                ("kernel", 2, lambda b: kernel_snapshot(reader, b, runner)))
    for name, seconds, collect in sections:
        began = clock()
        captured = utc_now()
        try:
            budget.remaining()
            section_budget = budget.child(seconds)
            reader.budget = section_budget
            data = collect(section_budget)
            if data.get("status", "ok") == "ok":
                data["status"] = "partial" if has_incomplete(data) else "ok"
        except Exception as exc:
            data = {"status": "unknown", "error": error_name(exc)}
        data.update(captured_at=captured, elapsed_seconds=round(began - start, 6),
                    duration_seconds=round(clock() - began, 6))
        report["sections"][name] = data
    report.update(duration_seconds=round(clock() - start, 6),
                  files_attempted=reader.files, file_bytes_read=reader.bytes)
    return report


def has_incomplete(value):
    if isinstance(value, dict):
        if value.get("error") or value.get("errors") or value.get("status") in ("unknown", "missing", "error", "unavailable"):
            return True
        if any(value.get(flag) for flag in ("truncated", "context_truncated", "logs_limit_reached")):
            return True
        if value.get("owner_check_status") in ("changed", "error"):
            return True
        return any(has_incomplete(item) for item in value.values())
    if isinstance(value, list):
        return any(has_incomplete(item) for item in value)
    return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dbus-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    sys.dont_write_bytecode = True
    try:
        if args.dbus_worker:
            budget = Budget(10)
            report = dbus_snapshot(Reader(budget), budget)
        else:
            report = make_snapshot()
        print(json.dumps(report, ensure_ascii=True, allow_nan=False, indent=2))
    except BrokenPipeError:
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
