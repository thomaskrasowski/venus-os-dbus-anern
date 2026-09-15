# Validation — 2026-09-11

22 offline tests passed on Windows with Python 3.13.7:

- 11 existing source/CRC/tooling checks adapted to the supplied driver layout.
- 11 Grid behavioral checks, including a real loopback HTTP /metrics request.
- The fixed remote Python program compiles without execution.
- Both supervisor scripts passed shell syntax checks.
- Local Markdown links resolve. The six-panel Grafana JSON has unique IDs,
  valid grid bounds, no overlapping panels and no gap-filling configuration.

The driver's query allowlist remains QID/QMN/QMOD/QPIGS. No virtual Solar
Charger or control path was added. Source bytes remain the imported baseline.
The exporter uses only the Python standard library on its host.

Grafana JSON was structurally inspected. No authenticated import, rendered
dashboard, live metrics or Prometheus server configuration change occurred.
Cerbo SSH responded but unattended authentication failed.

No Cerbo deployment, restart, BMS/DVCC change or hardware test occurred.
VRM Grid and the main Solar Charger tile remain unresolved.


## 2026-09-14 — relocation/documentation validation

All moved files were compared to their pre-move SHA-256 values.
Runtime source, tooling, service scripts, tests and monitoring definitions are
unchanged. Documentation links, English path names and ignored local folders
were checked. No new runtime test suite was needed for the documentation changes.
No Cerbo, SSH or other energy-device connection was attempted.
The earlier 22-test result remains historical, not a fresh hardware validation.

## 2026-09-14 — power diagnostics and offline dashboard

93 offline tests passed with the bundled Python interpreter:

- 22 existing driver CRC/framing, source, Grid and tooling checks.
- 20 passive collector checks with fake D-Bus, command runners and sysfs files.
- 44 analysis checks for invalid/missing/zero data, discovery errors, service
  continuity, clock/session boundaries, source-specific Grid/inverter paths,
  CAN/Bluetooth events and owner-verification failures.
- 3 dashboard checks for safe embedded JSON, non-finite data rejection and
  explicit synthetic demo scenarios.
- 4 native Grafana checks for layout, data gaps, bank separation, Grid source
  integrity and explicit transport mapping.

The synthetic 37-observation report was generated end to end and inspected in
the in-app browser. Source cards, SOC gaps, incident filtering, transport sample
selection and measurement-quality panels rendered. Browser console inspection
reported no errors or warnings. The temporary preview used loopback only.
`git diff --check` passed. New collector `--help` runs without dbus-python.

Production source, service scripts and existing Grid tools/definitions are
unchanged. No Cerbo/HA connection, hardware test, live CAN/Bluetooth test,
driver update, deployment or VRM change occurred. Diagnostic compatibility and
source-to-bank mappings still need owner-supplied evidence.

The native dashboard was published through the authorized Minizon Grafana API
and read back. UID, title, folder, datasource variable, 28 panels, 31 targets
and version 1 matched; dashboard search returned one result. A query inspection
found no battery aggregation or inferred Grid-power expression. All 31 unique
panel expressions parsed successfully through the live Prometheus API. Prometheus
had no matching live power-monitor/Cerbo/JK/Anern series, so no live values or
panel behavior were hardware-validated. Grafana's optional image-render endpoint
reported that the renderer plugin is not installed; API read-back verification
did not depend on it.

## 2026-09-15 — CAN diagnostic follow-up

The full offline suite now has 99 passing tests, including 25 collector tests.
New cases verify the
exact SocketCAN controller-counter header mapping, compact selected-interface
output, explicit unknown status for a missing interface, counter deltas/resets,
state transitions, CAN-only report compatibility, and CLI operation without
importing D-Bus. The bulk
`GetItems` timeout test verifies one device-level error instead of duplicated
per-path errors. Python compilation and `git diff --check` passed.

The owner-supplied sample was analyzed locally; its raw text was not added to
the repository. No Cerbo connection, CAN socket, live hardware test, deployment,
setting change, service restart or continuous process occurred.

## 2026-09-15 — topology and configuration snapshot

The full offline suite passed all 124 tests with the bundled Python interpreter,
including 25 new configuration-snapshot tests. These verify fixed read-only
command and D-Bus scope, individually allowlisted settings, private configuration
filtering, bounded file/subprocess output, command and D-Bus worker timeouts,
owned-child cleanup on interruption, and explicit incomplete/unknown evidence.
The hung-worker test exercises the parent's deadline without a live D-Bus daemon.

All 45 local Markdown links checked across the updated documentation resolved.
The example mapping JSON parsed successfully; the exact BLE identifier remains
in ignored private mapping data. Public changes were checked for the owner's
BLE address and raw logs. `git diff --check` passed.

The production driver, existing collectors, service scripts and Grafana
definitions are unchanged. No Cerbo connection, live CAN/Bluetooth/D-Bus test,
setting change, restart or deployment occurred. The owner must review and run
the snapshot to establish target compatibility and provide current evidence.

## 2026-09-15 — supplied snapshot analysis and sysfs correction

All 127 offline tests passed, including three new cases for nominal sysfs size
versus actual content, genuine head/tail truncation, and the global byte limit.
Updated local documentation links resolve and `git diff --check` passed.
The owner supplied a completed 2.45-second snapshot; it exposed a false
truncation flag on complete sysfs counter values. The flag is corrected locally.
No assistant Cerbo access, service action, settings change or deployment took
place. The new correction has not been tested on hardware.
