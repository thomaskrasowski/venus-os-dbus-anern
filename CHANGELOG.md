# Changelog

## 2026-09-11 — public repository preparation

- Imported the owner's local driver file; recorded source hash and provenance limits.
- Added MIT, third-party notices, English/Polish README and safety notice.
- Added curated development history and public GitHub publication guide.
- Adapted source checks to the supplied driver layout.
- No remote deployment, service restart or GitHub publication performed by this change.

## 2026-09-11 — Grid observability implementation

- Added SSH/D-Bus snapshot and topology diagnostics.
- Added external Prometheus V/Hz exporter with freshness gating.
- Added Grafana JSON and Prometheus scrape-job example.
- Added tests for stale/disconnected/invalid/zero readings, index wrap,
  SSH input validation, transport failure and HTTP exposition.
- Driver and target configuration are unchanged by this feature.
- Live deployment, graph rendering and VRM Grid remain unverified.
