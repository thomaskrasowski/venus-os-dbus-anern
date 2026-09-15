# VRM Grid troubleshooting

This document records why the current driver does not populate the VRM Grid
tile and what evidence is still needed. Grafana has a separate
[monitoring document](GRAFANA.md).

The owner verifies every Cerbo setting and performs deployment. Assistants must
ask and wait for explicit approval before every Cerbo connection. See
[owner access and deployment rules](OWNER-RULES.md).

## Confirmed live state — 15 September 2026

The owner ran the checks on the Cerbo and supplied the terminal output:

| Check | Result |
|---|---|
| Venus OS | v3.79, build `20260826152305` |
| Driver status | up; `/Connected = 1` |
| Installed source | no differences from the GitHub `src/dbus-anern.py` candidate |
| AC input | approximately 234 V / 50 Hz |
| Driver connection | `PI30 RS232 /dev/ttyUSB0` |
| `/Ac/Grid/L1/Power` | unavailable (`[]`) |
| `/Ac/Grid/L2/Power` | unavailable (`[]`) |
| `/Ac/ActiveIn/Source` | 240, meaning no active system AC input |
| Grid/Multi/VE.Bus service | none present in the supplied D-Bus service list |

The list did contain `com.victronenergy.shelly` and
`com.victronenergy.fronius`. Their presence alone does not identify a Grid
meter or its electrical boundary; their devices and paths can be checked during
the later VRM investigation.

The USB adapter is now identified as
`usb-FTDI_FT232R_USB_UART_BG041YD3-if00-port0`. The installed driver is using
the `/dev/ttyUSB0` fallback because its source still contains the old serial
`BG03FXF0`.

## Why replacing the script will not create VRM Grid power

The current QPIGS response provides measured AC-input voltage and frequency,
then AC-output voltage, frequency, apparent power and active power. It does not
provide verified AC-input current, active power or imported energy.

The driver therefore publishes:

- `/Ac/In/L1/V` and `/Ac/In/L1/F`: input voltage and frequency;
- `/Ac/Out/L1/P`: measured inverter output active power;
- `/Ac/Out/L1/S`: measured inverter output apparent power.

The output values cannot be relabelled as grid import. Loads may be supplied by
grid bypass, battery, PV or a mixture, and charging plus conversion losses are
not represented by output power alone.

Victron SystemCalc monitors output paths for a
`com.victronenergy.inverter` service. Its supported AC-input power/current paths
belong to inverter/charger service types such as `com.victronenergy.multi`, or
to a real `com.victronenergy.grid` meter. The driver's custom `/Ac/In/L1/V` and
`/Ac/In/L1/F` paths therefore do not establish a system Grid source.

Changing the service type, copying output watts into a Grid path or publishing
a fake meter would create misleading energy accounting and can affect system
calculations. No such driver change is proposed.

## What may already be visible in VRM

The driver already publishes standard inverter-output paths. VRM device or
Advanced views may expose some of the following, depending on the installed
logger mapping:

- inverter output voltage and current;
- inverter output active power;
- inverter DC voltage;
- connected state and identity.

Custom battery, internal-PV and AC-input paths are not guaranteed to be logged
merely because they exist on D-Bus. A local D-Bus value and a VRM graph are two
separate facts.

Read the current local values with:

~~~sh
dbus -y com.victronenergy.inverter.anern2 /Ac/Out/L1/V GetValue
dbus -y com.victronenergy.inverter.anern2 /Ac/Out/L1/I GetValue
dbus -y com.victronenergy.inverter.anern2 /Ac/Out/L1/P GetValue
dbus -y com.victronenergy.inverter.anern2 /Ac/Out/L1/S GetValue
dbus -y com.victronenergy.inverter.anern2 /Dc/0/Voltage GetValue
dbus -y com.victronenergy.inverter.anern2 /Connected GetValue
~~~

These checks identify available source data. They do not prove VRM ingestion.

## Valid ways to obtain VRM Grid power

VRM Grid W/A/kWh needs a measured value at the intended electrical boundary.
The viable routes are:

1. a correctly installed and configured supported AC grid meter; or
2. a separately verified command from this exact inverter/protocol variant that
   reports AC-input current or power with defined units, sign and timing.

Before integration, verify phase assignment, direction/sign, measurement
boundary, loss-of-grid behaviour, timestamps and energy accumulation against an
independent measurement. A meter on this inverter feed may still not represent
the whole property.

## Read-only follow-up checks

The existing probe can capture topology and supported values after separate
access approval:

~~~sh
python tools/grid_probe.py --ssh-target root@CERBO_HOST --diagnostics
~~~

For an already open owner-operated SSH session:

~~~sh
dbus -y com.victronenergy.inverter.anern2 /Connected GetValue
dbus -y com.victronenergy.inverter.anern2 /Ac/In/L1/V GetValue
dbus -y com.victronenergy.inverter.anern2 /Ac/In/L1/F GetValue
dbus -y com.victronenergy.inverter.anern2 /Ac/Out/L1/P GetValue
dbus -y com.victronenergy.system /Ac/Grid/L1/Power GetValue
dbus -y com.victronenergy.system /Ac/ActiveIn/Source GetValue
dbus -y
~~~

VRM Grid remains unresolved. The missing main Solar Charger tile is a separate
open issue.

## Technical sources inspected

- [Victron D-Bus path documentation](https://github.com/victronenergy/venus/wiki/dbus)
- [Victron SystemCalc source](https://github.com/victronenergy/dbus-systemcalc-py/blob/master/dbus_systemcalc.py)
- [Victron AC-input implementation](https://github.com/victronenergy/dbus-systemcalc-py/blob/master/delegates/acinput.py)
- [Representative PI30 protocol document](https://www.smartphoton.ch/wp-content/uploads/2021/12/pip-gk-mk-protocol.pdf)

The PI30 document describes a related protocol family and is not proof that
every field or optional command behaves identically on this inverter. Upstream
Victron master may also differ from the installed v3.79 build.
