# Power dashboard and read-only stability diagnostics

Prepared locally on 2026-09-14. The HTML dashboard reviews finite captures
offline. A native dashboard was also published to Minizon Grafana; it currently
has no matching live metrics. Neither dashboard is connected to Cerbo, Home
Assistant or VRM. The production driver and existing Grid tools are unchanged.
The owner runs any live capture; assistants still require approval before every
Cerbo connection.

## Current installation report

The owner reports JK-BMS on both batteries, battery2 connected through CAN,
and battery1 Bluetooth handled by Cerbo GX. Battery2 intermittently loses SOC
while voltage/current remain visible; battery1 loses Bluetooth connection.
The owner also mentioned a larger "600Amps" model. Exact model, firmware,
capacity, driver version, service identities and CAN interface remain unverified.
That description is not interpreted as a confirmed 600 Ah capacity.

Keep battery1/inverter1 separate from battery2/inverter2. A selected system
battery source is not an aggregate of these banks.

## Start with a small capture

Inside your own existing Cerbo terminal session, these commands read version,
host state and service identities without installing anything:

```sh
date -u
cat /opt/victronenergy/version
cat /proc/uptime
cat /proc/loadavg
dbus -y
```

Paste the output, preferably while the problem is present, and say whether
the missing SOC is on the system overview or the battery's own device page.
Review identifiers before sharing. These commands do not require a token.

The following optional reads identify the overview's selected sources:

```sh
dbus -y com.victronenergy.system /ActiveBatteryService GetValue
dbus -y com.victronenergy.system /Dc/Battery/BatteryService GetValue
dbus -y com.victronenergy.system /Dc/Battery/VoltageService GetValue
dbus -y com.victronenergy.system /Dc/Battery/Soc GetValue
```

An unsupported path or command is useful evidence; include the error. Do not
change settings to make a diagnostic command work. After the actual battery
service is identified, read its `/Connected`, `/Soc`, `/Dc/0/Voltage`,
`/Dc/0/Current` and `/Mgmt/Connection` using the same `GetValue` pattern.
Never use `SetValue` for this workflow.

## Finite advanced capture

[cerbo_diagnostics.py](../tools/cerbo_diagnostics.py) is a standalone owner-run
Python 3 script using Cerbo's existing `dbus-python`. It has no SSH client.
After you choose to place the reviewed script at `/tmp/cerbo_diagnostics.py`,
run it in the foreground in your own terminal:

```sh
python3 /tmp/cerbo_diagnostics.py --samples 1
```

For a short comparison before/during an intermittent problem:

```sh
python3 /tmp/cerbo_diagnostics.py --samples 60 --interval 5
```

This requests 60 observations at nominal five-second intervals, around five
minutes. Slow reads stretch the interval. It stops after the requested count;
Ctrl+C stops it early. The default is one observation; the accepted maximum
is 120. There is no scheduler, auto-reconnect, service installation or listener.

Output is one JSON object per line on stdout. Save the terminal output on your
workstation as `captures/cerbo-fault.jsonl` (UTF-8); exclude prompts and shell
echoes. Alternatively, append `> /tmp/cerbo-fault.jsonl` yourself to the command
if you want a local output file on Cerbo. That shell redirection writes a file;
the collector itself writes only stdout. Any transfer is owner-operated.

`--logs` optionally includes the final 16 KiB of the kernel log in the first
sample. It does not clear the log or follow it. Kernel time remains raw and is
not treated as UTC. No driver logs or configuration files are read automatically.
Once we identify the driver, a short excerpt from its existing log around the
fault will be more useful than an unbounded dump.

What the capture reads:

| Evidence | Meaning and limits |
|---|---|
| Existing D-Bus services, owners and scalar paths | Battery SOC/V/A/W/temperature, alarms, reported BMS limits, cell extrema, inverter/PV/AC and system source selection when present |
| CAN sysfs counters and optional `ip -details -statistics link show dev INTERFACE` | Interface-wide observations; no frame transmission, CAN socket or bitrate changes |
| Existing BlueZ object properties | Cached connection/service-discovery state and optional RSSI; no scanning, pairing or connection attempts |
| `/proc` and Venus version | Uptime, load and selected memory counters to help identify shared-host symptoms |

The collector prefers one `GetItems` response, with a budgeted legacy
`GetValue` fallback. It uses existing unique D-Bus owners without activating
missing device services. A changed owner or inconsistent bracketed read is
qualified. Missing/invalid values and read errors remain distinct.

Limits: at most 32 services, a 15-second collection-operation budget, 0.75-second
D-Bus/subprocess timeouts and finite output excerpts. Local D-Bus initialization
and OS filesystem scheduling are outside a strict wall-clock guarantee. These
reads add some load. Discovery truncation and collection failures are recorded.
The sample timestamp marks collection start, not simultaneous device updates.

## Build and open the dashboard on the workstation

From the repository directory, with Python 3.9 or later:

```powershell
python tools/power_diagnostics.py --demo --output outputs/power-dashboard-demo.html
python tools/power_diagnostics.py captures/cerbo-fault.jsonl --output outputs/power-report.html
```

If the Windows Python launcher is unavailable, the bundled interpreter in this
Codex workspace is:

```powershell
& 'C:/Users/thoma/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' tools/power_diagnostics.py --demo --output outputs/power-dashboard-demo.html
```

Open the generated HTML directly in a browser. It is self-contained: no server,
Internet access, CDN, credentials or ongoing device connection is required.
The demo is conspicuously labelled synthetic. The HTML template in
`monitoring/power-dashboard.html` must first be rendered by the report tool.

Copy [power-mapping.example.json](../monitoring/power-mapping.example.json) into
the ignored `captures/` directory. Replace the two placeholder service names
with exact identities after verifying which physical battery each represents:

```powershell
python tools/power_diagnostics.py captures/cerbo-fault.jsonl --mapping captures/power-mapping.json --output outputs/power-report.html --json-output outputs/power-report.json
```

Without a mapping, device names remain their exact services and banks remain
`unassigned`. Mapping changes labels only; it cannot alter a device. It does not
automatically associate BlueZ addresses or CAN interfaces with a battery.
Multiple capture files can be supplied in order; each file/session breaks
continuity. Capture inputs must be valid JSONL, at most 64 MiB combined.
Keep captures and generated reports private: they contain identifiers and may
include logs. The repository already ignores `captures/` and `outputs/`.

Dashboard features:

- Separate source cards, metric selection, time windows and hover values.
- SOC, DC voltage/current/power, temperature, PV and inverter AC input/output
  when present. Grid phase power only from existing Grid paths; no power totals,
  energy integration or assumed household phase mapping.
- Incident timeline for partial SOC, disconnect/recovery, service disappearance,
  owner changes, CAN counter changes/resets and Bluetooth connection transitions.
- Measurement validity, raw paths, BMS limits/alarms, source identities,
  passive transport snapshots and collector/host evidence.

## Native Grafana dashboard

The generated [Grafana definition](../monitoring/grafana-power-observatory.json)
is built by `tools/build_grafana_power_dashboard.py`. It was published through
the existing Minizon service account on 2026-09-14 and read back as version 1:

- Title/UID: `Cerbo Power Observatory` / `cerbo-power-observatory`
- Folder: `60 - Client Services` (`cfso3l27dkuf4b`)
- Datasource: Minizon `Prometheus` (`PBFA97CFB590B2093`)
- Live URL: <https://opole.minizon.net:3000/d/cerbo-power-observatory/cerbo-power-observatory>

The live Prometheus label inventory contained no metric beginning with
`anern_`, `cerbo_`, `venus_`, `jk_`, `battery_`, `homeassistant_` or the new
`power_monitor_` prefix at publication time. The native dashboard therefore
starts as an accurately labelled scaffold, not a claim that collection is live.

The normalized exporter contract uses `source`, `bank` and `device` labels.
Transport metrics require an explicit physical mapping; a D-Bus suffix, BlueZ
path or CAN interface is not enough to assign a bank. Main metric families are:

| Area | Metric families |
|---|---|
| Observer | `power_monitor_observer_up`, `power_monitor_battery_sample_fresh` |
| Battery | `power_monitor_battery_soc_percent`, `*_voltage_volts`, `*_current_amperes`, `*_power_watts`, `*_temperature_celsius` |
| Validity | `power_monitor_battery_soc_valid`, `*_voltage_valid`, `*_current_valid`, `*_connected` |
| Cell/BMS | `power_monitor_battery_min_cell_voltage_volts`, `*_max_cell_voltage_volts`, `*_allow_charge`, `*_allow_discharge`, `*_alarm_active` |
| Bluetooth | `power_monitor_bluetooth_connected`, `*_services_resolved`, `*_rssi_dbm` |
| CAN/D-Bus | `power_monitor_can_rx_errors_total`, `*_tx_errors_total`, `*_rx_dropped_total`, `power_monitor_dbus_owner_changes_total` |
| Inverter/PV | `power_monitor_inverter_ac_output_power_watts`, `*_pv_power_watts` |
| Grid | `power_monitor_grid_power_watts` only for an explicit real Grid source |

The dashboard also queries the existing optional Anern exporter series
`anern_ac_input_voltage_volts` and `anern_ac_input_frequency_hertz`. Those are
input V/Hz only. The dashboard does not request invented Grid power.

Numeric zero is preserved. Disconnected, inconsistent and unknown observations
do not fill gaps with zero or carry old values forward. If an available
`UpdateIndex` stops advancing, numeric fields are withheld after 35 seconds by
default (`--stale-after` changes this conservative policy). This is not proof
of a transport failure: index semantics vary by service. Without an index,
field freshness is unverified. Even an advancing index does not prove that every
individual BMS field is fresh. Stable voltage/SOC alone is not classified stale.

## Interpret the first fault

1. Compare system source identities with the intended battery service. The GX
   overview can retain V/A from another source when a battery monitor is absent;
   missing overview SOC alone does not prove partial CAN delivery.
2. If the actual battery service has invalid SOC but valid V/A, record partial
   telemetry. Correlate its service ownership, reported connection and transport
   evidence before assigning a cause.
3. If the battery service disappears or reports disconnected, compare CAN
   controller state/counter changes and an existing driver log at the same time.
   CAN RX traffic may belong to other devices; ERROR-ACTIVE is a normal state.
4. For battery1, distinguish a BlueZ link loss from a connected link whose
   battery values are invalid. `ServicesResolved` and RSSI are not payload-age
   measurements. An absent BlueZ object is unknown; a driver may use another
   Bluetooth implementation.
5. If both banks fail together, examine host/collector evidence before assuming
   two separate physical faults. Sampling can miss events between observations.

These comparisons narrow the investigation; no fault has been reproduced on
hardware and no root cause is established yet.

## Home Assistant later

Cerbo already handles battery1 Bluetooth, so first establish which per-battery
metrics Cerbo actually publishes. Home Assistant may add missing metrics later.
Do not assume a JK-BMS accepts simultaneous active Bluetooth clients. Decide
the Bluetooth owner after confirming the exact integration and model.

A later HA adapter should preserve original entity/device identities, units,
reported timestamps, unavailable/unknown states, and an explicit bank mapping.
Duplicate Cerbo/HA observations must be compared, not summed or used as silent
fallbacks. HA integration, continuous collection, Prometheus ingestion, storage
and alerts are not implemented by this finite capture tool. The native Grafana
shell is published, but it needs a reviewed exporter before panels populate. The existing
[Grid Grafana dashboard](GRID.md) remains separate and unchanged.

## Primary technical references

- [Victron GX source selection](https://www.victronenergy.com/media/pg/Cerbo_GX/en/configuration.html)
- [Victron systemcalc and fallback measurements](https://github.com/victronenergy/dbus-systemcalc-py/blob/master/dbus_systemcalc.py)
- [Victron D-Bus definitions](https://github.com/victronenergy/venus/wiki/dbus-api)
- [Victron GetItems implementation](https://github.com/victronenergy/velib_python/blob/master/vedbus.py)
- [Linux CAN state and statistics](https://docs.kernel.org/networking/can.html)
- [BlueZ device properties](https://github.com/bluez/bluez/blob/master/doc/org.bluez.Device.rst)
- [Home Assistant Bluetooth](https://www.home-assistant.io/integrations/bluetooth/)

Upstream definitions informed these tools; compatibility with the actual Venus
and JK-BMS driver versions remains a hardware acceptance task for the owner.
