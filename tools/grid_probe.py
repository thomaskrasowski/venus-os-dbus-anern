#!/usr/bin/env python3
"""Read existing Cerbo D-Bus values over SSH; no serial access or target file writes."""
import argparse
import json
import re
import subprocess

SERVICE = "com.victronenergy.inverter.anern2"
SERVICE_RE = re.compile(r"com\.victronenergy\.inverter\.[A-Za-z0-9_.-]+\Z")
TARGET_RE = re.compile(r"(?:[A-Za-z0-9_.-]+@)?[A-Za-z0-9][A-Za-z0-9_.-]*\Z")

# This fixed program is passed on standard input, never interpolated into a shell.
# json conversion is provided by dbus-python's numeric/container subclasses.
REMOTE = r'''
import dbus
import json
from pathlib import Path
import sys

service = sys.argv[1]
diagnostics = sys.argv[2] == "diagnostics"
bus = dbus.SystemBus()
def value(name, path):
    try:
        item = bus.get_object(name, path, introspect=False)
        v = item.GetValue(dbus_interface="com.victronenergy.BusItem", timeout=2)
        if isinstance(v, (list, tuple, dict)):
            return None
        return v
    except dbus.DBusException:
        return None

try:
    owner = str(bus.get_name_owner(service))
except dbus.DBusException:
    owner = None

sample = {"service": service, "owner": owner}
for attempt in range(2):
    before = value(service, "/UpdateIndex")
    connected_before = value(service, "/Connected")
    sample["values"] = {
        "voltage": value(service, "/Ac/In/L1/V"),
        "frequency": value(service, "/Ac/In/L1/F"),
    }
    sample["connected"] = value(service, "/Connected")
    after = value(service, "/UpdateIndex")
    try:
        current_owner = str(bus.get_name_owner(service))
    except dbus.DBusException:
        current_owner = None
    sample["update_index"] = after
    sample["coherent"] = (before is not None and before == after
                          and connected_before == sample["connected"]
                          and owner is not None and owner == current_owner)
    if sample["coherent"]:
        break

if diagnostics:
    names = sorted(str(s) for s in bus.list_names() if str(s).startswith(
        ("com.victronenergy.inverter.", "com.victronenergy.grid.",
         "com.victronenergy.vebus.", "com.victronenergy.multi.",
         "com.victronenergy.acsystem.")))
    sample["services"] = names
    system_paths = [
        "/Ac/Grid/L1/Power", "/Ac/Grid/L2/Power", "/Ac/Grid/L3/Power",
        "/Ac/Grid/L1/Current", "/Ac/ActiveIn/Source", "/Ac/In/0/ServiceName",
        "/Ac/In/0/Source", "/Ac/In/NumberOfAcInputs",
    ]
    sample["system"] = {p: value("com.victronenergy.system", p) for p in system_paths}
    sample["settings"] = {
        p: value("com.victronenergy.settings", p) for p in
        ["/Settings/SystemSetup/AcInput1", "/Settings/SystemSetup/AcInput2"]}
    sample["ac_services"] = {
        name: {p: value(name, p) for p in [
            "/Connected", "/Ac/L1/Power", "/Ac/L1/Voltage",
            "/Ac/ActiveIn/L1/P", "/Ac/ActiveIn/ActiveInput",
            "/Ac/NumberOfAcInputs", "/Ac/In/1/Type"]}
        for name in names[:20]
    }
    version = Path("/opt/victronenergy/version")
    sample["venus_version"] = version.read_text().strip() if version.is_file() else None
print(json.dumps(sample, allow_nan=False))
'''


def collect(target, service=SERVICE, timeout=15, diagnostics=False):
    """Use the user's SSH config/agent. Never request or print a password."""
    if not TARGET_RE.fullmatch(target):
        raise ValueError("Use an SSH config alias or user@hostname / IPv4 address")
    if not SERVICE_RE.fullmatch(service):
        raise ValueError("Expected a com.victronenergy.inverter.* service")
    command = [
        "ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", "ConnectTimeout=5", target, "python", "-", service,
        "diagnostics" if diagnostics else "sample",
    ]
    result = subprocess.run(command, input=REMOTE, text=True, encoding="utf-8",
                            capture_output=True, timeout=timeout, check=False)
    if result.returncode:
        # Do not echo arbitrary target output or credentials to a metrics endpoint.
        raise RuntimeError("SSH/D-Bus read failed; check SSH access and remote Python/dbus")
    data = json.loads(result.stdout)
    if not isinstance(data, dict) or data.get("service") != service:
        raise ValueError("Unexpected snapshot")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-target", required=True, help="SSH alias or user@hostname")
    parser.add_argument("--service", default=SERVICE)
    parser.add_argument("--diagnostics", action="store_true")
    args = parser.parse_args()
    try:
        data = collect(args.ssh_target, args.service,
                       timeout=120 if args.diagnostics else 15,
                       diagnostics=args.diagnostics)
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Probe failed: {exc}\n")
    print(json.dumps(data, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
