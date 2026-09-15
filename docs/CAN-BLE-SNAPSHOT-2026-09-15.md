# CAN and Bluetooth configuration snapshot findings

Evidence: owner-supplied local `cerbo-config-before.json`, captured at
2026-09-15 20:55:51 UTC. Collection completed in 2.45 seconds. Raw output and
unique device addresses are private and excluded from this repository.
No assistant connection, service action, settings change or deployment occurred.

## CAN failure mechanism

`vecan1` remains `ERROR-PASSIVE`. Its counters match the earlier observations:
19 bus-offs and restarts, 52 warning transitions, 67 passive transitions,
1,385,074 RX packets, 102,567 TX packets and 71 dropped TX packets. Matching
snapshots are evidence of stalled delivery over those observations, not
continuous observation or proof that the BMS stopped transmitting electrically.

The retained kernel messages show repeated bus-offs followed by the
`mcp251xfd_handle_tefif()` / IRQ-handler `-22` failure at uptime 51359.664.
Capture uptime is 95731.52 seconds. Native `can-bus-bms` remains running since
boot, while its log and systemcalc independently record battery-service removal.
Connection/registration lines replayed in a backlog dump are historical.

Victron's source tag matching reported kernel `6.12.90-venus-4` routes TEFIF
errors into `out_fail`. For this error, it logs the IRQ failure, disables chip
interrupts and stops timestamping. That supports a persistent host-side CAN
delivery failure. The installed binary has not been hash-compared with the tag;
the cause of the earlier bus-offs and the trigger for `-22` remain unproven.
[Exact-tag error path](https://github.com/victronenergy/linux/blob/v6.12.90-venus-4/drivers/net/can/spi/mcp251xfd/mcp251xfd-core.c#L1491-L1569)

## Battery selection and Bluetooth

D-Bus discovery succeeded without truncation, and inspected service owners were
stable. Neither battery service was present. Settings select BMS instance 512,
battery `com.victronenergy.battery/512`, and that battery's temperature path.
The retained systemcalc log explicitly maps instance 512 to
`com.victronenergy.battery.socketcan_vecan1`, then records its disappearance.

At capture time, active battery/BMS identity and SOC were unavailable. DVCC and
all captured active sensing/control flags were zero. Persisted shared voltage,
temperature and current sensing settings were each 1; they are not disabled
settings. `CanBmsSense` was 0. System voltage named inverter2 as its source;
the sources of current/power were not established.

The battery1 supervisor is confirmed as `/service/dbus-blebattery.0`. Its run
script launches the JK BLE Python driver as a child and forwards TERM/INT.
Reported driver version is `2.1.20260729dev`. The retained BLE log repeatedly
reports a successful connection followed by missing characteristic UUID
`0000ffe1-0000-1000-8000-00805f9b34fb` and missing fallback handle 4. This is
characteristic discovery/access failure, not proof of a weak radio signal.

Decoded log-clock times place the last retained BLE shutdown message on
September 14 at about 18:26, well before the September 15 CAN removal at about
08:36. These clocks have not been independently synchronized. The BLE Python
process and its supervisor still appear running at the snapshot. A stuck exit
is a hypothesis; the shutdown log alone does not establish process termination.
Do not describe these retained events as a simultaneous failure.

`vesmart-server` is installed but absent from the process/service listings.
`dbus-ble-sensors` is running and its log says it opened `hci0`. That is not
evidence either component caused the CAN failure. A future isolation test must
verify the JK child process actually stops and start from recovered CAN; a
pause during an already-stalled CAN state cannot test prevention.

## Other observations and collection limits

Current load is 0.44/0.67/0.73 with about 567 MiB memory available. This does not
establish resource conditions at failure time. PSI files are unavailable.
The inverter2 log also contains current `QPIGS: no response` errors; overview
voltage is therefore not proof of fresh BMS or inverter communication.

Missing alternative configuration directories, PSI files, and battery-only
paths on SmartSolar services explain many `partial`/`missing` results. The
snapshot collector also incorrectly used nominal sysfs file sizes to mark
short, complete CAN values as truncated. That metadata defect does not explain
the actual bus-offs or IRQ errors; the actual counter text remains usable.
The accompanying collector correction uses actual bytes read to detect head
truncation, while preserving real log-tail and byte-budget limits.

## Next bounded owner-run read

The matching kernel exposes these read-only cached SPI/recovery attributes.
Read them before resetting/rebooting or changing a service:

```sh
date -u
cat /sys/class/net/vecan1/spi_stats
cat /sys/class/net/vecan1/failed
cat /sys/class/net/vecan1/restarted
```

Keep errors if an attribute is absent. `spi_stats` reports SPI transfers and CRC
retries/errors, distinct from CAN bus-offs. `failed=0` cannot exclude the TEFIF
failure: that flag belongs to a different recovery path.
[Attribute definitions](https://github.com/victronenergy/linux/blob/v6.12.90-venus-4/drivers/net/can/spi/mcp251xfd/mcp251xfd-core.c#L1968-L2008)
