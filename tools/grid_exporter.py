#!/usr/bin/env python3
"""Expose existing inverter AC-input V/Hz to Prometheus from a separate host."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import math
import os
import threading
import time

from grid_probe import collect, SERVICE


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


class Tracker:
    """Require an observed UpdateIndex advance; invalidate data on read failure."""
    def __init__(self, stale_after=35):
        self.stale_after = stale_after
        self.reset()

    def reset(self):
        self.owner = None
        self.index = None
        self.advanced_at = None
        self.checked_at = None
        self.last_sample = None

    def observe(self, sample, now):
        if not isinstance(sample, dict):
            self.reset()
            return
        index = number(sample.get("update_index"))
        owner = sample.get("owner")
        values = sample.get("values")
        valid = (
            sample.get("connected") == 1 and sample.get("coherent") is True
            and isinstance(owner, str) and bool(owner)
            and index is not None and index.is_integer() and 0 <= index <= 255
            and isinstance(values, dict)
        )
        if not valid:
            self.reset()
            return
        if owner != self.owner:
            self.reset()
            self.owner = owner
        elif self.index is not None and index != self.index:
            self.advanced_at = now
        self.index = index
        self.checked_at = now
        self.last_sample = sample

    def render(self, now):
        read_ok = (self.checked_at is not None
                   and now - self.checked_at <= self.stale_after)
        fresh = (read_ok and self.advanced_at is not None
                 and now - self.advanced_at <= self.stale_after)
        lines = [
            "# HELP anern_grid_read_success Latest coherent connected D-Bus read succeeded.",
            "# TYPE anern_grid_read_success gauge",
            f"anern_grid_read_success {int(read_ok)}",
            "# HELP anern_grid_sample_fresh UpdateIndex was observed advancing within the freshness window.",
            "# TYPE anern_grid_sample_fresh gauge",
            f"anern_grid_sample_fresh {int(fresh)}",
        ]
        if fresh:
            # Labels intentionally omit phase: device-local L1 is not household L1.
            for key, metric, unit in (
                ("voltage", "anern_ac_input_voltage_volts", "volts"),
                ("frequency", "anern_ac_input_frequency_hertz", "hertz"),
            ):
                value = number(self.last_sample["values"].get(key))
                if value is not None and value >= 0:
                    lines += [
                        f"# HELP {metric} Inverter-reported AC input {unit}; not grid power or relay state.",
                        f"# TYPE {metric} gauge",
                        f"{metric} {value:.12g}",
                    ]
        return "\n".join(lines) + "\n"


class ExporterServer(ThreadingHTTPServer):
    daemon_threads = True


def handler_for(tracker, lock):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/metrics":
                self.send_error(404)
                return
            with lock:
                body = tracker.render(time.monotonic()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-target", default=os.getenv("CERBO_SSH_TARGET"))
    parser.add_argument("--service", default=SERVICE)
    parser.add_argument("--listen", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9786)
    parser.add_argument("--interval", type=float, default=10)
    parser.add_argument("--stale-after", type=float, default=35)
    args = parser.parse_args()
    if not args.ssh_target:
        parser.error("Set CERBO_SSH_TARGET or --ssh-target")
    if not (5 <= args.interval <= 15 and 20 <= args.stale_after <= 120
            and 1 <= args.port <= 65535):
        parser.error("interval: 5..15 s; stale-after: 20..120 s; port: 1..65535")
    tracker = Tracker(args.stale_after)
    lock = threading.Lock()
    stop = threading.Event()

    def worker():
        failed = False
        while not stop.is_set():
            start = time.monotonic()
            try:
                sample = collect(args.ssh_target, args.service)
                with lock:
                    tracker.observe(sample, time.monotonic())
                if failed:
                    print("SSH/D-Bus reads resumed", flush=True)
                failed = False
            except Exception as exc:
                with lock:
                    tracker.reset()
                if not failed:
                    print(f"SSH/D-Bus read failed ({type(exc).__name__}); telemetry withheld", flush=True)
                failed = True
            stop.wait(max(0, args.interval - (time.monotonic() - start)))

    server = ExporterServer((args.listen, args.port), handler_for(tracker, lock))
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    print(f"Metrics: http://{args.listen}:{args.port}/metrics", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        thread.join(timeout=16)


if __name__ == "__main__":
    main()
