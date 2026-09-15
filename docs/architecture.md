# Architecture and telemetry

## Owner-confirmed installation arrangement

See [TOPOLOGY.md](TOPOLOGY.md) for the 2026-09-15 correction. Installation1
(Grid Phase1) has battery1/inverter1 and an existing JK-BMS Bluetooth connection
through `dbus-serialbattery` / `Jkbms_Ble`. Installation2 (Grid Phase2) has
battery2a and battery2b in parallel on the DC side with inverter2. Their JK BMSs
use an RS485-2 master/slave link: battery2a is the master sending CAN to Cerbo
`vecan1`, and battery2b is the slave. The aggregation semantics of the master's
fields remain unverified.

## Existing inverter2 monitoring bridge

```text
inverter2 RS232 -> USB serial adapter -> one Python process
                                            |
                         com.victronenergy.inverter.anern2 [40]
                                            |
                                Venus consumers / VRM

installation2 JK master -> CAN vecan1 -> native CAN battery service
installation2 SmartSolars -> CAN vecan0 -> native solar-charger services
```

The SmartSolar installation association comes from earlier owner context;
`socketcan_vecan0` is reported by the supplied service evidence. Active DVCC
battery selection and control relationships still require verification. The
diagram does not assert that the CAN master currently controls the chargers.

The bridge queries QID and QMN at startup, QPIGS on a nominal 5-second timer and QMOD periodically.
It validates received CRC and retries up to three times, including explicit NAK responses.
Serial reads/retries run in the GLib thread, so the timing is nominal rather than a hard 5-second deadline.

## Principal paths

| Path | Meaning in the prototype | Qualification |
|---|---|---|
| `/Ac/In/L1/V`, `/Ac/In/L1/F` | AC input V and Hz | Not grid W/A |
| `/Ac/Out/L1/V`, `/Ac/Out/L1/F` | AC output V and Hz | Inverter's own phase |
| `/Ac/Out/L1/P`, `/Ac/Out/L1/S` | Output W and VA | QPIGS reported |
| `/Ac/Out/L1/I` | Output current | Calculated VA/V |
| `/Dc/0/Voltage` | Inverter DC-terminal voltage | Not necessarily identical to BMS voltage |
| `/Battery/ChargeCurrent`, `/Battery/DischargeCurrent` | Inverter-reported charging/discharging A | Not net current including external MPPTs |
| `/Battery/ReportedSoc` | Inverter-reported SOC | NOT top-level `/Soc`; BMS remains separate |
| `/Pv/0/Voltage`, `/Pv/0/Current`, `/Pv/0/Power` | Internal PV measurements | Variant-specific QPIGS parsing |
| `/Yield/User`, `/Yield/System` | Locally integrated PV kWh | Not a lifetime inverter energy register |
| `/History/Daily/0/Yield` | Local daily energy estimate | Follows GX process date/time; originally UTC |
| `/Raw/Mode` | Raw QMOD response | B observed; `/Mode=2` is still a static placeholder |
| `/Connected` | Latest polling success | Old telemetry is not cleared on failure |

The source preserves QPIGS field 19 as PV power and a V*I fallback for a zero value.
That fallback is a known limitation: field meanings and valid zero readings must be reviewed
before claiming an accurate generic PI30 implementation.

## No imaginary grid meter

The demonstrated response has AC input voltage/frequency, not a validated input power measurement.
Do not derive grid power by subtracting asynchronous PV/load/BMS readings and call it measured.
QPIGS does provide measured AC output active and apparent power, already
published as `/Ac/Out/L1/P` and `/Ac/Out/L1/S`. These describe power delivered
at the inverter output and cannot be renamed as utility import.

On the confirmed Venus OS v3.79 system, `/Ac/Grid/L1/Power` was unavailable and
`/Ac/ActiveIn/Source` was 240. See [VRM Grid troubleshooting](GRID.md).

## PV tile / accounting

D-Bus registration, a custom path and a local JSON counter are separate from VRM ingestion,
system aggregation and dashboard rendering. The last snapshot intentionally omits `/Yield/Power`.
No claim is made that internal inverter PV is currently included in the VRM main PV tile or all energy totals.
Two real SmartSolars remain native services. Their missing tile is an open problem, not proof they stopped.

## Control

The process sends read queries only, not inverter setting writes. It does not implement a DVCC control path.
Nevertheless publishing data can influence other Venus consumers. 'Read-only' is not a blanket guarantee
of no side effects. In particular, reintroducing `com.victronenergy.solarcharger` requires careful DVCC review.
