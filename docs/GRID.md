# Grid graphs: evidence, implementation and remaining work

## Implemented locally

- Read-only D-Bus probe over SSH: tools/grid_probe.py.
- Separate-host Prometheus exporter: tools/grid_exporter.py.
- Grafana import: monitoring/grafana-ac-input.json — V, Hz, D-Bus read health,
  source freshness and Prometheus scrape health.
- Scrape job for an existing Prometheus: monitoring/prometheus.yml.example.

These tools have offline tests, including an HTTP endpoint test. They are not
installed on the owner's servers and no live series have been verified.
They do not modify the driver, register D-Bus services, open the serial port,
change settings or restart Cerbo services.

## Why custom input paths do not establish VRM Grid

The driver parses QPIGS fields 0 and 1 as AC input V and Hz. It publishes
/Ac/In/L1/V and /Ac/In/L1/F on an inverter service. Its /Ac/L1/Power
and /Ac/Power are output power, not input/grid power. No verified input-current,
input-power or imported-energy field is used.

In upstream dbus-systemcalc-py inspected on 2026-09-11, the inverter-service
input list omits these custom AC-input paths. Grid aggregation uses a grid
meter or an appropriate inverter/charger input. This supports the diagnosis
that the custom V/Hz paths alone do not supply the system Grid graph.
This is not a fresh audit of the installed firmware or every VRM logging rule.

Do not copy output power into Grid power, derive it from unaligned battery/PV
readings, rename this service to VE.Bus/Multi or publish a fake grid meter.
A meter on one inverter feed is not necessarily a whole-property meter.
Confirm the measurement boundary and actual phase before integration.

## VRM next step

1. Capture firmware, input values, existing Grid/Multi/VE.Bus services,
   selected system source and input settings with the probe below.
2. Compare the installed SystemCalc input map and VRM logger mappings with
   available VRM Advanced widgets for that exact firmware version.
3. For V/Hz, establish whether VRM logs a supported inverter input field.
   A D-Bus path existing does not prove its ingestion by VRM.
4. For W/A/kWh, identify a correctly installed real AC meter or a documented,
   validated measurement from this exact inverter protocol variant.
5. Verify source, phase, sign, measurement boundary, loss of grid, timestamps
   and daily energy against independent measurements. Check existing
   BMS/DVCC/SmartSolar behavior after any approved integration change.

**VRM Grid is still unresolved.** The missing main Solar Charger tile is a
separate open issue. No unverified service-type change is supplied.

## Read-only diagnosis

Run from a workstation/monitoring host with an established SSH key/agent:

~~~sh
python tools/grid_probe.py --ssh-target root@CERBO_HOST --diagnostics
~~~

SSH host verification stays enabled. BatchMode cannot prompt for passwords.
Establish host trust and working SSH authentication interactively first.
The probe sends a fixed Python program on stdin, writes no target file and
uses only D-Bus reads. Keep output private; it may identify local topology.

For an existing password-only SSH session, run these commands inside that
interactive session instead:

~~~sh
cat /opt/victronenergy/version
dbus -y com.victronenergy.inverter.anern2 /Connected GetValue
dbus -y com.victronenergy.inverter.anern2 /Ac/In/L1/V GetValue
dbus -y com.victronenergy.inverter.anern2 /Ac/In/L1/F GetValue
dbus -y com.victronenergy.inverter.anern2 /Mgmt/Connection GetValue
dbus -y com.victronenergy.system /Ac/Grid/L1/Power GetValue
dbus -y com.victronenergy.system /Ac/Grid/L2/Power GetValue
dbus -y com.victronenergy.system /Ac/ActiveIn/Source GetValue
dbus -y
~~~

## Prometheus / Grafana setup

Use a separate monitoring host with Python 3.9+ and OpenSSH. Remote dbus-python
is already a dependency of the current Cerbo driver.

~~~sh
export CERBO_SSH_TARGET='root@CERBO_HOST'
python3 tools/grid_probe.py --ssh-target "$CERBO_SSH_TARGET"
python3 tools/grid_exporter.py
~~~

The exporter binds to 127.0.0.1:9786. Set --listen to an explicit private
interface if Prometheus is elsewhere. Keep the endpoint on the intended private
network; it has no authentication. No Grafana credential is needed by the exporter.

Merge the supplied job into the existing scrape_configs. Replace EXPORTER_HOST
with an address reachable from Prometheus. In a container, loopback is that
container, not the host. Validate the full configuration with the existing
promtool and use the deployment's normal reload procedure. Do not replace
an entire configuration with the example fragment.

Check in Prometheus:

~~~promql
up{job="anern-grid"}
anern_grid_sample_fresh{job="anern-grid"}
anern_ac_input_voltage_volts{job="anern-grid"}
anern_ac_input_frequency_hertz{job="anern-grid"}
~~~

The first two should be 1. V/Hz should match the inverter input. The exporter
waits for UpdateIndex to advance before releasing initial values. A failed,
disconnected or incoherent read invalidates telemetry. An unchanged index
expires after 35 seconds. Missing/nonfinite values are omitted, not zero.
Real measured zero is preserved.

UpdateIndex is an approximate freshness signal, wrapping every 256 successful
polls. Multi-path D-Bus reads are not atomic. Checking the index around reads
reduces inconsistencies but does not replace a timestamped driver snapshot.

In Grafana, select Dashboards → New → Import, upload the JSON and choose the
existing Prometheus datasource. UID anern-pi30-acinput is independent of database
dashboards; if it already exists, compare before overwriting. No alerts are defined.
The imported dashboard uses job anern-grid; keep the job name or edit its queries.

Live acceptance remains pending: compare readings and units, exercise communication
failure and valid zero, verify gaps/freshness/recovery and confirm time axes.
The exporter runs in the foreground. Add persistence only after the monitoring
host, account and configuration ownership are known. Prometheus stores the
time series; Grafana queries and displays them.

## Primary sources inspected on 2026-09-11

- [Victron D-Bus](https://github.com/victronenergy/venus/wiki/dbus)
- [SystemCalc source](https://github.com/victronenergy/dbus-systemcalc-py/blob/master/dbus_systemcalc.py)
- [AC input delegation](https://github.com/victronenergy/dbus-systemcalc-py/blob/master/delegates/acinput.py)
- [Prometheus exposition](https://prometheus.io/docs/instrumenting/exposition_formats/)
- [Grafana import](https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/import-dashboards/)

Upstream master may differ from the installed release. Source-derived findings
are technical inferences, not confirmation of remote VRM behavior.
