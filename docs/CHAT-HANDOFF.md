# ChatGPT / Codex project handover

This is a curated handover, **not a complete chat export**. Read `SOURCE-STATUS.md` before editing.

## Objective

Maintain a read-only PI30 -> Venus D-Bus bridge for a 6200 W third-party inverter on a Cerbo GX MK2.
Develop in Git, test offline, then make explicitly approved, reversible changes to the live GX.

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
Verify live source/USB mapping and AC input capabilities. Do not deploy, restart,
change DVCC/BMS limits or publish a virtual Solar Charger as part of repository preparation.

Grid tools now exist in tools/grid_probe.py and tools/grid_exporter.py;
monitoring/ contains Grafana JSON and a scrape example. Read GRID.md.
Live values, target mapping, SSH access, monitoring-host configuration
and VRM ingestion still need verification. Preserve the production driver.
