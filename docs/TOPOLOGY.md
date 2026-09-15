# Installation topology and evidence boundaries

The owner's clarification on 2026-09-15 supersedes older single-pack descriptions
of installation2. This is the intended physical mapping supplied by the owner;
it does not establish the currently selected DVCC source or the meaning of every
reported BMS field.

| Installation | Grid phase | DC storage and inverter | BMS path to Cerbo |
|---|---|---|---|
| Installation1 | Grid Phase1 | battery1 and inverter1 | Existing JK-BMS Bluetooth integration: `dbus-serialbattery`, `Jkbms_Ble` |
| Installation2 | Grid Phase2 | battery2a + battery2b in parallel on the DC side, with inverter2 | JK master/slave link over RS485-2; battery2a master sends CAN to `vecan1`, battery2b is the slave |

```text
Installation1 / Grid Phase1
  battery1 <-> inverter1
     JK-BMS -- Bluetooth --> Cerbo / existing Jkbms_Ble integration

Installation2 / Grid Phase2
  battery2a (master) --+
                     +-- parallel DC bank <-> inverter2
  battery2b (slave) ---+
     JK master <--> RS485-2 <--> JK slave
         |
         +-- CAN --> Cerbo vecan1 / native can-bus-bms
```

The owner identifies battery2a as master and battery2b as slave. Do not assume
that the master's CAN SOC, current, capacity, cell values or limits describe
both packs; verify the master/slave reporting behavior
before treating a value as a bank aggregate. Older capacity figures and the
owner's description "600Amps" are not verified current bank capacities.

Keep installation1 independent from installation2 in all calculations and
dashboard mappings. Their grid phases are household phase assignments; a
single-phase device's D-Bus `L1` path remains local to that device.

## Service identities

| Role | D-Bus service or supervisor entry | Qualification |
|---|---|---|
| battery1 Bluetooth | `com.victronenergy.battery.ble_<device-address>` | Exact address is kept in ignored private mapping/capture files |
| Installation2 master CAN | `com.victronenergy.battery.socketcan_vecan1` | Native service associated with `can-bus-bms.vecan1` |
| inverter2 | `com.victronenergy.inverter.anern2` | Existing independent RS232 monitoring bridge |
| Possible battery1 supervisor | `dbus-blebattery.0` | Likely association; inspect its run configuration and status before claiming the mapping |

Two SmartSolar 250/70 chargers belong to installation2 in the earlier owner
context; supplied D-Bus evidence names `socketcan_vecan0` for both. Current
DVCC battery selection and effective control relationships remain pending
read-only verification. Service presence is not proof of the active controller.

## Deployment and diagnosis status

The owner confirms no Cerbo runtime configuration changes or deployment since
starting the local Codex/repository work. The Bluetooth integration already
existed. Owner-run read-only captures provide diagnostic evidence; they do not
establish a deployed collector or continuous monitoring integration.

The owner reports that CAN and battery1 Bluetooth were implemented together
and their dropouts started together. There is no CAN-only baseline from before
BLE was introduced. This reported timing supports comparison but does not prove
that Bluetooth caused the CAN failure.

A Grafana-only dashboard scaffold was imported historically. Cerbo-to-Grafana
data integration, continuous collection and Home Assistant collection are not
implemented. See [SOURCE-STATUS.md](SOURCE-STATUS.md) for that distinction and
[POWER-DIAGNOSTICS.md](POWER-DIAGNOSTICS.md) for the owner-run configuration
snapshot command.

The owner supplies and reviews all live configuration evidence. This topology
record grants no permission to connect, change settings, restart services or
deploy code.
