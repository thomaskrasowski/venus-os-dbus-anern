"""Behavioral tests for Grid collection/export. No Cerbo or Internet access."""
from http.client import HTTPConnection
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import grid_exporter as exporter
import grid_probe as probe


def sample(index=1, **kw):
    result = {
        "service": probe.SERVICE, "owner": ":1.40", "update_index": index,
        "connected": 1, "coherent": True,
        "values": {"voltage": 230.4, "frequency": 49.98},
    }
    result.update(kw)
    return result


class GridTests(unittest.TestCase):
    def setUp(self):
        self.tracker = exporter.Tracker(35)

    def ready(self):
        self.tracker.observe(sample(1), 0)
        self.tracker.observe(sample(2), 10)

    def test_waits_for_poll_advance(self):
        self.tracker.observe(sample(), 0)
        self.assertNotIn("anern_ac_input_voltage_volts 230", self.tracker.render(0))
        self.tracker.observe(sample(2), 10)
        text = self.tracker.render(10)
        self.assertIn("anern_ac_input_voltage_volts 230.4", text)
        self.assertIn("anern_ac_input_frequency_hertz 49.98", text)
        self.assertNotIn("anern_grid_power", text)

    def test_frozen_index_expires_despite_successful_reads(self):
        self.ready()
        self.tracker.observe(sample(2), 50)
        text = self.tracker.render(50)
        self.assertIn("anern_grid_read_success 1", text)
        self.assertIn("anern_grid_sample_fresh 0", text)
        self.assertNotIn("anern_ac_input_voltage_volts", text)

    def test_index_wrap(self):
        self.tracker.observe(sample(255), 0)
        self.tracker.observe(sample(0), 10)
        self.assertIn("anern_grid_sample_fresh 1", self.tracker.render(10))

    def test_disconnect_error_and_restart_withhold_readings(self):
        for failed in (None, sample(3, connected=0),
                       sample(3, coherent=False), sample(3, owner=":1.99")):
            with self.subTest(failed=failed):
                self.ready()
                self.tracker.observe(failed, 11)
                self.assertNotIn("anern_ac_input_voltage_volts", self.tracker.render(11))

    def test_missing_and_nonfinite_are_not_zero(self):
        for value in (None, [], "230", True, float("nan"), float("inf"), -1):
            with self.subTest(value=value):
                self.ready()
                self.tracker.observe(sample(3, values={"voltage": value, "frequency": 50}), 20)
                text = self.tracker.render(20)
                self.assertNotIn("anern_ac_input_voltage_volts", text)
                self.assertIn("anern_ac_input_frequency_hertz 50", text)

    def test_real_zero_is_preserved(self):
        self.ready()
        self.tracker.observe(sample(3, values={"voltage": 0, "frequency": 0}), 20)
        self.assertIn("anern_ac_input_voltage_volts 0", self.tracker.render(20))

    def test_paused_worker_expires_all_data(self):
        self.ready()
        text = self.tracker.render(46)
        self.assertIn("anern_grid_read_success 0", text)
        self.assertNotIn("anern_ac_input_voltage_volts", text)

    def test_collect_uses_fixed_read_program_on_stdin(self):
        result = subprocess.CompletedProcess([], 0, json.dumps(sample()), "")
        with patch.object(probe.subprocess, "run", return_value=result) as run:
            self.assertEqual(probe.collect("root@cerbo.local")["values"]["voltage"], 230.4)
        args, kwargs = run.call_args
        self.assertIn("StrictHostKeyChecking=yes", args[0])
        self.assertIn("BatchMode=yes", args[0])
        self.assertEqual(kwargs["input"], probe.REMOTE)
        self.assertFalse(kwargs.get("shell", False))
        self.assertNotIn("SetValue", probe.REMOTE)
        compile(probe.REMOTE, "<remote>", "exec")

    def test_target_and_service_injection_rejected(self):
        for target in ("-oProxyCommand=bad", "host;bad", "host\nbad", "u@host $(bad)"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                probe.collect(target)
        with self.assertRaises(ValueError):
            probe.collect("cerbo", service="com.victronenergy.grid.fake")

    def test_transport_failure_and_invalid_payload(self):
        for result in (
            subprocess.CompletedProcess([], 255, "", "private text"),
            subprocess.CompletedProcess([], 0, "[]", ""),
            subprocess.CompletedProcess([], 0, "not json", ""),
        ):
            with patch.object(probe.subprocess, "run", return_value=result):
                with self.assertRaises((RuntimeError, ValueError)) as raised:
                    probe.collect("cerbo")
                self.assertNotIn("private text", str(raised.exception))

    def test_http_exposition_and_not_found(self):
        now = time.monotonic()
        self.tracker.observe(sample(1), now - 10)
        self.tracker.observe(sample(2), now)
        server = exporter.ExporterServer(("127.0.0.1", 0),
                                        exporter.handler_for(self.tracker, threading.Lock()))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            conn.request("GET", "/metrics")
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn("version=0.0.4", response.getheader("Content-Type"))
            self.assertIn(b"anern_ac_input_voltage_volts 230.4\n", response.read())
            conn.close()
            conn = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            conn.request("GET", "/other")
            self.assertEqual(conn.getresponse().status, 404)
            conn.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
