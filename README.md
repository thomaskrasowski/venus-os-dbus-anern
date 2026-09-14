# Anern 6200 PI30 inverter monitoring for Venus OS

[Polish README](README.pl.md) · [Safety](SAFETY.md) · [History](docs/HISTORY.md) ·
[Operations](docs/operations.md) · [Source status](docs/SOURCE-STATUS.md)

An independent, experimental Python D-Bus integration for monitoring an
**Anern AN-SCI-EVO-6200 / 6200 W PI30 inverter** on **Victron Venus OS / Cerbo GX**.
It reads RS232 telemetry and publishes an inverter service for Venus OS consumers.
This is a community driver/add-on, not an official Victron or Anern plugin.

> **Electrical safety:** incorrect settings, wiring, software or measurements can
> contribute to fire, electric shock, overvoltage and equipment/battery damage.
> Every user must verify their installation and settings. Read [SAFETY.md](SAFETY.md).

## Status and compatibility

The owner reports successful monitoring after replacing the USB adapter.
The repository now includes the locally supplied file named
dbus-anern.running.py as its driver baseline; its hash is recorded in
[source status](docs/SOURCE-STATUS.md). It has not been compared with a fresh
live Cerbo capture in this session. This is an experimental source release,
not a newly hardware-tested deployment.

| Item | Evidence / limitation |
|---|---|
| Hardware | Owner-labelled Anern AN-SCI-EVO-6200, Cerbo GX MK2 |
| Protocol | PI30, RS232 2400 baud, 8N1; CRC16/XMODEM with reserved-byte adjustment |
| Runtime | Last reported Venus OS v3.79 Large / Python 3.12 |
| Queries | QID, QMN, QMOD, QPIGS; no setting commands |
| Other PI30 inverters | Compatibility must be verified; shared protocol does not prove identical fields |
| USB replacement | Reported working; new persistent by-id identity still needs verification |
| VRM | Custom paths are not automatically guaranteed to be recorded or graphed |

QMN reported VMII-NXPW5KW; that does not independently confirm the retail
model or the 6200 W rating.

## Measurements

- AC output voltage, frequency, real power and apparent power; current derived from VA/V.
- AC input voltage and frequency. **Grid current, real power and energy are not measured by this driver.**
- Inverter-side battery voltage, charge/discharge current and reported SOC in custom paths.
- Internal MPPT PV voltage/current/power, temperature, raw mode and local PV-energy estimates.

The driver publishes com.victronenergy.inverter.anern2, device instance 40.
Internal MPPT data is under /Pv/0/*. The experimental virtual Solar Charger
was removed after systemcalc/DVCC issues. Native BMS/SmartSolar services remain separate.

## Working installation locations

| Purpose | Path |
|---|---|
| Driver | /data/apps/dbus-anern-inverter2/dbus-anern.py |
| Supervisor | /service/dbus-anern-inverter2 |
| Log | /data/log/dbus-anern-inverter2/current |
| Local PV counters | /data/apps/dbus-anern-inverter2/pv-yield.json |

## Start here

1. Read the safety notice, [known issues](docs/known-issues.md) and source status.
2. Capture and compare the working driver and service files using [Operations](docs/operations.md).
3. Verify serial identity, pinout, isolation, phase/bank mapping and field interpretation.
4. Run offline checks before reviewing any installation change:

~~~sh
python -m unittest discover -s tests -v
python tools/inspect-source.py src/dbus-anern.py
~~~

The baseline still has a historical USB serial and a /dev/ttyUSB0 fallback.
It is not a portable multi-adapter installer. Do not copy it over a working
system without explicitly selecting and validating the intended adapter.
No automatic installer or device-control capability is supplied.

## Documentation

- [English architecture and path map](docs/architecture.md)
- [Polish introduction](README.pl.md)
- [Development history](docs/HISTORY.md) and [handover](docs/CHAT-HANDOFF.md)
- [Public GitHub publication steps](docs/PUBLISH.md) ([Polish translation](docs/PUBLISH.pl.md))
- [Owner access and deployment rules](docs/OWNER-RULES.md)
- [Contributing](CONTRIBUTING.md) and [security](SECURITY.md)

## License and names

[MIT License](LICENSE), Copyright © 2026 Thomas Krasowski.
See [third-party notices](THIRD-PARTY-NOTICES.md). Product names describe intended
compatibility only. This project is not affiliated with, endorsed by or certified
by Victron Energy, Anern or Voltronic Power.

## Grid observability

[Implementation and VRM investigation](docs/GRID.md): SSH/D-Bus probe,
external Prometheus exporter and [Grafana dashboard](monitoring/grafana-ac-input.json).
V/Hz and freshness have offline tests. Live collection, dashboard rendering
and VRM Grid ingestion are not yet verified.


## Owner-controlled deployment and access

The owner checks all Cerbo settings and performs all driver updates/deployment.
An assistant must ask for explicit permission before every proposed Cerbo
connection, including read-only SSH. Autonomous/background connections and
polling are prohibited. Existing monitoring scripts are optional owner-operated
tools, not authorization to execute them. See [owner rules](docs/OWNER-RULES.md).

The 2026-09-14 update changes organization and documentation only. The driver,
tools, tests, service scripts and monitoring definitions are unchanged.
