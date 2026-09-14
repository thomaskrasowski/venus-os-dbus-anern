# Development history

This is a curated technical history, not a verbatim chat export and not a claim
that every historical experiment worked. Original discussion:
[Improve JK BMS Monitoring](chatgpt-conversation://6a95570c-aaec-83ed-bcad-f7b5cba54244).
That application link is a private reference and may not open for other users;
all information needed for this project is summarized here.

## Initial development — before 10 September 2026

1. Investigated the owner's 6200 W inverter / JK BMS monitoring installation.
2. Identified PI30 communication at 2400 baud, 8N1, with CRC16/XMODEM and
   the PI30 reserved-checksum-byte adjustment. QPI reported PI30; QMN
   returned VMII-NXPW5KW.
3. Developed an RS232 query loop with CRC validation, NAK handling and retries.
4. Published a single inverter service, instance 40, including AC output,
   AC input V/Hz, inverter-side battery readings, internal MPPT and temperature.
5. Added local PV energy integration and persistent daily/total state.
6. Investigated a virtual Solar Charger for internal PV. A string firmware
   value caused a numeric type failure in systemcalc/DVCC, and charger
   current accounting raised additional concerns. The virtual service was removed.
7. Removed inverter /Yield/Power as a diagnostic change. Internal PV remains
   in /Pv/0/*; inclusion in official system/VRM PV totals was not established.
8. Investigated the missing main VRM Solar Charger tile. SmartSolar data was
   still available in Advanced. Browser/Beta/driver-removal experiments did
   not establish a cause or fix.
9. Corrected an earlier statement about Grafana: its installation must be
   checked separately; it was not demonstrated as running on the Cerbo.

## 10 September 2026

Prepared a four-page Word summary of the protocol, wiring discussion, paths,
service operations, troubleshooting and remaining work. The original remains
in the owner's local archive. Current Markdown documentation qualifies older
claims about USB identity, generic pinouts, firmware identity and VRM accounting.

## 11 September 2026 — repository preparation

- Owner reported that a replacement USB adapter worked immediately.
- Earlier repository package contained reconstructed source, tooling and 11
  offline tests; those results were not a new hardware validation.
- Located the owner's local dbus-anern.running.py and imported it as the
  source baseline. Recorded SHA-256 and remaining provenance limitations.
- Selected MIT for original project material; added English/Polish safety
  and non-affiliation notices and English/Polish READMEs.
- Prepared public GitHub instructions for thomaskrasowski/venus-os-dbus-anern.
- Requested the next improvement: Grid graphs in both VRM and Grafana.
  Source inspection confirms input V/Hz, without validated input W/A/kWh.

## Open work

Fresh target capture and USB mapping; accurate Grid measurement/topology and
verified VRM ingestion; Grafana collection; stale-data handling; PV field
validation; missing main VRM PV tile. Completed code work and live validation
must be recorded separately in CHANGELOG.md.

## 11 September 2026 — Grid observability code

Implemented external SSH/D-Bus reader, Prometheus exporter and Grafana V/Hz
dashboard with freshness handling and tests. Live collection and VRM Grid
resolution are pending; no input-power measurement has been invented.


## 14 September 2026 — project organization and owner workflow

Moved the checkout and Git history to C:/Users/thoma/Documents/Codex/cerbo.
Preserved the local source copies and historical Word file under private-notes/.
The repository uses English names and primary documentation; Polish is additional.
The owner is testing the baseline and did not request code changes.

The owner personally checks all Cerbo settings and performs deployment.
Each proposed Cerbo connection requires a fresh explicit access prompt, even if
read-only. Autonomous/background connections are prohibited. These preferences
are persisted in AGENTS.md and OWNER-RULES.md.
