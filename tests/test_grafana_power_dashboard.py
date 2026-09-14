"""Structural tests for the native Power Observatory Grafana dashboard."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_grafana_power_dashboard import build_dashboard


class GrafanaPowerDashboardTests(unittest.TestCase):
    def setUp(self):
        self.dashboard = build_dashboard()

    def test_identity_panels_and_grid_do_not_overlap(self):
        self.assertEqual("cerbo-power-observatory", self.dashboard["uid"])
        self.assertEqual("Cerbo Power Observatory", self.dashboard["title"])
        ids = [panel["id"] for panel in self.dashboard["panels"]]
        self.assertEqual(len(ids), len(set(ids)))
        occupied = set()
        for panel in self.dashboard["panels"]:
            pos = panel["gridPos"]
            self.assertLessEqual(pos["x"] + pos["w"], 24)
            for x in range(pos["x"], pos["x"] + pos["w"]):
                for y in range(pos["y"], pos["y"] + pos["h"]):
                    self.assertNotIn((x, y), occupied, panel["title"])
                    occupied.add((x, y))

    def test_no_cross_bank_aggregation_or_fabricated_grid_power(self):
        text = str(self.dashboard)
        self.assertNotIn("sum(power_monitor_battery", text)
        grid = next(panel for panel in self.dashboard["panels"] if panel["id"] == 27)
        self.assertEqual("power_monitor_grid_power_watts", grid["targets"][0]["expr"].split("{")[0])
        self.assertNotIn("anern_grid_power", text)

    def test_missing_data_is_not_spanned_or_replaced_with_zero(self):
        for panel in self.dashboard["panels"]:
            if panel["type"] == "timeseries":
                self.assertFalse(panel["fieldConfig"]["defaults"]["custom"]["spanNulls"])
        scope = self.dashboard["panels"][0]["options"]["content"]
        self.assertIn("Blank panels mean no telemetry", scope)
        self.assertIn("never be exported as zero", scope)

    def test_source_mapping_is_explicit_in_transport_queries(self):
        bluetooth = next(panel for panel in self.dashboard["panels"] if panel["id"] == 19)
        self.assertIn("Requires explicit device-to-bank mapping", bluetooth["description"])
        can = next(panel for panel in self.dashboard["panels"] if panel["id"] == 21)
        self.assertIn("Interface-wide", can["description"])


if __name__ == "__main__":
    unittest.main()
