# ChatGPT / Codex project handover

This is a curated handover, **not a complete chat export**. Read `SOURCE-STATUS.md` before editing.

## Objective

Maintain a read-only PI30 -> Venus D-Bus bridge for a 6200 W third-party inverter on a Cerbo GX MK2.
Develop locally when requested. The owner tests, checks all settings and performs live deployment.

## Last confirmed installation facts

- Last reported Venus OS: v3.79 Large; Python 3.12; BusyBox command-line utilities.
- Protocol demonstrated: PI30, 2400 baud, 8N1; CRC16/XMODEM with reserved CRC-byte adjustment.
- QPI identified PI30; QMN reported `VMII-NXPW5KW`. Product label in our software is
  `Anern AN-SCI-EVO-6200`, but QMN alone is not an exact retail-model or rated-power confirmation.
- Driver: `/data/apps/dbus-anern-inverter2/dbus-anern.py`.
- Service: `/service/dbus-anern-inverter2`; logs: `/data/log/dbus-anern-inverter2/current`.
- D-Bus name: `com.victronenergy.inverter.anern2`; instance 40; custom name `inverter2`.
- Local PV counter: `/data/apps/dbus-anern-inverter2/pv-yield.json`.
- The owner now reports that the USB adapter was replaced and works immediately.
  The new USB identity is not in the supplied evidence. OLD adapter serial: BG03FXF0.

## Electrical / control separation

The owner's 2026-09-15 clarification supersedes the older single-pack description:

- Installation1 / Grid Phase1: battery1 and inverter1. Existing
  `dbus-serialbattery` / `Jkbms_Ble` provides the JK-BMS Bluetooth integration.
- Installation2 / Grid Phase2: battery2a + battery2b in parallel on the DC side,
  with inverter2. JK master/slave communication uses RS485-2; battery2a is the
  CAN master on Cerbo `vecan1`, service `com.victronenergy.battery.socketcan_vecan1`,
  and battery2b is the slave.

Do not combine the two installations. Current capacities and which CAN fields
describe a pack versus the parallel bank are
not verified. The two SmartSolar 250/70 chargers belong to installation2 in
earlier owner context and report `socketcan_vecan0` in supplied captures.
Current DVCC selection remains pending. This RS232 bridge does not coordinate
charge limits. See [TOPOLOGY.md](TOPOLOGY.md); exact BLE addresses stay private.

## Latest source state represented here

One inverter service only. Internal PV is `/Pv/0/Voltage`, `/Pv/0/Current`, `/Pv/0/Power`.
No virtual `solarcharger.anern2pv`. No top-level `/Soc` or DVCC `/Link/*` controls.
`/Yield/Power` was removed in the last diagnostic patch. The counters under `/Yield/User`,
`/Yield/System` and `/History/Daily/*` remain local estimates, not guaranteed VRM statistics.
The current file on the Cerbo may differ. Export it before replacing anything.

## What was tried and must not be repeated blindly

1. A second virtual solarcharger required a private D-Bus connection to avoid object-path `/` collisions.
2. String FirmwareVersion on that service crashed systemcalc/DVCC (`str & int`).
3. Fake DC-side charger current can affect DVCC. Zeroing it gives an inconsistent charger model.
4. Spoofing a Victron product/firmware ID did not restore the PV tile.
5. Removing the virtual charger, removing inverter `/Yield/Power`, stopping the bridge,
   deleting stale VRM entries, refreshing, incognito and VRM Beta did not establish a fix.
6. Original SmartSolar data remained visible in VRM Advanced. Logger showed their discovery and a successful post.
7. `serial-starter`/other drivers have grabbed the same USB serial adapter. Check ownership, never race readers.
8. BusyBox `ps -fp` and `head -30` were not supported; use `ps` and `head -n 30`.
9. A previous assertion that Venus OS Large includes Grafana was corrected. Do not assume Grafana is installed.

## Current next step

The owner supplied a local file named dbus-anern.running.py; it now replaces the
reconstruction in src/. See SOURCE-STATUS.md for the hash and remaining limitations.
The owner chose public GitHub publication with MIT, English/Polish documentation,
and Grid graphs in both VRM and Grafana.
Prefer owner-supplied local captures. Ask before every proposed Cerbo connection.
Never connect in the background. Do not deploy, restart,
change DVCC/BMS limits or publish a virtual Solar Charger as part of repository preparation.

Grid tools now exist in tools/grid_probe.py and tools/grid_exporter.py;
monitoring/ contains Grafana JSON and a scrape example. Read GRID.md.
Live values, target mapping, SSH access, monitoring-host configuration
and VRM ingestion still need verification. Preserve the production driver.


## Current working boundary — 2026-09-14

The project is now at C:/Users/thoma/Documents/Codex/cerbo, with .git at its root.
All repository names and primary documentation are English. Polish remains
supplementary. Read AGENTS.md and OWNER-RULES.md before doing any work.
The owner handles deployment and must check every Cerbo setting. Every proposed
connection requires a fresh prompt and explicit answer; background access is
prohibited. No runtime code changes are requested while the owner tests.

GitHub target: thomaskrasowski/venus-os-dbus-anern. Follow PUBLISH.md.
The optional Grid tools remain unmodified and must not be launched by assistants.

## Power diagnostics work — 2026-09-14

The owner requested a new power dashboard and advanced read-only diagnostics.
Both batteries are described as JK-BMS; battery1 Bluetooth is currently handled
by Cerbo GX, and battery2 CAN intermittently loses SOC while V/A remain visible.
At this stage exact models, firmware, ratings/capacities and service mappings
were not verified. The owner mentioned "600Amps"; do not reinterpret that as
600 Ah. See the later topology clarification for the current mapping.

New offline-tested finite capture/report tools and an HTML dashboard are prepared;
read [POWER-DIAGNOSTICS.md](POWER-DIAGNOSTICS.md). The dashboard distinguishes
invalid SOC, missing service, observer errors and passive transport evidence.
System battery/voltage source selection is captured because overview V/A can
have a different source from SOC. At that stage no live fault or root cause
had been confirmed; the later owner-supplied captures below show CAN faults.

Next input: owner-run service/version/source-selection output, then a short
capture during a failure and exact service-to-bank mapping. Home Assistant is
planned as an additional source; no second Bluetooth client is configured.
Driver baseline and existing monitoring tools remain unchanged. No live access,
deployment, settings changes or hardware test occurred. VRM missing PV tile
and Grid ingestion remain open.

On the owner's next request, the native `Cerbo Power Observatory` dashboard was
published via the saved Minizon Grafana service account into `60 - Client
Services`, UID `cerbo-power-observatory`, and read back at version 1. This was a
Grafana-only connection. The Prometheus datasource returned zero matching
Cerbo/JK/Anern/power-monitor metric names, so the dashboard is a truthful empty
shell pending a separately reviewed continuous exporter. No Cerbo connection
or background polling was started.

## First CAN fault evidence — 2026-09-15

The owner ran `cerbo_diagnostics.py --samples 1` and supplied the output. The
sample caught no `com.victronenergy.battery.*` service. System battery service,
auto/active selection and SOC were invalid, while voltage/current remained
visible. The voltage source explicitly named inverter2; the source of the
current was not established. This is battery service absence with fallback
voltage, not proof of a BMS service publishing only some fields.

`vecan1` was `ERROR-PASSIVE`; cumulative history showed 19 restarts, 52
error-warning transitions, 67 error-passive transitions and 19 bus-off events.
`vecan0` was `ERROR-ACTIVE` with zero such history, and both detected SmartSolar
services named `socketcan_vecan0`. Later owner clarification identifies `vecan1`
as the installation2 JK master CAN connection. The first sample alone cannot
date the counter increments or identify cable, termination, power, BMS,
transceiver, adapter or noise as the cause.

The focused next owner-run command is documented in POWER-DIAGNOSTICS.md. The
collector now supports finite `--scope can --interface vecan1` sampling and
within-session deltas, and no longer duplicates one bulk D-Bus `NoReply` across
every allowlisted path. This work was prepared and tested offline. No Cerbo
connection, deployment, setting change, service action or hardware test was
performed by the assistant.

## Topology and configuration evidence — 2026-09-15

The owner confirms no Cerbo runtime configuration changes or deployment since
starting local Codex/repository work. The battery1 BLE integration was already
present. The historical Grafana-only scaffold import remains recorded above;
Cerbo/Grafana data integration and a deployed continuous collector do not exist.
The owner reports CAN and battery1 BLE were implemented together, with dropouts
starting together. There is no pre-BLE CAN-only baseline. This temporal
association does not establish that BLE caused the CAN fault.

Supplied evidence reports kernel `6.12.90-venus-4`, native `can-bus-bms` v0.71,
and a BMS timeout followed by D-Bus disconnection at about 08:36:24 on September
15. A kernel IRQ message maps to approximately 08:36:18 using the supplied
clock anchor; that conversion is an estimate, not a verified exact timestamp.
Later `ERROR-PASSIVE` state and frozen counters do not identify the exact stop
instant or prove the cause. The daemon remained running after the timeout.

`vesmart-server` package `0.5.14-r0` is installed, but no corresponding process or
`/service` entry appeared in the supplied listings. Installation is not evidence
that it was running. `bluetoothd` was running. `dbus-blebattery.0` is a likely
battery1 supervisor association; its run configuration and status still need
checking. These facts do not prove a Bluetooth/CAN causal link.

The next owner-operated evidence step is the local, read-only
`tools/cerbo_config_snapshot.py` described in [POWER-DIAGNOSTICS.md](POWER-DIAGNOSTICS.md).
It records selected configuration and service state; no changes, restarts,
connections or deployment were performed by the assistant. Current DVCC source
selection and the master/slave CAN field semantics remain open.
