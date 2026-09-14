#!/usr/bin/env python3
"""Build an offline power report from owner-supplied diagnostic JSONL captures.

This module has no network, D-Bus, serial, Bluetooth or hardware access. A value
in a report is an observation, not proof of a fresh measurement at the battery.
"""
import argparse
from collections import Counter
from datetime import datetime
import json
import math
from pathlib import Path
import sys


MAX_BYTES = 64 * 1024 * 1024
MAX_RECORDS = 20000
MAX_DEVICES = 128
MAX_DEVICE_SAMPLES = 500000
FIELDS = {
    "soc": (("/Soc",), 0, 100),
    "voltage": (("/Dc/0/Voltage",), 0, 2000),
    "current": (("/Dc/0/Current",), -1000000, 1000000),
    "power": (("/Dc/0/Power",), -1000000000, 1000000000),
    "temperature": (("/Dc/0/Temperature", "/Temperature"), -100, 300),
    "pv_power": (("/Pv/0/Power",), 0, 1000000000),
    "ac_output_power": (("/Ac/Out/L1/P", "/Ac/Out/L1/Power"), -1000000000, 1000000000),
    "ac_input_voltage": (("/Ac/In/L1/V", "/Ac/In/1/L1/V", "/Ac/ActiveIn/L1/V"), 0, 2000),
    "ac_input_frequency": (("/Ac/In/L1/F", "/Ac/In/1/L1/F", "/Ac/ActiveIn/L1/F"), 0, 1000),
    "grid_l1_power": ((), -1000000000, 1000000000),
    "grid_l2_power": ((), -1000000000, 1000000000),
    "grid_l3_power": ((), -1000000000, 1000000000),
}
VALUE_STATES = {"ok", "invalid", "missing", "error"}
BLOCKED = {"disconnected", "missing", "unknown", "incoherent", "stale"}


class CaptureError(ValueError):
    """Invalid capture or mapping, with context suitable for a CLI error."""


def _finite(value):
    # Integers are finite without conversion to float (huge JSON integers can
    # otherwise raise OverflowError before range validation).
    return (isinstance(value, int) and not isinstance(value, bool)) or (
        isinstance(value, float) and math.isfinite(value))


def _reject_constant(value):
    raise CaptureError("Non-finite JSON constant: " + value)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CaptureError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def _parse_json(text):
    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise CaptureError("Non-finite JSON number: " + value)
        return parsed
    return json.loads(text, parse_constant=_reject_constant, parse_float=finite_float,
                      object_pairs_hook=_unique_object)


def _json_safe(value):
    """Keep invalid raw evidence inspectable without emitting nonstandard JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return {"invalid_nonfinite": str(value)}
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 80:
        raise CaptureError("captured_at must be an ISO 8601 timestamp with a timezone")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CaptureError("captured_at is not an ISO 8601 timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise CaptureError("captured_at must include a timezone")
    return result


def _validate_record(record):
    if (not isinstance(record, dict) or type(record.get("schema_version")) is not int
            or record.get("schema_version") != 1):
        raise CaptureError("Expected a JSON object with schema_version 1")
    if record.get("type") == "error":
        raise CaptureError("Collector error: " + str(record.get("error", "unspecified"))[:256] +
                           ". This record contains no telemetry; it does not establish an empty installation.")
    if record.get("type", "sample") != "sample":
        raise CaptureError("Expected a sample record")
    for key in ("source", "session_id"):
        if not isinstance(record.get(key), str) or not 1 <= len(record[key]) <= 256:
            raise CaptureError(key + " must be a nonempty string of at most 256 characters")
    _timestamp(record.get("captured_at"))
    if not _finite(record.get("elapsed_seconds")) or not 0 <= record["elapsed_seconds"] <= 10 ** 12:
        raise CaptureError("elapsed_seconds must be a finite number between 0 and 1e12")
    for key in ("discovery_success", "discovery_truncated"):
        if not isinstance(record.get(key), bool):
            raise CaptureError(key + " must be a boolean")
    devices = record.get("devices")
    if not isinstance(devices, list) or len(devices) > MAX_DEVICES:
        raise CaptureError("devices must be a list with at most 128 entries")
    names = set()
    for device in devices:
        if not isinstance(device, dict):
            raise CaptureError("Each device must be an object")
        service = device.get("service")
        if not isinstance(service, str) or not 1 <= len(service) <= 512 or service in names:
            raise CaptureError("Device services must be unique nonempty strings")
        names.add(service)
        if device.get("owner") is not None and not isinstance(device["owner"], str):
            raise CaptureError("Device owner must be a string or null")
        if not isinstance(device.get("owner_consistent"), bool):
            raise CaptureError("Device owner_consistent must be a boolean")
        if device.get("owner_check_status") not in (None, "ok", "changed", "error"):
            raise CaptureError("Device owner_check_status must be ok, changed or error")
        if device.get("snapshot_consistent") is not None and not isinstance(device["snapshot_consistent"], bool):
            raise CaptureError("Device snapshot_consistent must be a boolean or null")
        values = device.get("values")
        if not isinstance(values, dict) or len(values) > 256:
            raise CaptureError("Device values must be a path-to-observation object")
        for path, item in values.items():
            if not isinstance(path, str) or not isinstance(item, dict) or item.get("status") not in VALUE_STATES:
                raise CaptureError("Every path observation needs status ok, invalid, missing or error")
    for key in ("can", "bluetooth"):
        raw = record.get(key, {})
        if not isinstance(raw, dict):
            raise CaptureError(key + " must be an object")
        entries = raw.get("interfaces" if key == "can" else "devices", [])
        if not isinstance(entries, list) or len(entries) > 256 or any(not isinstance(item, dict) for item in entries):
            raise CaptureError(key + " entries must be a list of at most 256 objects")


def load_records(paths):
    """Read bounded JSONL files. File boundaries always break analysis continuity."""
    if not 1 <= len(paths) <= 20:
        raise CaptureError("Supply between 1 and 20 JSONL capture files")
    records, total_bytes = [], 0
    for file_index, name in enumerate(paths):
        path = Path(name)
        size = path.stat().st_size
        total_bytes += size
        if total_bytes > MAX_BYTES:
            raise CaptureError("Capture inputs exceed the combined 64 MiB limit")
        with path.open("r", encoding="utf-8-sig") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    record = _parse_json(line)
                    _validate_record(record)
                except (ValueError, RecursionError) as exc:
                    raise CaptureError(f"{path.name}:{line_number}: {exc}") from exc
                record["_capture_file"] = str(file_index)
                records.append(record)
                if len(records) > MAX_RECORDS:
                    raise CaptureError("Capture inputs exceed the 20,000 sample limit")
    if not records:
        raise CaptureError("No sample records found")
    return records


def _mapping(mapping):
    if mapping is None:
        return {}
    if not isinstance(mapping, dict) or not isinstance(mapping.get("devices", {}), dict):
        raise CaptureError("Mapping must contain a devices object keyed by exact service name")
    devices = mapping.get("devices", {})
    for service, item in devices.items():
        if not isinstance(service, str) or not isinstance(item, dict):
            raise CaptureError("Mapping entries must be service-name objects")
        for key in ("label", "bank", "transport"):
            if key in item and (not isinstance(item[key], str) or len(item[key]) > 512):
                raise CaptureError("Mapping labels, banks and transports must be strings of at most 512 characters")
    return devices


def _value(values, paths, minimum, maximum):
    for path in paths:
        item = values.get(path, {"status": "missing"})
        status = item.get("status", "missing")
        if status == "missing":
            continue
        if status != "ok":
            return None, status
        value = item.get("value")
        if not _finite(value):
            return None, "invalid"
        if not minimum <= value <= maximum:
            return None, "out_of_range"
        return value, "ok"
    return None, "missing"


def _connected(values):
    item = values.get("/Connected", {})
    if item.get("status") == "ok":
        value = item.get("value")
        if isinstance(value, bool):
            return value
        if _finite(value) and value in (0, 1):
            return bool(value)
    return None


def _index(values):
    value, status = _value(values, ("/UpdateIndex",), 0, 2 ** 53)
    return int(value) if status == "ok" and int(value) == value else None


def _event(report, device, sample, kind, severity, message):
    event = {"at": sample["at"], "device": device["id"] if device else "collector",
             "kind": kind, "severity": severity, "message": message}
    report["events"].append(event)
    if device:
        device["events"].append(event)


def _transport_events(report, record, segment, previous):
    stamp = {"at": record["captured_at"], "elapsed": record["elapsed_seconds"],
             "session_id": record["session_id"], "segment": segment}
    for kind in ("can", "bluetooth"):
        raw = record.get(kind, {"status": "not_collected"})
        report["transport"][kind].append(dict(stamp, snapshot=_json_safe(raw)))
        state_key = (segment, record["source"], kind)
        earlier = previous.get(state_key, {})
        current = {}
        if raw.get("status") not in ("ok", "partial"):
            previous[state_key] = current
            continue
        if kind == "can":
            for interface in raw.get("interfaces", []):
                name, stats = interface.get("name"), interface.get("stats", {})
                if not isinstance(name, str) or not isinstance(stats, dict):
                    continue
                for counter in ("rx_errors", "tx_errors", "rx_dropped", "tx_dropped", "rx_packets", "tx_packets"):
                    value = stats.get(counter)
                    if not _finite(value) or value < 0:
                        continue
                    key = (name, counter)
                    current[key] = value
                    old = earlier.get(key)
                    if old is None or old == value:
                        continue
                    reset = value < old
                    if not reset and counter in ("rx_packets", "tx_packets"):
                        continue
                    report["events"].append({"at": stamp["at"], "device": "can:" + name,
                        "kind": "can_counter_reset" if reset else "can_counter_increase",
                        "severity": "info" if reset else "warning",
                        "message": f"{name} {counter}: {old} -> {value}. " +
                            ("Counter reset or interface replacement; no loss delta calculated." if reset else
                             "Interface observation; no battery or root cause inferred.")})
        else:
            for remote in raw.get("devices", []):
                path, connected = remote.get("path"), remote.get("connected")
                if not isinstance(path, str) or not isinstance(connected, bool):
                    continue
                current[path] = connected
                if path in earlier and earlier[path] != connected:
                    report["events"].append({"at": stamp["at"], "device": "bluetooth:" + path,
                        "kind": "bluetooth_connected_changed", "severity": "info" if connected else "warning",
                        "message": f"BlueZ {path} Connected changed to {connected}. "
                            "This device is not automatically associated with either battery."})
        previous[state_key] = current


def analyze(records, mapping=None, stale_after=35):
    """Normalize observed telemetry; never combine banks or synthesize missing power."""
    if not _finite(stale_after) or stale_after <= 0:
        raise CaptureError("stale_after must be a finite positive number")
    if not isinstance(records, (list, tuple)) or not 1 <= len(records) <= MAX_RECORDS:
        raise CaptureError("Expected 1 to 20,000 sample records")
    labels = _mapping(mapping)
    sources = {}
    for position, record in enumerate(records, 1):
        try:
            _validate_record(record)
        except CaptureError as exc:
            raise CaptureError(f"Record {position}: {exc}") from exc
        for device in record["devices"]:
            sources[(record["source"], device["service"])] = None
    if len(sources) > MAX_DEVICES or len(sources) * len(records) > MAX_DEVICE_SAMPLES:
        raise CaptureError("Capture exceeds the report limit of 128 devices or 500,000 device samples")
    report = {"schema_version": 1, "demo": False,
              "summary": {"samples": len(records), "start": records[0]["captured_at"],
                          "end": records[-1]["captured_at"], "duration_seconds": 0, "sessions": 0},
              "devices": [], "events": [], "transport": {"can": [], "bluetooth": []}, "observer": [],
              "notes": ["All values are observations from existing services; no hardware settings were written.",
                  "Independent batteries remain separate. No energy, Grid power, SOC or charging phase is derived.",
                  "UpdateIndex activity describes service activity, not freshness of each measurement. Unsupported index means unverified freshness.",
                  "UpdateIndex may not be periodic for every service. Withholding after an unchanged index is a configurable conservative capture policy, not proof of a transport failure.",
                  "A reported Connected value or changing telemetry does not prove valid battery communication.",
                  "Partial SOC telemetry and CAN/Bluetooth counters are observations, not a root-cause diagnosis.",
                  "Files and sessions form separate chart segments. Raw timestamp labels are retained; duration uses monotonic elapsed time.",
                  "Snapshot timestamps mark the start of sequential reads; device and transport observations are not synchronized hardware measurements.",
                  "Captures may include private device identifiers and logs. Share only after reviewing locally."]}
    for source, service in sources:
        mapped = labels.get(source + "::" + service, labels.get(service, {}))
        default_label = "System overview (sources may differ)" if service == "com.victronenergy.system" else service
        device = {"id": source + "::" + service, "source": source, "service": service,
                  "label": mapped.get("label") or default_label, "bank": mapped.get("bank") or "unassigned",
                  "transport": mapped.get("transport") or "unknown", "samples": [], "events": [],
                  "latest": None, "counts": {}}
        sources[(source, service)] = device
        report["devices"].append(device)
    device_state, transport_state, latest_raw, seen_devices = {}, {}, {}, set()
    last_key, segment, last_elapsed, last_at = None, "", None, None
    block, chart_epoch = 0, 0
    for record in records:
        key = (record.get("_capture_file", "memory"), record["session_id"], record["source"])
        elapsed, at = record["elapsed_seconds"], record["captured_at"]
        if key != last_key:
            block += 1
            segment = str(block) + ":" + record["session_id"]
            report["summary"]["sessions"] += 1
            device_state = {}
            last_elapsed, last_at = None, None
        if last_elapsed is not None:
            if elapsed <= last_elapsed:
                raise CaptureError("elapsed_seconds must increase within a file/session; use a new session_id after restart")
            report["summary"]["duration_seconds"] += elapsed - last_elapsed
            if _timestamp(at) < _timestamp(last_at):
                chart_epoch += 1
                _event(report, None, {"at": at}, "clock_moved_backwards", "warning",
                       "Wall clock moved backwards; monotonic elapsed time still orders this session.")
            elif elapsed - last_elapsed > stale_after:
                chart_epoch += 1
                _event(report, None, {"at": at}, "observation_gap", "info",
                       "Sample interval exceeded the freshness threshold. Chart lines break across this unobserved period.")
        last_key, last_elapsed, last_at = key, elapsed, at
        observer = {"at": at, "elapsed": elapsed, "session_id": record["session_id"], "segment": segment,
                    "collection_duration_seconds": record.get("collection_duration_seconds"),
                    "discovery_success": record["discovery_success"],
                    "discovery_truncated": record["discovery_truncated"],
                    "errors": record.get("errors", []), "host": record.get("host", {"status": "not_collected"})}
        if "logs" in record:
            observer["logs"] = record["logs"]
        report["observer"].append(_json_safe(observer))
        present = {item["service"]: item for item in record["devices"]}
        for (source, service), device in sources.items():
            if source != record["source"]:
                continue
            raw = present.get(service)
            sample = {"at": at, "elapsed": elapsed, "session_id": record["session_id"], "segment": segment,
                      "status": "unknown", "connected": None, "owner": None,
                      "values": {field: None for field in FIELDS},
                      "field_status": {field: "unavailable" for field in FIELDS},
                      "freshness": "unavailable", "snapshot_consistent": None,
                      "metadata": {"source_paths": {}, "read_method": None}}
            previous = device_state.get(device["id"], {})
            temporal = dict(previous)
            if raw is None:
                latest_raw[device["id"]] = {}
                sample["status"] = "missing" if (device["id"] in seen_devices and record["discovery_success"]
                                                   and not record["discovery_truncated"]) else "unknown"
                temporal.pop("index", None)
                temporal.pop("index_at", None)
            else:
                seen_devices.add(device["id"])
                latest_raw[device["id"]] = raw["values"]
                sample["metadata"] = {"read_method": raw.get("read_method"),
                    "owner_check_status": raw.get("owner_check_status"), "owner_error": raw.get("error"), "source_paths": {
                    path: raw["values"][path] for path in ("/ActiveBatteryService", "/Dc/Battery/BatteryService",
                        "/Dc/Battery/VoltageService", "/AutoSelectedBatteryService") if path in raw["values"]}}
                sample["owner"] = raw.get("owner")
                sample["connected"] = _connected(raw["values"])
                sample["snapshot_consistent"] = raw.get("snapshot_consistent")
                owner_changed = (previous.get("owner") is not None and sample["owner"] is not None
                                 and raw.get("owner_check_status") != "error"
                                 and previous["owner"] != sample["owner"])
                if owner_changed:
                    temporal["owner_generation"] = previous.get("owner_generation", 0) + 1
                    _event(report, device, sample, "owner_changed", "warning",
                           "D-Bus owner changed. This can indicate a service restart; freshness history was reset.")
                    temporal.pop("index", None)
                    temporal.pop("index_at", None)
                if not sample["owner"] or raw.get("owner_check_status") == "error":
                    sample["status"] = "unknown"
                elif not raw["owner_consistent"] or raw.get("snapshot_consistent") is False:
                    sample["status"] = "incoherent"
                elif sample["connected"] is False:
                    sample["status"] = "disconnected"
                else:
                    for field, (paths, minimum, maximum) in FIELDS.items():
                        if service == "com.victronenergy.system" and field in ("soc", "voltage", "current", "power"):
                            paths = ("/Dc/Battery/" + field.capitalize(),)
                        if field == "pv_power" and service.startswith("com.victronenergy.solarcharger."):
                            paths = paths + ("/Yield/Power",)
                        if field == "ac_output_power" and service.startswith("com.victronenergy.inverter."):
                            paths = paths + ("/Ac/L1/Power",)
                        if field.startswith("grid_l"):
                            phase = field.split("_")[1].upper()
                            if service.startswith("com.victronenergy.grid."):
                                paths = ("/Ac/" + phase + "/Power",)
                            elif service == "com.victronenergy.system":
                                paths = ("/Ac/Grid/" + phase + "/Power",)
                        sample["values"][field], sample["field_status"][field] = _value(raw["values"], paths, minimum, maximum)
                    index = _index(raw["values"])
                    if index is None:
                        sample["freshness"] = "unverified"
                        temporal.pop("index", None)
                        temporal.pop("index_at", None)
                    elif temporal.get("index") != index:
                        sample["freshness"] = "index_advanced" if "index" in temporal else "index_observed"
                        temporal["index"], temporal["index_at"] = index, elapsed
                    elif elapsed - temporal["index_at"] > stale_after:
                        sample["freshness"] = "index_stalled"
                    else:
                        sample["freshness"] = "index_observed"
                    available = any(value is not None for value in sample["values"].values())
                    battery_partial = service.startswith("com.victronenergy.battery.") and any(
                        sample["values"][field] is None for field in ("soc", "voltage", "current"))
                    sample["status"] = "partial" if battery_partial and available else "usable" if available else "unknown"
                    if sample["freshness"] == "index_stalled":
                        sample["status"] = "stale"
                    if battery_partial and sample["values"]["soc"] is None and all(
                            sample["values"][field] is not None for field in ("voltage", "current")):
                        if not previous.get("soc_partial", False):
                            _event(report, device, sample, "soc_missing_with_voltage_current", "warning",
                                   "SOC is unavailable while voltage and current are present. Partial telemetry does not prove a CAN failure.")
                        temporal["soc_partial"] = True
                    else:
                        temporal["soc_partial"] = False
            if sample["status"] in BLOCKED:
                for field in FIELDS:
                    sample["values"][field] = None
                    if sample["field_status"][field] == "ok":
                        sample["field_status"][field] = "withheld_" + sample["status"]
                if sample["status"] != "stale":
                    temporal.pop("index", None)
                    temporal.pop("index_at", None)
                    temporal["soc_partial"] = False
            old_status = previous.get("status")
            if old_status != sample["status"]:
                severity = "info" if sample["status"] == "usable" else "warning"
                messages = {
                    "usable": "Numeric observations available; freshness and connection remain separately qualified.",
                    "partial": "Some battery measurements are unavailable. Available fields remain separate from missing fields.",
                    "disconnected": "Service reports Connected=0. Retained numeric values are withheld.",
                    "missing": "Service absent from a successful, complete discovery. Numeric values are withheld.",
                    "unknown": "Observer evidence is insufficient for usable telemetry. No device outage is inferred.",
                    "incoherent": "Owner or snapshot changed during collection. Numeric values are withheld.",
                    "stale": "UpdateIndex was unchanged in observations beyond the configured interval. Numeric values are withheld by capture policy; this does not prove transport failure.",
                }
                _event(report, device, sample, "status_" + sample["status"], severity, messages[sample["status"]])
            if old_status == "missing" and raw is not None:
                _event(report, device, sample, "service_reappeared", "info", "Service reappeared in discovery; data validity is evaluated separately.")
            if raw is not None and sample["owner"] is not None and raw.get("owner_check_status") != "error":
                temporal["owner"] = sample["owner"]
            temporal["status"] = sample["status"]
            sample["segment"] = segment + ":" + str(chart_epoch) + ":" + str(temporal.get("owner_generation", 0))
            device_state[device["id"]] = temporal
            device["samples"].append(sample)
            device["latest"] = sample
        _transport_events(report, record, segment, transport_state)
    for device in report["devices"]:
        device["counts"] = dict(Counter(sample["status"] for sample in device["samples"]))
        device["latest"]["raw_values"] = _json_safe(latest_raw.get(device["id"], {}))
    if not report["devices"]:
        report["notes"].append("No device services were observed. Empty discovery does not identify either battery.")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("captures", nargs="*", help="Owner-supplied JSONL files, processed in supplied order")
    parser.add_argument("--mapping", help="Local JSON mapping of exact service names to labels/banks/transports")
    parser.add_argument("--stale-after", type=float, default=35, help="Unchanged UpdateIndex interval in seconds (default: 35)")
    parser.add_argument("--output", default="outputs/power-report.html", help="Self-contained local HTML output")
    parser.add_argument("--json-output", help="Also write normalized report JSON locally")
    parser.add_argument("--demo", action="store_true", help="Use clearly labelled synthetic example data")
    args = parser.parse_args(argv)
    if args.demo and args.captures:
        parser.error("--demo cannot be combined with capture files")
    if not args.demo and not args.captures:
        parser.error("Supply capture files or --demo")
    try:
        mapping = None
        if args.mapping:
            if Path(args.mapping).stat().st_size > 1024 * 1024:
                raise CaptureError("Mapping exceeds 1 MiB")
            mapping = _parse_json(Path(args.mapping).read_text(encoding="utf-8-sig"))
        if args.demo:
            from power_demo import demo_mapping, demo_records
            records = demo_records()
            mapping = mapping if mapping is not None else demo_mapping()
        else:
            records = load_records(args.captures)
        outputs = [Path(args.output)] + ([Path(args.json_output)] if args.json_output else [])
        inputs = [Path(path).resolve() for path in args.captures] + ([Path(args.mapping).resolve()] if args.mapping else [])
        if any(path.resolve() in inputs for path in outputs) or len({path.resolve() for path in outputs}) != len(outputs):
            raise CaptureError("Outputs must be distinct and must not overwrite captures or mapping")
        report = analyze(records, mapping, args.stale_after)
        report["demo"] = args.demo
        from power_dashboard import render
        html = render(report)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(html, encoding="utf-8")
        if args.json_output:
            Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json_output).write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(1, f"Report failed: {exc}\n")
    print(f"Wrote {Path(args.output).resolve()} ({len(report['devices'])} services, {len(records)} samples)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
