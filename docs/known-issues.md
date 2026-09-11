# Known issues and release gates

This repository records limitations instead of hiding them behind a working dashboard.

## P0 - capture exact deployed source / adapter

The owner reports a working system after USB replacement. The local running-file import is recorded,
but fresh remote provenance is unverified. Before any
new installation, export and compare the real files. The old serial + ttyUSB0 fallback must not be
used to identify two or three independent devices. Avoid multiple readers/probers on one serial port.

## P0 - control/systemcalc safety

Earlier virtual Solar Charger work caused a numeric firmware type error in DVCC/systemcalc.
Dropping writeable paths did not establish total independence from its charger accounting.
The virtual service is removed. Never fake a Victron product or version to claim charger capability.
Do not change charge limits while troubleshooting a UI component.

## P1 - PV dashboard missing / statistics unverified

The original SmartSolars remained in D-Bus/VRM Advanced, while the main PV Charger tile disappeared.
Removing the virtual service, removing `/Yield/Power`, stopping the bridge, browser cleanup and Beta
comparison did not establish the cause. Successful logging is not proof every custom path is ingested.
The final reference has no inverter `/Yield/Power`; do not claim full PV accounting remains enabled.
No fix or authoritative VRM outage was confirmed.

## P1 - incomplete inverter topology and state

The source is an inverter-only abstraction of an inverter/charger. Grid V/Hz are available, grid W/A are not.
`/Mode=2` is a static placeholder, not a truthful mapping of every QMOD state. Full active-input topology
is missing. The path `L1` is local to the single-phase device and must not be confused with the household
phase L2 feeding inverter2. Do not 'fix' a grid tile by inventing input power or faking VE.Bus.

## P1 - telemetry validity

On failed polls `/Connected` becomes 0 but last telemetry stays populated. Initial unknown values are zero.
Consumers and diagnostics need an explicit stale-data policy. CRC-valid frames still need field/range
validation. AC output I is derived from VA/V. Inverter-reported charge current is not total battery charge
including the external MPPTs. QPIGS field-12 interpretation and zero-PV V*I fallback are variant-dependent.

## P2 - local energy estimates

The current rectangle-rule integration is not an inverter lifetime counter. Gaps >30 seconds are excluded;
shorter failures can still distort estimates. Saving is periodic (~60 seconds). Corrupt state currently
resets silently; normal SIGTERM cleanup is not explicitly installed. Daily rollover follows the process
clock (observed UTC), not necessarily the owner's local calendar, and multi-day gaps are simplistic.
Preserve existing state privately; do not commit a live `pv-yield.json`.

## P2 - process / port / dependency hardening

Serial IO and retries block the GLib event loop; opening/flushing may discard late frames.
Partial writes, serial exclusivity and reconnection identity need review. Recursive first-match loading of
`vedbus.py` is nondeterministic when multiple bundled versions exist. Firmware metadata is a model string
on the inverter, retained for fidelity, and should be model metadata in a future reviewed revision.
No new firmware/dependency compatibility has been tested by packaging this repository.

## Historical advice not to treat as proven

Read-only publication does not guarantee no effects on system calculations. Zero battery current/full SOC
was not a proven cause of a missing tile. Removing a VRM device is not known to reset topology or preserve
all history. A successful adapter loopback does not establish correct voltage levels/pin numbering.
One non-isolated USB adapter is not automatically safe merely because only one inverter is being tested.
