# USB replacement and multi-adapter mapping

## Owner rules, effective 2026-09-14

The owner verifies every Cerbo setting and performs all deployment.
Assistants must ask and wait for explicit approval before EACH Cerbo connection,
including read-only SSH/SCP/SFTP. Never connect autonomously or in the background.
Existing exporters and diagnostic tools must not be launched by assistants.
The commands below are reference instructions for owner-operated work.
See [OWNER-RULES.md](OWNER-RULES.md).

## Confirmed adapter vs current source

On 2026-09-15 the owner supplied this live mapping:

~~~text
usb-FTDI_FT232R_USB_UART_BG041YD3-if00-port0 -> ../../ttyUSB0
~~~

The replacement adapter serial is therefore `BG041YD3`. The OLD development
adapter was `BG03FXF0`, which is still selected by the current source:

```python
ports = glob.glob(f"/dev/serial/by-id/*{FTDI_SERIAL}*")
PORT = ports[0] if ports else "/dev/ttyUSB0"
```

The driver reports `PI30 RS232 /dev/ttyUSB0`, so it is using the fallback rather
than the new by-id identity. It currently works, but after a reboot/replug the
fallback can target the wrong device when several independent inverters or BMS
adapters are connected.

## Observe without disrupting monitoring

```sh
ls -l /dev/serial/by-id/
ls -l /dev/serial/by-path/
dbus -y com.victronenergy.inverter.anern2 /Mgmt/Connection GetValue
```

Compare the new links with the configuration in the actual running-source capture. An old by-id link
already selected before unplugging may not reconnect just because a new adapter appears; exact behavior
depends on whether the driver was restarted and how the source now resolves the port.

## Mapping to record before adding ports

| Device | Physical bank | Adapter by-id | Status |
|---|---|---|---|
| inverter2 | bat2a + two real SmartSolars | `BG041YD3` | Connected and polling through ttyUSB0 fallback |
| inverter1 | independent bat1 | NOT CAPTURED | Do not assign inverter2's instance/config |

Use a separate reviewed change to implement exact `BG041YD3` by-id selection
and fail-closed behavior with no silent ttyUSB fallback. A single two-port
adapter may have a shared isolated side; verify isolation per inverter, not
only a marketing label. Isolation for the new product has not been independently
inspected here.

## Wiring record, not universal pinout

The operator ultimately measured inverter pin 1 around -13.26 V relative to pin 8 and obtained successful
PI30 responses with inverter TX -> adapter RX, inverter RX <- adapter TX and signal GND connected.
This was recorded as inverter pin 1 TX, pin 2 RX, pin 8 GND for that connector orientation/unit.
Do not reuse early contradictory Cisco/RS232 mappings or extrapolate this to every rebrand.
Use the actual port documentation and confirm numbering before wiring another unit.
