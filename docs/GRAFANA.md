# AC-input Grafana monitoring

Grafana work is separate from the Cerbo driver and from VRM Grid integration.
Further deployment instructions will be completed when the monitoring host,
Prometheus ownership and network path are chosen.

This file covers only the experimental AC-input V/Hz dashboard. The separate
`Cerbo Power Observatory` battery/CAN dashboard and its historical Grafana
import are documented in [Power diagnostics](POWER-DIAGNOSTICS.md).

## Prepared locally

- `tools/grid_probe.py` reads the driver's AC-input V/Hz paths over SSH.
- `tools/grid_exporter.py` exposes those readings and freshness state to Prometheus.
- `monitoring/prometheus.yml.example` is a scrape-job fragment.
- `monitoring/grafana-ac-input.json` is a six-panel dashboard for V, Hz,
  D-Bus read health, source freshness and Prometheus scrape health.

These components have offline tests. They have not been installed on the
owner's servers and no live series or rendered dashboard has been verified.
They do not provide grid W/A/kWh.

## Current reference workflow

Use a separate monitoring host with Python 3.9+ and OpenSSH:

~~~sh
export CERBO_SSH_TARGET='root@CERBO_HOST'
python3 tools/grid_probe.py --ssh-target "$CERBO_SSH_TARGET"
python3 tools/grid_exporter.py
~~~

The exporter binds to `127.0.0.1:9786`. If Prometheus runs elsewhere, choose
an explicit private listening address and protect the endpoint; it has no
authentication. In a container, loopback refers to that container.

Merge the supplied job into the existing `scrape_configs`; do not replace a
complete Prometheus configuration with the example. Validate the resulting
configuration with that deployment's `promtool` and normal reload procedure.

Reference queries:

~~~promql
up{job="anern-grid"}
anern_grid_sample_fresh{job="anern-grid"}
anern_ac_input_voltage_volts{job="anern-grid"}
anern_ac_input_frequency_hertz{job="anern-grid"}
~~~

The first two should be 1. Unknown, disconnected, incoherent, non-finite or
stale readings are omitted instead of being converted to zero. The exporter
requires `UpdateIndex` to advance before releasing initial telemetry and marks
unchanged data stale after 35 seconds.

The dashboard can later be imported through Grafana's dashboard import page.
Its UID is `anern-pi30-acinput` and its queries expect job `anern-grid`.
Compare before overwriting an existing dashboard with the same UID.

## Work deliberately left for later

- Choose the monitoring host and service account.
- Decide how the exporter should run persistently.
- Configure the real Prometheus deployment and network access.
- Import and render the dashboard.
- Validate values, gaps, failure recovery and time axes against live readings.

Grafana stores and displays these diagnostic time series independently of VRM.
See [VRM troubleshooting](GRID.md) for the separate Grid-tile question.
