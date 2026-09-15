# Anern 6200 PI30 inverter monitoring for Venus OS

[Polish README](README.pl.md) · [Safety](SAFETY.md) ·
[Connect the inverter](docs/INVERTER-CONNECTION.md) ·
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
The repository includes the locally supplied file named dbus-anern.running.py
as its driver baseline; its hash is recorded in [source status](docs/SOURCE-STATUS.md).
On 15 September 2026 the owner downloaded the GitHub source on the Cerbo,
compiled it and compared it with the running file; `diff` reported no changes.
This remains an experimental source release, not a hardware-tested release.

| Item | Evidence / limitation |
|---|---|
| Hardware | Owner-labelled Anern AN-SCI-EVO-6200, Cerbo GX MK2 |
| Protocol | PI30, RS232 2400 baud, 8N1; CRC16/XMODEM with reserved-byte adjustment |
| Runtime | Last reported Venus OS v3.79 Large / Python 3.12 |
| Queries | QID, QMN, QMOD, QPIGS; no setting commands |
| Other PI30 inverters | Compatibility must be verified; shared protocol does not prove identical fields |
| USB replacement | `usb-FTDI_FT232R_USB_UART_BG041YD3-if00-port0`; currently reached through the ttyUSB0 fallback |
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
2. Follow [Connect the inverter](docs/INVERTER-CONNECTION.md) for the confirmed
   wiring record, adapter identity, service layout and read-only checks.
3. Capture and compare the working driver and service files using [Operations](docs/operations.md).
4. Verify serial identity, pinout, isolation, phase/bank mapping and field interpretation.
5. Run offline checks before reviewing any installation change:

~~~sh
python -m unittest discover -s tests -v
python tools/inspect-source.py src/dbus-anern.py
~~~

The baseline still has a historical USB serial and a /dev/ttyUSB0 fallback.
It is not a portable multi-adapter installer. Do not copy it over a working
system without explicitly selecting and validating the intended adapter.
No automatic installer or device-control capability is supplied.

## Documentation

- [Owner-confirmed installation topology](docs/TOPOLOGY.md)
- [English architecture and path map](docs/architecture.md)
- [Connect the inverter](docs/INVERTER-CONNECTION.md)
- [VRM Grid troubleshooting](docs/GRID.md)
- [AC-input Grafana monitoring](docs/GRAFANA.md)
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

## VRM and Grafana

[VRM Grid troubleshooting](docs/GRID.md) records the confirmed live results and
why the present PI30 data cannot supply Grid W/A/kWh. The driver already
publishes measured inverter output power, but that is not grid input power.

[AC-input Grafana monitoring](docs/GRAFANA.md) now contains the separate
Prometheus and V/Hz dashboard material. The broader power dashboard remains in
[Power diagnostics](docs/POWER-DIAGNOSTICS.md). Live AC-input collection and
dashboard rendering remain future work.


## Owner-controlled deployment and access

The owner checks all Cerbo settings and performs all driver updates/deployment.
An assistant must ask for explicit permission before every proposed Cerbo
connection, including read-only SSH. Autonomous/background connections and
polling are prohibited. Existing monitoring scripts are optional owner-operated
tools, not authorization to execute them. See [owner rules](docs/OWNER-RULES.md).

The relocation update changed organization and documentation only. Subsequent
local diagnostic additions are described below; the driver, existing tools and
service scripts remain unchanged.

## Power dashboard and battery stability diagnostics

[Read-only capture and dashboard guide](docs/POWER-DIAGNOSTICS.md): finite
owner-run Cerbo captures plus a self-contained offline dashboard for separate
battery sources, missing SOC, CAN statistics and Bluetooth connection evidence.
Home Assistant is reserved as a later additional source. Generate the synthetic
preview with `python tools/power_diagnostics.py --demo`.

The native [Grafana dashboard definition](monitoring/grafana-power-observatory.json)
has a historically imported scaffold in Minizon Grafana under `60 - Client Services`
as `Cerbo Power Observatory`. Cerbo-to-Grafana data integration and continuous
collection are not implemented. The existing battery1 Bluetooth integration
predates this repository work; no Cerbo runtime change or deployment has been
made during this work.

The finite [configuration snapshot](tools/cerbo_config_snapshot.py) helps the owner
collect the CAN driver, service, selected-battery and shared-sensing evidence
needed before considering a Bluetooth isolation test. Its
[run instructions](docs/POWER-DIAGNOSTICS.md) describe the report and privacy limits.

No Cerbo connection, installation or live hardware validation was performed.

The 2026-09-15 update records owner-supplied live evidence and reorganizes the
documentation. The driver, tools, service scripts and monitoring definitions
remain unchanged and nothing was deployed from this repository update.
