# Connect the inverter to Cerbo GX

This guide describes the confirmed monitoring connection for the owner's
Anern inverter. It is not a universal pinout or an automatic installer. The
driver sends read-only PI30 queries; it does not send inverter setting commands.

The owner verifies all Cerbo and inverter settings and performs deployment.
See [owner access and deployment rules](OWNER-RULES.md) and [safety](../SAFETY.md).

## Confirmed arrangement

| Item | Confirmed value |
|---|---|
| Inverter interface | RS232 using PI30 |
| Serial format | 2400 baud, 8 data bits, no parity, 1 stop bit |
| USB adapter | `usb-FTDI_FT232R_USB_UART_BG041YD3-if00-port0` |
| Current kernel device | `/dev/ttyUSB0` |
| Driver | `/data/apps/dbus-anern-inverter2/dbus-anern.py` |
| Service | `/service/dbus-anern-inverter2` |
| D-Bus service | `com.victronenergy.inverter.anern2` |
| Device instance | 40 |

The adapter's persistent identity is `BG041YD3`. `/dev/ttyUSB0` is only its
current kernel name and can change when USB devices are added or reordered.

## 1. Connect the RS232 interface

Use an adapter designed for real RS232 voltage levels. A bare TTL UART adapter
is not equivalent. Verify isolation, connector orientation and pin numbering
for the actual hardware before energising it.

The working connection recorded for this specific inverter and connector
orientation is:

| Inverter contact | Function | Connect to adapter |
|---|---|---|
| Pin 1 | inverter TX | adapter RX |
| Pin 2 | inverter RX | adapter TX |
| Pin 8 | signal ground | adapter GND |

This record must not be copied to another model or connector without checking
its documentation and measuring the actual interface.

## 2. Confirm the adapter identity

Run on the Cerbo:

~~~sh
ls -l /dev/serial/by-id/
~~~

The confirmed adapter appears as:

~~~text
usb-FTDI_FT232R_USB_UART_BG041YD3-if00-port0 -> ../../ttyUSB0
~~~

The current repository source still searches for the historical serial
`BG03FXF0` and then falls back to `/dev/ttyUSB0`. The live driver therefore
works through that fallback. Do not rely on this when more serial devices are
connected. A future reviewed driver change should select `BG041YD3` explicitly
and fail clearly if it is absent.

## 3. Confirm the installed service

~~~sh
cat /service/dbus-anern-inverter2/run
svstat /service/dbus-anern-inverter2
dbus -y com.victronenergy.inverter.anern2 /Mgmt/Connection GetValue
dbus -y com.victronenergy.inverter.anern2 /Connected GetValue
~~~

The confirmed service command is:

~~~sh
exec python /data/apps/dbus-anern-inverter2/dbus-anern.py
~~~

On 15 September 2026, the running service reported `Connected = 1` and
`PI30 RS232 /dev/ttyUSB0`.

## 4. Check read-only telemetry

~~~sh
dbus -y com.victronenergy.inverter.anern2 /Ac/In/L1/V GetValue
dbus -y com.victronenergy.inverter.anern2 /Ac/In/L1/F GetValue
dbus -y com.victronenergy.inverter.anern2 /Ac/Out/L1/P GetValue
dbus -y com.victronenergy.inverter.anern2 /Ac/Out/L1/S GetValue
dbus -y com.victronenergy.inverter.anern2 /Pv/0/Power GetValue
dbus -y com.victronenergy.inverter.anern2 /Dc/0/Voltage GetValue
~~~

AC input V/Hz prove that the inverter reports input voltage and frequency.
They do not prove that a grid relay is closed or quantify imported power.
`/Ac/Out/L1/P` is inverter output power, not grid input power.

## Updating an existing installation

Do not replace a working driver merely to obtain a VRM Grid tile. The current
PI30 response has no verified grid-input current, power or energy field, and
the repository file already matches the installed file.

For a future reviewed driver update, use the backup, compare, restart and
rollback procedure in [operations](operations.md). Preserve `pv-yield.json` and
the existing supervisor/startup arrangement. Do not replace `/data/rc.local`
with a template.

## What this connection provides

The driver currently publishes inverter output, AC-input V/Hz, inverter-side
battery observations, internal PV observations, temperature and mode. See the
[path map](architecture.md). VRM Grid behaviour is tracked separately in
[VRM troubleshooting](GRID.md). Grafana work is kept in
[AC-input Grafana monitoring](GRAFANA.md).
