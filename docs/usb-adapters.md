# USB replacement and multi-adapter mapping

## Current report vs known configuration

The user reports the replacement adapter works immediately. Its identity is not yet known to this repository.
The OLD development adapter was `BG03FXF0`. The last shared code uses:

```python
ports = glob.glob(f"/dev/serial/by-id/*{FTDI_SERIAL}*")
PORT = ports[0] if ports else "/dev/ttyUSB0"
```

Consequently 'working straight away' is consistent with either a working by-id match or a fallback.
Do not infer which occurred. In particular, after a reboot/replug the fallback can target the wrong device
when several independent inverters or BMS adapters are connected.

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
| inverter2 | bat2a + two real SmartSolars | NEW ID PENDING | Owner reports working |
| inverter1 | independent bat1 | NOT CAPTURED | Do not assign inverter2's instance/config |

Use a separate reviewed change to implement exact by-id selection and fail-closed behavior with no
silent ttyUSB fallback. A single two-port adapter may have a shared isolated side; verify isolation per
inverter, not only a marketing label. Isolation and pinout for the new product have not been inspected here.

## Wiring record, not universal pinout

The operator ultimately measured inverter pin 1 around -13.26 V relative to pin 8 and obtained successful
PI30 responses with inverter TX -> adapter RX, inverter RX <- adapter TX and signal GND connected.
This was recorded as inverter pin 1 TX, pin 2 RX, pin 8 GND for that connector orientation/unit.
Do not reuse early contradictory Cisco/RS232 mappings or extrapolate this to every rebrand.
Use the actual port documentation and confirm numbering before wiring another unit.
