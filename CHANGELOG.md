# Changelog

## 2026-09-14 — relocation, English documentation and owner access rules

- Moved the complete local checkout/Git history to the cerbo project directory.
- Retained local captures and Word history in ignored private-notes/.
- Added primary English publication instructions and a separate Polish safety notice.
- Recorded mandatory owner review of every setting, owner-performed deployment,
  per-connection access approval and the prohibition on background Cerbo access.
- Preserved all source, tools, tests, service scripts and monitoring files.
- No Cerbo connection, deployment or runtime tests were performed in this update.

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
