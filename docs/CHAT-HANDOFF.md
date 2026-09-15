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

bat1 (628 Ah) belongs to inverter1, on a separate installation/phase from inverter2.
bat2a (280 Ah in the original topology) belongs to inverter2 and the two real SmartSolar 250/70 chargers.
The two banks must not be treated as one DC bank. Ask before assuming later parallel-battery changes.
Native CAN bat2a was the intended controlling BMS for the real SmartSolars.
The inverter also charges bat2a independently. This RS232 bridge does not coordinate charge limits.

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
Exact models, firmware, current ratings/capacities and service mappings are not
verified. The owner mentioned "600Amps"; do not reinterpret that as 600 Ah.

New offline-tested finite capture/report tools and an HTML dashboard are prepared;
read [POWER-DIAGNOSTICS.md](POWER-DIAGNOSTICS.md). The dashboard distinguishes
invalid SOC, missing service, observer errors and passive transport evidence.
System battery/voltage source selection is captured because overview V/A can
have a different source from SOC. No live fault or root cause is confirmed.

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
