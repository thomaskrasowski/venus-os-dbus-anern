#!/usr/bin/env python3

import os
import sys
import glob
import time
import json
import termios
import select

from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib


# ============================================================
# CONFIG
# ============================================================

SERVICE_NAME = "com.victronenergy.inverter.anern2"

DEVICE_INSTANCE = 40

CUSTOM_NAME = "inverter2"
PRODUCT_NAME = "Anern AN-SCI-EVO-6200"

FTDI_SERIAL = "BG03FXF0"

POLL_SECONDS = 5

STATE_DIR = "/data/apps/dbus-anern-inverter2"
YIELD_FILE = STATE_DIR + "/pv-yield.json"


# ============================================================
# SERIAL PORT
# ============================================================

ports = glob.glob(
    f"/dev/serial/by-id/*{FTDI_SERIAL}*"
)

if ports:
    PORT = ports[0]
else:
    PORT = "/dev/ttyUSB0"


# ============================================================
# FIND VICTRON vedbus.py
# ============================================================

vedbus_matches = glob.glob(
    "/opt/victronenergy/**/vedbus.py",
    recursive=True
)

if not vedbus_matches:
    raise RuntimeError(
        "Cannot find Victron vedbus.py"
    )

VEDBUS_PATH = vedbus_matches[0]

sys.path.insert(
    0,
    os.path.dirname(VEDBUS_PATH)
)

from vedbus import VeDbusService


# ============================================================
# PI30 CRC
# ============================================================

def crc16_xmodem(data):
    crc = 0

    for b in data:
        crc ^= b << 8

        for _ in range(8):
            if crc & 0x8000:
                crc = (
                    ((crc << 1) ^ 0x1021)
                    & 0xffff
                )
            else:
                crc = (
                    (crc << 1)
                    & 0xffff
                )

    hi = (crc >> 8) & 0xff
    lo = crc & 0xff

    # PI30 reserved-byte escaping
    if hi in (0x28, 0x0d, 0x0a):
        hi = (hi + 1) & 0xff

    if lo in (0x28, 0x0d, 0x0a):
        lo = (lo + 1) & 0xff

    return bytes((hi, lo))


# ============================================================
# PI30 SERIAL DRIVER
# ============================================================

class PI30:

    def __init__(self, port):
        self.port = port
        self.fd = None

    def close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass

        self.fd = None

    def open(self):
        if self.fd is not None:
            return

        self.fd = os.open(
            self.port,
            os.O_RDWR |
            os.O_NOCTTY |
            os.O_NONBLOCK
        )

        attrs = termios.tcgetattr(
            self.fd
        )

        # Raw serial
        attrs[0] = 0
        attrs[1] = 0
        attrs[3] = 0

        # 2400 baud, 8N1
        attrs[2] = (
            termios.CLOCAL |
            termios.CREAD |
            termios.CS8
        )

        attrs[4] = termios.B2400
        attrs[5] = termios.B2400

        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0

        termios.tcsetattr(
            self.fd,
            termios.TCSANOW,
            attrs
        )

        termios.tcflush(
            self.fd,
            termios.TCIOFLUSH
        )

    def receive(self, timeout=2.5):
        result = b""

        end = (
            time.monotonic()
            + timeout
        )

        while time.monotonic() < end:

            remaining = (
                end
                - time.monotonic()
            )

            wait = min(
                0.20,
                max(0, remaining)
            )

            ready, _, _ = select.select(
                [self.fd],
                [],
                [],
                wait
            )

            if not ready:
                continue

            try:
                chunk = os.read(
                    self.fd,
                    4096
                )

            except BlockingIOError:
                continue

            if not chunk:
                continue

            result += chunk

            if b"\r" in result:
                break

        return result

    def query_once(self, cmd):
        self.open()

        raw = cmd.encode("ascii")

        packet = (
            raw
            + crc16_xmodem(raw)
            + b"\r"
        )

        termios.tcflush(
            self.fd,
            termios.TCIOFLUSH
        )

        os.write(
            self.fd,
            packet
        )

        termios.tcdrain(
            self.fd
        )

        response = self.receive()

        if not response:
            raise RuntimeError(
                f"{cmd}: no response"
            )

        if not response.endswith(b"\r"):
            raise RuntimeError(
                f"{cmd}: incomplete response "
                f"{response!r}"
            )

        if len(response) < 4:
            raise RuntimeError(
                f"{cmd}: response too short "
                f"{response!r}"
            )

        # BODY + CRC(2 bytes) + CR
        body = response[:-3]

        received_crc = response[-3:-1]
        expected_crc = crc16_xmodem(body)

        if received_crc != expected_crc:
            raise RuntimeError(
                f"{cmd}: CRC mismatch "
                f"rx={received_crc.hex()} "
                f"expected={expected_crc.hex()} "
                f"raw={response!r}"
            )

        if not body.startswith(b"("):
            raise RuntimeError(
                f"{cmd}: invalid PI30 response "
                f"{response!r}"
            )

        text = (
            body[1:]
            .decode(
                "ascii",
                errors="replace"
            )
        )

        # Valid PI30 NAK -> retry
        if text.startswith("NAK"):
            raise RuntimeError(
                f"{cmd}: inverter returned NAK"
            )

        return text

    def query(self, cmd, retries=3):
        last_error = None

        for attempt in range(
            1,
            retries + 1
        ):
            try:
                return self.query_once(cmd)

            except Exception as exc:
                last_error = exc
                self.close()

                if attempt < retries:
                    print(
                        f"{cmd}: retry "
                        f"{attempt}/{retries} "
                        f"after: {exc}",
                        flush=True
                    )

                    time.sleep(0.4)

        raise last_error


# ============================================================
# PV ENERGY COUNTERS
# ============================================================

def default_yield_state():
    return {
        "total_kwh": 0.0,
        "today_date": time.strftime(
            "%Y-%m-%d"
        ),
        "today_kwh": 0.0,
        "today_max_w": 0.0,
        "yesterday_kwh": 0.0,
        "yesterday_max_w": 0.0
    }


def load_yield_state():
    try:
        with open(
            YIELD_FILE,
            "r"
        ) as f:
            state = json.load(f)

        defaults = default_yield_state()

        for key, value in defaults.items():
            if key not in state:
                state[key] = value

        return state

    except Exception:
        return default_yield_state()


def save_yield_state():
    try:
        os.makedirs(
            STATE_DIR,
            exist_ok=True
        )

        tmp = YIELD_FILE + ".tmp"

        with open(
            tmp,
            "w"
        ) as f:
            json.dump(
                yield_state,
                f
            )

        os.replace(
            tmp,
            YIELD_FILE
        )

    except Exception as exc:
        print(
            f"Yield save error: {exc}",
            flush=True
        )


yield_state = load_yield_state()

last_energy_time = time.monotonic()
last_yield_save = time.monotonic()


def update_yield(pv_w):
    global last_energy_time
    global last_yield_save

    now = time.monotonic()

    dt = (
        now
        - last_energy_time
    )

    last_energy_time = now

    # Ignore long gaps after restart/debug/hang
    if dt < 0 or dt > 30:
        dt = 0

    today = time.strftime(
        "%Y-%m-%d"
    )

    if (
        yield_state["today_date"]
        != today
    ):
        yield_state[
            "yesterday_kwh"
        ] = yield_state[
            "today_kwh"
        ]

        yield_state[
            "yesterday_max_w"
        ] = yield_state[
            "today_max_w"
        ]

        yield_state[
            "today_date"
        ] = today

        yield_state[
            "today_kwh"
        ] = 0.0

        yield_state[
            "today_max_w"
        ] = 0.0

        save_yield_state()

    pv_w = max(
        0.0,
        float(pv_w)
    )

    energy_kwh = (
        pv_w
        * dt
        / 3600000.0
    )

    yield_state[
        "total_kwh"
    ] += energy_kwh

    yield_state[
        "today_kwh"
    ] += energy_kwh

    if (
        pv_w
        > yield_state["today_max_w"]
    ):
        yield_state[
            "today_max_w"
        ] = pv_w

    if (
        now
        - last_yield_save
        >= 60
    ):
        save_yield_state()
        last_yield_save = now


# ============================================================
# DBUS
# ============================================================

DBusGMainLoop(
    set_as_default=True
)

dbusservice = VeDbusService(
    SERVICE_NAME,
    register=False
)


# ============================================================
# MANAGEMENT
# ============================================================

dbusservice.add_path(
    "/Mgmt/ProcessName",
    __file__
)

dbusservice.add_path(
    "/Mgmt/ProcessVersion",
    "0.5"
)

dbusservice.add_path(
    "/Mgmt/Connection",
    f"PI30 RS232 {PORT}"
)


# ============================================================
# IDENTIFICATION
# ============================================================

dbusservice.add_path(
    "/DeviceInstance",
    DEVICE_INSTANCE
)

dbusservice.add_path(
    "/ProductId",
    0xffff
)

dbusservice.add_path(
    "/ProductName",
    PRODUCT_NAME
)

dbusservice.add_path(
    "/CustomName",
    CUSTOM_NAME
)

dbusservice.add_path(
    "/FirmwareVersion",
    "PI30"
)

dbusservice.add_path(
    "/HardwareVersion",
    1
)

dbusservice.add_path(
    "/Serial",
    ""
)

dbusservice.add_path(
    "/Connected",
    0
)

dbusservice.add_path(
    "/UpdateIndex",
    0
)


# ============================================================
# STANDARD INVERTER PATHS
# ============================================================

# Read-only. We do not expose writable inverter controls.
dbusservice.add_path(
    "/Mode",
    2
)


# ------------------------------------------------------------
# AC OUTPUT
# ------------------------------------------------------------

dbusservice.add_path(
    "/Ac/Out/L1/V",
    0.0
)

dbusservice.add_path(
    "/Ac/Out/L1/I",
    0.0
)

dbusservice.add_path(
    "/Ac/Out/L1/P",
    0.0
)

dbusservice.add_path(
    "/Ac/Out/L1/S",
    0.0
)

dbusservice.add_path(
    "/Ac/Out/L1/F",
    0.0
)


# Compatibility paths used by Venus/VRM
dbusservice.add_path(
    "/Ac/L1/Voltage",
    0.0
)

dbusservice.add_path(
    "/Ac/L1/Current",
    0.0
)

dbusservice.add_path(
    "/Ac/L1/Power",
    0.0
)

dbusservice.add_path(
    "/Ac/Power",
    0.0
)


# ------------------------------------------------------------
# AC INPUT / GRID TELEMETRY
# ------------------------------------------------------------

dbusservice.add_path(
    "/Ac/In/L1/V",
    0.0
)

dbusservice.add_path(
    "/Ac/In/L1/F",
    0.0
)


# ------------------------------------------------------------
# BATTERY
# ------------------------------------------------------------

# Voltage only as standard DC path.
#
# Deliberately NO /Soc.
# bat2a remains the real system battery/BMS.
#
dbusservice.add_path(
    "/Dc/0/Voltage",
    0.0
)


# Additional read-only battery telemetry
dbusservice.add_path(
    "/Battery/ChargeCurrent",
    0.0
)

dbusservice.add_path(
    "/Battery/DischargeCurrent",
    0.0
)

dbusservice.add_path(
    "/Battery/ReportedSoc",
    0.0
)


# ============================================================
# BUILT-IN INVERTER PV
# ============================================================

dbusservice.add_path(
    "/Pv/0/Voltage",
    0.0
)

dbusservice.add_path(
    "/Pv/0/Current",
    0.0
)

dbusservice.add_path(
    "/Pv/0/Power",
    0.0
)


# This is important:
#
# dbus-systemcalc includes /Yield/Power from inverter services
# in the system PV total.
#

# Local persistent PV energy counters
dbusservice.add_path(
    "/Yield/User",
    float(
        yield_state["total_kwh"]
    )
)

dbusservice.add_path(
    "/Yield/System",
    float(
        yield_state["total_kwh"]
    )
)

dbusservice.add_path(
    "/History/Daily/0/Yield",
    float(
        yield_state["today_kwh"]
    )
)

dbusservice.add_path(
    "/History/Daily/0/MaxPower",
    float(
        yield_state["today_max_w"]
    )
)

dbusservice.add_path(
    "/History/Daily/1/Yield",
    float(
        yield_state["yesterday_kwh"]
    )
)

dbusservice.add_path(
    "/History/Daily/1/MaxPower",
    float(
        yield_state["yesterday_max_w"]
    )
)


# ============================================================
# OTHER TELEMETRY
# ============================================================

dbusservice.add_path(
    "/Temperature",
    0.0
)

dbusservice.add_path(
    "/LoadPercent",
    0.0
)

dbusservice.add_path(
    "/BusVoltage",
    0.0
)

dbusservice.add_path(
    "/Protocol",
    "PI30"
)

dbusservice.add_path(
    "/Raw/Mode",
    ""
)


dbusservice.register()


# ============================================================
# PI30 OBJECT
# ============================================================

pi30 = PI30(PORT)

poll_counter = 0


# ============================================================
# IDENTIFICATION
# ============================================================

def update_identification():
    try:
        serial = pi30.query(
            "QID",
            retries=3
        )

        dbusservice[
            "/Serial"
        ] = serial

        print(
            f"Serial: {serial}",
            flush=True
        )

    except Exception as exc:
        print(
            f"QID failed: {exc}",
            flush=True
        )

    try:
        model = pi30.query(
            "QMN",
            retries=3
        )

        if model:
            dbusservice[
                "/FirmwareVersion"
            ] = model

            print(
                f"Model/FW: {model}",
                flush=True
            )

    except Exception as exc:
        print(
            f"QMN failed: {exc}",
            flush=True
        )


# ============================================================
# OPERATING MODE
# ============================================================

def update_mode():
    try:
        mode = pi30.query(
            "QMOD",
            retries=3
        )

        dbusservice[
            "/Raw/Mode"
        ] = mode

    except Exception as exc:
        print(
            f"QMOD failed: {exc}",
            flush=True
        )


# ============================================================
# POLL
# ============================================================

def poll():
    global poll_counter

    try:
        response = pi30.query(
            "QPIGS",
            retries=3
        )

        values = response.split()

        if len(values) < 20:
            raise RuntimeError(
                f"QPIGS: only "
                f"{len(values)} fields: "
                f"{response}"
            )


        # ====================================================
        # QPIGS PARSING
        # ====================================================

        ac_in_v = float(
            values[0]
        )

        ac_in_f = float(
            values[1]
        )

        ac_out_v = float(
            values[2]
        )

        ac_out_f = float(
            values[3]
        )

        ac_out_va = float(
            values[4]
        )

        ac_out_w = float(
            values[5]
        )

        load_pct = float(
            values[6]
        )

        bus_v = float(
            values[7]
        )

        batt_v = float(
            values[8]
        )

        batt_charge_a = float(
            values[9]
        )

        batt_reported_soc = float(
            values[10]
        )

        temperature = float(
            values[11]
        )

        pv_a = float(
            values[12]
        )

        pv_v = float(
            values[13]
        )

        batt_discharge_a = float(
            values[15]
        )

        pv_w = float(
            values[19]
        )


        # Fallback if PV power is not populated
        if (
            pv_w <= 0
            and pv_v > 0
            and pv_a > 0
        ):
            pv_w = (
                pv_v
                * pv_a
            )


        # AC output current estimated from VA/V
        if ac_out_v > 1:
            ac_out_a = (
                ac_out_va
                / ac_out_v
            )
        else:
            ac_out_a = 0.0


        # ====================================================
        # AC OUTPUT
        # ====================================================

        dbusservice[
            "/Ac/Out/L1/V"
        ] = ac_out_v

        dbusservice[
            "/Ac/Out/L1/I"
        ] = ac_out_a

        dbusservice[
            "/Ac/Out/L1/P"
        ] = ac_out_w

        dbusservice[
            "/Ac/Out/L1/S"
        ] = ac_out_va

        dbusservice[
            "/Ac/Out/L1/F"
        ] = ac_out_f


        dbusservice[
            "/Ac/L1/Voltage"
        ] = ac_out_v

        dbusservice[
            "/Ac/L1/Current"
        ] = ac_out_a

        dbusservice[
            "/Ac/L1/Power"
        ] = ac_out_w

        dbusservice[
            "/Ac/Power"
        ] = ac_out_w


        # ====================================================
        # AC INPUT / GRID
        # ====================================================

        dbusservice[
            "/Ac/In/L1/V"
        ] = ac_in_v

        dbusservice[
            "/Ac/In/L1/F"
        ] = ac_in_f


        # ====================================================
        # BATTERY
        # ====================================================

        dbusservice[
            "/Dc/0/Voltage"
        ] = batt_v

        dbusservice[
            "/Battery/ChargeCurrent"
        ] = batt_charge_a

        dbusservice[
            "/Battery/DischargeCurrent"
        ] = batt_discharge_a

        dbusservice[
            "/Battery/ReportedSoc"
        ] = batt_reported_soc


        # ====================================================
        # BUILT-IN PV
        # ====================================================

        dbusservice[
            "/Pv/0/Voltage"
        ] = pv_v

        dbusservice[
            "/Pv/0/Current"
        ] = pv_a

        dbusservice[
            "/Pv/0/Power"
        ] = pv_w


        # This is the value used by systemcalc
        # to include inverter2 PV in TOTAL system PV.

        # ====================================================
        # LOCAL PV ENERGY COUNTERS
        # ====================================================

        update_yield(
            pv_w
        )

        dbusservice[
            "/Yield/User"
        ] = float(
            yield_state[
                "total_kwh"
            ]
        )

        dbusservice[
            "/Yield/System"
        ] = float(
            yield_state[
                "total_kwh"
            ]
        )

        dbusservice[
            "/History/Daily/0/Yield"
        ] = float(
            yield_state[
                "today_kwh"
            ]
        )

        dbusservice[
            "/History/Daily/0/MaxPower"
        ] = float(
            yield_state[
                "today_max_w"
            ]
        )

        dbusservice[
            "/History/Daily/1/Yield"
        ] = float(
            yield_state[
                "yesterday_kwh"
            ]
        )

        dbusservice[
            "/History/Daily/1/MaxPower"
        ] = float(
            yield_state[
                "yesterday_max_w"
            ]
        )


        # ====================================================
        # OTHER
        # ====================================================

        dbusservice[
            "/Temperature"
        ] = temperature

        dbusservice[
            "/LoadPercent"
        ] = load_pct

        dbusservice[
            "/BusVoltage"
        ] = bus_v

        dbusservice[
            "/Connected"
        ] = 1


        # UpdateIndex
        idx = int(
            dbusservice[
                "/UpdateIndex"
            ]
        )

        dbusservice[
            "/UpdateIndex"
        ] = (
            idx + 1
        ) % 256


        # QMOD every approximately 30 seconds
        poll_counter += 1

        if poll_counter % 6 == 0:
            update_mode()


        print(
            f"OK "
            f"ACout={ac_out_w:.0f}W "
            f"PV={pv_w:.0f}W "
            f"PVV={pv_v:.1f}V "
            f"PVI={pv_a:.1f}A "
            f"Bat={batt_v:.2f}V "
            f"Charge={batt_charge_a:.1f}A "
            f"Discharge={batt_discharge_a:.1f}A "
            f"Load={load_pct:.0f}% "
            f"Temp={temperature:.0f}C "
            f"YieldToday="
            f"{yield_state['today_kwh']:.3f}kWh",
            flush=True
        )


    except Exception as exc:

        dbusservice[
            "/Connected"
        ] = 0

        print(
            f"POLL ERROR: {exc}",
            flush=True
        )

        pi30.close()

    return True


# ============================================================
# START
# ============================================================

print(
    f"Starting {SERVICE_NAME}",
    flush=True
)

print(
    f"Serial port: {PORT}",
    flush=True
)

print(
    "Baud: 2400 8N1",
    flush=True
)

print(
    "Protocol: PI30",
    flush=True
)

print(
    f"vedbus: {VEDBUS_PATH}",
    flush=True
)

print(
    f"PV yield file: {YIELD_FILE}",
    flush=True
)


update_identification()

update_mode()

poll()


GLib.timeout_add_seconds(
    POLL_SECONDS,
    poll
)


mainloop = GLib.MainLoop()

try:
    mainloop.run()

except KeyboardInterrupt:
    print(
        "Stopping...",
        flush=True
    )

finally:
    save_yield_state()
    pi30.close()
