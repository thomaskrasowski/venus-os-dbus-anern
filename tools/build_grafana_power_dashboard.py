#!/usr/bin/env python3
"""Build the native Grafana Power Observatory dashboard deterministically."""
import argparse
import json
from pathlib import Path


PROM_UID = "PBFA97CFB590B2093"
DS = {"type": "prometheus", "uid": "${DS_PROMETHEUS}"}


def target(expr, legend, ref="A"):
    return {"refId": ref, "expr": expr, "legendFormat": legend,
            "range": True, "datasource": DS}


def timeseries(panel_id, title, description, x, y, w, h, unit, targets,
               minimum=None, maximum=None):
    defaults = {"unit": unit, "color": {"mode": "palette-classic"},
                "custom": {"drawStyle": "line", "lineInterpolation": "linear",
                           "lineWidth": 2, "fillOpacity": 12, "gradientMode": "opacity",
                           "showPoints": "auto", "pointSize": 5, "spanNulls": False,
                           "axisPlacement": "auto", "axisColorMode": "text",
                           "axisLabel": "", "scaleDistribution": {"type": "linear"},
                           "hideFrom": {"tooltip": False, "viz": False, "legend": False},
                           "thresholdsStyle": {"mode": "off"}},
                "thresholds": {"mode": "absolute", "steps": [{"color": "green"}]}}
    if minimum is not None:
        defaults["min"] = minimum
    if maximum is not None:
        defaults["max"] = maximum
    return {"id": panel_id, "type": "timeseries", "title": title,
            "description": description, "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "datasource": DS, "targets": targets,
            "fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {"legend": {"displayMode": "table", "placement": "bottom",
                                    "calcs": ["lastNotNull", "min", "max"]},
                        "tooltip": {"mode": "multi", "sort": "none"}}}


def stat(panel_id, title, description, x, y, w, expr, legend, unit="none",
         thresholds=None, mappings=None):
    thresholds = thresholds or [{"color": "red"}, {"color": "green", "value": 1}]
    return {"id": panel_id, "type": "stat", "title": title, "description": description,
            "gridPos": {"x": x, "y": y, "w": w, "h": 4}, "datasource": DS,
            "targets": [target(expr, legend)],
            "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "thresholds"},
                "mappings": mappings or [{"type": "value", "options": {
                    "0": {"text": "NO", "color": "red"},
                    "1": {"text": "YES", "color": "green"}}}],
                "thresholds": {"mode": "absolute", "steps": thresholds}}, "overrides": []},
            "options": {"reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
                        "orientation": "auto", "textMode": "auto", "colorMode": "background",
                        "graphMode": "area", "justifyMode": "auto", "wideLayout": True,
                        "showPercentChange": False}}


def row(panel_id, title, y, collapsed=False):
    return {"id": panel_id, "type": "row", "title": title,
            "gridPos": {"x": 0, "y": y, "w": 24, "h": 1},
            "collapsed": collapsed, "panels": []}


def state_timeline(panel_id, title, description, x, y, w, h, targets):
    return {"id": panel_id, "type": "state-timeline", "title": title,
            "description": description, "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "datasource": DS, "targets": targets,
            "fieldConfig": {"defaults": {"unit": "none", "color": {"mode": "thresholds"},
                "mappings": [{"type": "value", "options": {
                    "0": {"text": "Unavailable", "color": "red"},
                    "1": {"text": "Observed", "color": "green"}}}],
                "thresholds": {"mode": "absolute", "steps": [
                    {"color": "red"}, {"color": "green", "value": 1}]},
                "custom": {"lineWidth": 0, "fillOpacity": 75,
                           "spanNulls": False, "hideFrom": {"legend": False,
                           "tooltip": False, "viz": False}}}, "overrides": []},
            "options": {"mergeValues": True, "showValue": "auto", "alignValue": "left",
                        "rowHeight": 0.8, "legend": {"displayMode": "list", "placement": "bottom"},
                        "tooltip": {"mode": "single", "sort": "none"}}}


def build_dashboard():
    panels = [{
        "id": 1, "type": "text", "title": "Scope, safety and current data state",
        "gridPos": {"x": 0, "y": 0, "w": 24, "h": 5},
        "options": {"mode": "markdown", "content":
            "## Cerbo Power Observatory\n"
            "Separate monitoring for **battery1 / inverter1** and **battery2 / inverter2**. "
            "Battery1 is owner-reported JK-BMS over Bluetooth on Cerbo; battery2 is owner-reported JK-BMS over CAN. "
            "Home Assistant is a later additional source.\n\n"
            "**No matching Cerbo/JK/power-monitor series were present in Minizon Prometheus at publication time (2026-09-14).** "
            "Blank panels mean no telemetry. Unknown, invalid and stale values must never be exported as zero. "
            "This dashboard does not change Cerbo, BMS, DVCC, charging or inverter settings.\n\n"
            "The normalized `power_monitor_*` metric contract is prepared for a reviewed collector. Existing `anern_*` AC-input V/Hz are also queried. "
            "Grid W appears only from a real, explicitly mapped Grid measurement; output power is never relabelled as Grid power."}
    }]
    panels += [row(2, "Collection and communication status", 5),
        stat(3, "Collector reachable", "Successful scrape of the normalized power collector. Scrape success is not device health.", 0, 6, 4,
             'max(power_monitor_observer_up{source=~"$source"})', "collector"),
        stat(4, "Battery 1 sample fresh", "Exporter-qualified freshness for explicitly mapped battery1. Unsupported freshness remains no telemetry.", 4, 6, 4,
             'max(power_monitor_battery_sample_fresh{bank="battery1",source=~"$source"})', "battery1"),
        stat(5, "Battery 2 sample fresh", "Exporter-qualified freshness for explicitly mapped battery2. This does not establish CAN health.", 8, 6, 4,
             'max(power_monitor_battery_sample_fresh{bank="battery2",source=~"$source"})', "battery2"),
        stat(6, "Battery 1 Bluetooth link", "BlueZ link state for a device explicitly mapped to battery1. Link state does not prove fresh BMS payloads.", 12, 6, 4,
             'max(power_monitor_bluetooth_connected{bank="battery1",source=~"$source"})', "battery1 BLE"),
        stat(7, "Battery 2 D-Bus connected", "The battery2 service-reported connection flag. It is separate from CAN controller state and per-field validity.", 16, 6, 4,
             'max(power_monitor_battery_connected{bank="battery2",source=~"$source"})', "battery2"),
        stat(8, "CAN RX errors / 15m", "Increase of interface-wide CAN RX errors. It is not automatically attributable to battery2.", 20, 6, 4,
             'sum(increase(power_monitor_can_rx_errors_total{source=~"$source"}[15m]))', "CAN RX errors", "short",
             [{"color": "green"}, {"color": "red", "value": 1}], []),
        row(9, "Battery banks — independent measurements", 10),
        timeseries(10, "State of charge", "Per-device SOC only. No averaged or combined bank SOC.", 0, 11, 12, 8, "percent",
                   [target('power_monitor_battery_soc_percent{bank=~"battery1|battery2",source=~"$source"}', "{{bank}} · {{source}} · {{device}}")], 0, 100),
        state_timeline(11, "Field validity", "A missing SOC with present voltage/current is partial telemetry evidence; it does not prove a CAN-layer fault.", 12, 11, 12, 8,
            [target('power_monitor_battery_soc_valid{bank=~"battery1|battery2",source=~"$source"}', "{{bank}} SOC", "A"),
             target('power_monitor_battery_voltage_valid{bank=~"battery1|battery2",source=~"$source"}', "{{bank}} voltage", "B"),
             target('power_monitor_battery_current_valid{bank=~"battery1|battery2",source=~"$source"}', "{{bank}} current", "C")]),
        timeseries(12, "Battery voltage", "Per-service voltage. System overview fallback voltage is excluded unless exported as a separate source.", 0, 19, 12, 8, "volt",
                   [target('power_monitor_battery_voltage_volts{bank=~"battery1|battery2",source=~"$source"}', "{{bank}} · {{source}} · {{device}}")]),
        timeseries(13, "Battery current", "Source-reported sign convention; verify charge/discharge polarity for each integration.", 12, 19, 12, 8, "amp",
                   [target('power_monitor_battery_current_amperes{bank=~"battery1|battery2",source=~"$source"}', "{{bank}} · {{source}} · {{device}}")]),
        timeseries(14, "Battery power", "Reported power only. The dashboard does not multiply asynchronous voltage and current or total the banks.", 0, 27, 12, 8, "watt",
                   [target('power_monitor_battery_power_watts{bank=~"battery1|battery2",source=~"$source"}', "{{bank}} · {{source}} · {{device}}")]),
        timeseries(15, "Battery temperature", "Per-device reported temperatures. Missing sensors remain absent.", 12, 27, 12, 8, "celsius",
                   [target('power_monitor_battery_temperature_celsius{bank=~"battery1|battery2",source=~"$source"}', "{{bank}} · {{sensor}} · {{source}}")]),
        timeseries(16, "Cell voltage extrema", "BMS-reported minimum and maximum cell voltage. Cell identity is shown only if the source supplies it.", 0, 35, 12, 8, "volt",
                   [target('power_monitor_battery_min_cell_voltage_volts{bank=~"battery1|battery2",source=~"$source"}', "{{bank}} minimum", "A"),
                    target('power_monitor_battery_max_cell_voltage_volts{bank=~"battery1|battery2",source=~"$source"}', "{{bank}} maximum", "B")]),
        state_timeline(17, "BMS permissions and alarms", "Observed read-only BMS permission/alarm values. This dashboard does not change charge or discharge permissions.", 12, 35, 12, 8,
            [target('power_monitor_battery_allow_charge{bank=~"battery1|battery2",source=~"$source"}', "{{bank}} allow charge", "A"),
             target('power_monitor_battery_allow_discharge{bank=~"battery1|battery2",source=~"$source"}', "{{bank}} allow discharge", "B"),
             target('1 - clamp_max(power_monitor_battery_alarm_active{bank=~"battery1|battery2",source=~"$source"}, 1)', "{{bank}} no alarm · {{alarm}}", "C")]),
        row(18, "Transport evidence — observational only", 43),
        state_timeline(19, "Bluetooth connection and services", "BlueZ Connected and ServicesResolved are link/service-discovery states, not BMS payload freshness. Requires explicit device-to-bank mapping.", 0, 44, 12, 8,
            [target('power_monitor_bluetooth_connected{source=~"$source"}', "{{bank}} · connected · {{device}}", "A"),
             target('power_monitor_bluetooth_services_resolved{source=~"$source"}', "{{bank}} · services resolved · {{device}}", "B")]),
        timeseries(20, "Bluetooth RSSI", "Optional advertising/inquiry RSSI. An absent value is unknown; it is not a disconnection event.", 12, 44, 12, 8, "dBm",
                   [target('power_monitor_bluetooth_rssi_dbm{source=~"$source"}', "{{bank}} · {{device}}")]),
        timeseries(21, "CAN controller error counters", "Interface-wide kernel counters. ERROR-ACTIVE is normal controller state; changes require correlation with service and field validity.", 0, 52, 12, 8, "short",
            [target('power_monitor_can_rx_errors_total{source=~"$source"}', "{{interface}} RX errors", "A"),
             target('power_monitor_can_tx_errors_total{source=~"$source"}', "{{interface}} TX errors", "B"),
             target('power_monitor_can_rx_dropped_total{source=~"$source"}', "{{interface}} RX dropped", "C")]),
        timeseries(22, "D-Bus service ownership changes", "Owner changes may indicate service restart. Failed owner verification must not increment this counter.", 12, 52, 12, 8, "short",
                   [target('power_monitor_dbus_owner_changes_total{source=~"$source"}', "{{bank}} · {{service}}")]),
        row(23, "Inverter, PV and AC input", 60),
        timeseries(24, "Inverter output and internal PV", "Inverter output and internal PV are distinct. Neither is Grid import power.", 0, 61, 12, 8, "watt",
            [target('power_monitor_inverter_ac_output_power_watts{bank="battery2",source=~"$source"}', "AC output · {{device}}", "A"),
             target('power_monitor_inverter_pv_power_watts{bank="battery2",source=~"$source"}', "internal PV · {{device}}", "B")]),
        timeseries(25, "Anern AC input voltage", "Existing Anern exporter metric. AC input voltage does not prove relay state or imported power. Device-local L1 is not household L1.", 12, 61, 6, 8, "volt",
                   [target('anern_ac_input_voltage_volts{job="anern-grid"}', "{{instance}}")]),
        timeseries(26, "Anern AC input frequency", "Existing Anern exporter metric. Gaps mean no fresh observation.", 18, 61, 6, 8, "hertz",
                   [target('anern_ac_input_frequency_hertz{job="anern-grid"}', "{{instance}}")]),
        timeseries(27, "Real Grid power, when available", "Only a real, explicitly mapped Grid source may publish this series. No inverter output or battery/PV estimate is substituted.", 0, 69, 24, 8, "watt",
                   [target('power_monitor_grid_power_watts{source=~"$source"}', "{{boundary}} · {{phase}} · {{source}} · {{device}}")]),
        {"id": 28, "type": "text", "title": "Interpretation guide",
         "gridPos": {"x": 0, "y": 77, "w": 24, "h": 5},
         "options": {"mode": "markdown", "content":
            "**SOC missing while V/A remain:** first compare the per-battery service with the GX system-selected battery and voltage services. The overview may retain V/A from another source. "
            "Treat the symptom as partial telemetry until service ownership, source selection and CAN evidence correlate.\n\n"
            "**Bluetooth:** separate link loss, incomplete service discovery and connected-but-invalid telemetry. Do not assume a JK-BMS accepts two simultaneous active clients when Home Assistant is added.\n\n"
            "**Timing:** scrape time is observer time, not a synchronized hardware timestamp. Sampling can miss short faults. Do not calculate energy or cross-bank balance from these panels."}}
    ]
    return {
        "annotations": {"list": [{"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                                     "enable": True, "hide": True, "iconColor": "rgba(0, 211, 255, 1)",
                                     "name": "Annotations & Alerts", "type": "dashboard"}]},
        "description": "Read-only Cerbo power and BMS stability observatory. Batteries remain independent; transport state and field validity are qualified separately.",
        "editable": True, "fiscalYearStartMonth": 0, "graphTooltip": 1, "id": None,
        "links": [], "liveNow": False, "panels": panels, "refresh": "15s",
        "schemaVersion": 41, "tags": ["cerbo", "jk-bms", "power", "diagnostics", "read-only"],
        "templating": {"list": [
            {"current": {"selected": True, "text": "Prometheus", "value": PROM_UID},
             "hide": 0, "includeAll": False, "label": "Prometheus", "multi": False,
             "name": "DS_PROMETHEUS", "options": [], "query": "prometheus", "refresh": 1,
             "regex": "", "skipUrlSync": False, "type": "datasource"},
            {"allValue": ".*", "current": {"selected": True, "text": "All", "value": "$__all"},
             "definition": "label_values(power_monitor_observer_up, source)", "hide": 0,
             "includeAll": True, "label": "Source", "multi": True, "name": "source", "options": [],
             "query": {"query": "label_values(power_monitor_observer_up, source)", "refId": "PowerSourceVariable"},
             "refresh": 1, "regex": "", "skipUrlSync": False, "sort": 1, "type": "query",
             "datasource": DS}]},
        "time": {"from": "now-6h", "to": "now"}, "timepicker": {},
        "timezone": "browser", "title": "Cerbo Power Observatory", "uid": "cerbo-power-observatory",
        "version": 0, "weekStart": ""
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("monitoring/grafana-power-observatory.json"))
    args = parser.parse_args(argv)
    dashboard = build_dashboard()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(dashboard['panels'])} panels)")


if __name__ == "__main__":
    main()
