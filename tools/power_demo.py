"""Synthetic capture scenario, deliberately unrelated to live device readings."""
from datetime import datetime, timedelta, timezone
import math

BAT1 = "com.victronenergy.battery.demo_bluetooth"
BAT2 = "com.victronenergy.battery.demo_can"
INVERTER = "com.victronenergy.inverter.demo"
SOLAR = "com.victronenergy.solarcharger.demo"


def demo_mapping():
    return {"devices": {
        BAT1: {"label": "Battery 1 · JK-BMS", "bank": "battery1", "transport": "bluetooth"},
        BAT2: {"label": "Battery 2 · JK-BMS", "bank": "battery2", "transport": "can"},
        INVERTER: {"label": "Inverter 2", "bank": "battery2", "transport": "serial"},
        SOLAR: {"label": "Solar charger · bank 2", "bank": "battery2", "transport": "unknown"},
    }}


def demo_records():
    start = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    def device(service, owner, values):
        return {"service": service, "owner": owner, "owner_consistent": True,
                "read_method": "synthetic", "values": {
                    path: {"status": "ok" if value is not None else "invalid", "value": value}
                    for path, value in values.items()}}
    records = []
    for i in range(37):
        ble_down = 12 <= i <= 17
        soc_missing = 6 <= i <= 10
        p = round(680 + 140 * math.sin(i / 4), 1)
        devices = [
            device(BAT1, ":demo.1", {"/Connected": 0 if ble_down else 1,
                   "/UpdateIndex": i, "/Soc": round(68.3 - i * .025, 2),
                   "/Dc/0/Voltage": round(52.2 + .1 * math.sin(i), 2),
                   "/Dc/0/Current": -8.2, "/Dc/0/Power": -428.0, "/Dc/0/Temperature": 24.2}),
            device(BAT2, ":demo.2" if i < 24 else ":demo.22", {
                   "/Connected": 1, "/UpdateIndex": i, "/Soc": None if soc_missing else round(81.1 + i * .01, 2),
                   "/Dc/0/Voltage": round(53.3 + .1 * math.cos(i / 5), 2),
                   "/Dc/0/Current": 12.6, "/Dc/0/Power": p, "/Dc/0/Temperature": 25.1}),
            device(INVERTER, ":demo.3", {"/Connected": 1, "/UpdateIndex": i,
                   "/Ac/Power": 1230 + i, "/Ac/L1/Power": 1230 + i,
                   "/Pv/0/Power": 790 + i * 2, "/Ac/In/L1/V": 230.1,
                   "/Ac/In/L1/F": 50.01, "/Dc/0/Voltage": 53.3}),
            device(SOLAR, ":demo.4", {"/Connected": 1,
                   "/Dc/0/Voltage": 53.3, "/Dc/0/Current": round(p / 53.3, 2),
                   "/Dc/0/Power": p, "/Yield/Power": p, "/Pv/V": 112.7}),
        ]
        # A discovered service vanishes for one observation, then returns.
        if i == 23:
            devices = [d for d in devices if d["service"] != BAT2]
        records.append({"schema_version": 1, "source": "cerbo", "session_id": "synthetic-demo",
                        "captured_at": (start + timedelta(seconds=i * 5)).isoformat().replace("+00:00", "Z"),
                        "elapsed_seconds": i * 5, "collection_duration_seconds": .12,
                        "discovery_success": True, "discovery_truncated": False,
                        "devices": devices,
                        "can": {"status": "ok", "interfaces": [{"name": "can-demo",
                            "stats": {"rx_packets": 5000 + i * 20, "rx_errors": 0 if i < 7 else 3,
                                      "tx_errors": 0, "rx_dropped": 0},
                            "detail": "SYNTHETIC: state ERROR-ACTIVE; no observed hardware"}]},
                        "bluetooth": {"status": "ok", "adapters": [{"path": "/demo/hci0", "powered": True}],
                            "devices": [{"path": "/demo/hci0/battery1", "name": "Synthetic JK-BMS",
                                "adapter": "/demo/hci0", "connected": not ble_down,
                                "services_resolved": not ble_down, "rssi": -65 if not ble_down else None}]},
                        "errors": []})
    return records
