# Source status and provenance

Prepared on 2026-09-11 and updated from owner-run checks on 2026-09-15.
No deployment was performed as part of this repository update.

Latest owner-supplied configuration evidence (2026-09-15 20:55:51 UTC):
[CAN/BLE snapshot findings](CAN-BLE-SNAPSHOT-2026-09-15.md). The owner ran the
snapshot successfully; the assistant analyzed its local output without a Cerbo
connection. This does not establish healthy telemetry or a deployed fix.

| Item | Provenance and status |
|---|---|
| src/dbus-anern.py | Copied byte-for-byte from the owner's local file named dbus-anern.running.py |
| SHA-256 of supplied raw file | 77f248ea522884c76831b8338b7bacc4ea8281e31a293f3c409c22bf01806847 |
| Second local file, dbus-anern.py | Same bytes and SHA-256 |
| Live source comparison | On 2026-09-15 the owner downloaded the GitHub raw source on the Cerbo; Python compilation succeeded and `diff -u` against the running file produced no output |
| service/run | Owner output confirms it executes `/data/apps/dbus-anern-inverter2/dbus-anern.py` with Python |
| service/log/run | Conversation-derived template; not a fresh remote capture |
| Earlier package | Reconstructed compact driver; superseded by the supplied local file |
| Replacement USB adapter | `usb-FTDI_FT232R_USB_UART_BG041YD3-if00-port0 -> ../../ttyUSB0`; running driver reports `/dev/ttyUSB0` |
| Original Word document | Retained in owner's original local folder; not included in public repository |

The baseline retains the old `BG03FXF0` adapter selector and therefore reaches
the confirmed `BG041YD3` adapter through its `/dev/ttyUSB0` fallback. It also
retains static mode/metadata,
initial zeros, stale values after failed polls and variant-dependent PV parsing.
The absent /Yield/Power path is confirmed in the imported code; nearby historical
comments referring to it do not make it a registered path.

Git may normalize line endings as specified in .gitattributes. The raw hash above
identifies the supplied local file, not a guarantee of identical checkout bytes
under every Git configuration. No known-working release tag has been created.

Before deployment, capture current source and supervisor scripts, verify hashes
and adapter association and compare to this baseline. Replace the ttyUSB fallback
with an explicit reviewed adapter selection before relying on multiple serial
devices. Preserve private captures.
Before claiming a hardware-tested release, record installed commit/version,
target firmware, verified measurements and systemcalc/DVCC/VRM behavior.


## Relocation — 2026-09-14

The checkout and complete Git history were moved to
C:/Users/thoma/Documents/Codex/cerbo. Existing local source copies are retained
under ignored private-notes/current-scripts/, and the historical Word document
under ignored private-notes/archive/. work/ contains private preparation records.
outputs/ contains local guides and archives; none of these directories is published.

All moved file contents were hash-verified. No driver, tool, service, test or
monitoring-definition changes were made. No Cerbo connection was attempted.
The owner performs deployment and checks all settings; see OWNER-RULES.md.

## Read-only diagnostic preparation — 2026-09-14

New local tools `tools/cerbo_diagnostics.py`, `tools/power_diagnostics.py`,
`tools/power_dashboard.py` and `tools/power_demo.py` provide finite owner-run
capture and offline visualization. The new HTML template and mapping example
are in `monitoring/`. See [POWER-DIAGNOSTICS.md](POWER-DIAGNOSTICS.md).

These additions are authored offline, not copied from or validated against live
Cerbo software. The production driver, supervisor files and existing Grid
tools are unchanged. Demo readings are entirely synthetic. No Cerbo connection
or deployment occurred. Home Assistant collection remains future work.

The generated native Grafana definition was published to Minizon Grafana on
2026-09-14 as UID `cerbo-power-observatory` in `60 - Client Services` and read
back at version 1. This authorized Grafana API write did not access Cerbo.
Minizon Prometheus had no matching power-monitor/Cerbo/JK/Anern series, so the
live dashboard contains no real readings yet.

## CAN diagnostic follow-up — 2026-09-15

The owner supplied one local collector output that caught battery D-Bus absence
and an `ERROR-PASSIVE` `vecan1` interface with cumulative bus-off history. No
private raw capture is committed. The collector gained a compact, bounded,
passive CAN-only scope and structured controller-counter deltas; it still sends
no CAN frames and changes no target state. The production driver and service
files remain unchanged. No assistant connection to Cerbo or deployment occurred.

## Owner topology clarification and configuration snapshot — 2026-09-15

[TOPOLOGY.md](TOPOLOGY.md) records the owner's corrected physical mapping:
installation1 / Grid Phase1 uses battery1/inverter1 and a pre-existing
`dbus-serialbattery` / `Jkbms_Ble` integration. Installation2 / Grid Phase2 uses
battery2a + battery2b in parallel, JK master/slave communication over RS485-2,
and battery2a master CAN to Cerbo `vecan1`, with battery2b as slave. Aggregate
field semantics, current capacity and active DVCC source are not verified. Public documentation
uses a placeholder for the exact BLE service address; private captures retain it.

The owner confirms no Cerbo runtime configuration changes or deployment since
starting this local Codex/repository work. Owner-run diagnostic captures are
evidence, not a deployed monitoring integration. The historical Grafana-only
scaffold import above is unchanged; live Cerbo/Grafana data integration and
continuous collection are not implemented.
The owner reports that CAN and battery1 BLE were introduced together and the
dropouts began together; there is no pre-BLE CAN-only baseline. This does not
establish Bluetooth as the cause.

New `tools/cerbo_config_snapshot.py` is local preparation for an owner-run
configuration snapshot. It reads bounded, selected service/configuration,
package, host, transport and D-Bus evidence and writes JSON to stdout. It has
not been executed on Cerbo by the assistant. Its output is private and must not
be committed. See [POWER-DIAGNOSTICS.md](POWER-DIAGNOSTICS.md) for the command.

Supplied logs identify kernel `6.12.90-venus-4` and `can-bus-bms` v0.71. The
September 15 timeout near 08:36:24 follows a kernel IRQ event estimated near
08:36:18 from a clock conversion; that is not exact verified time alignment.
Later terminal `ERROR-PASSIVE` state and frozen counters do not date the exact
traffic stop. `vesmart-server` `0.5.14-r0` is installed but was absent from the supplied
process and service listings; `bluetoothd` was running. No hardware fix, current
firmware identity for the BMS, or Bluetooth/CAN cause has been established.

## Owner-run live verification — 2026-09-15

The supplied terminal output confirms Venus OS v3.79 build `20260826152305`,
an up driver with `/Connected = 1`, AC input around 234 V / 50 Hz, and the
adapter identity above. System paths `/Ac/Grid/L1/Power` and
`/Ac/Grid/L2/Power` returned unavailable values (`[]`), while
`/Ac/ActiveIn/Source` returned 240. No Grid, Multi or VE.Bus service appeared
in the supplied D-Bus service list.

These observations were made by the owner in an interactive SSH session and
pasted into the project conversation. The assistant did not connect to the
Cerbo. They establish the current driver/source match and the absence of a
system Grid-power source; they are not a deployment or a full hardware test.
