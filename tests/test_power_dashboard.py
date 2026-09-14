"""Security and offline render checks; no device or network access."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from power_dashboard import render
from power_demo import demo_records


class DashboardTests(unittest.TestCase):
    def test_device_text_cannot_escape_data_script(self):
        payload = {"label": '</script><script>alert("bad")</script>&\u2028'}
        output = render(payload)
        data = output.split('<script id="power-report" type="application/json">', 1)[1].split('</script>', 1)[0]
        self.assertNotIn('<', data)
        self.assertNotIn('&', data)
        self.assertEqual(json.loads(data), payload)
        self.assertIn("connect-src 'none'", output)
        self.assertNotIn("__POWER_REPORT_JSON__", output)

    def test_nonfinite_values_cannot_enter_report(self):
        with self.assertRaises(ValueError):
            render({"value": float("nan")})

    def test_demo_is_explicit_synthetic_and_has_fault_scenarios(self):
        records = demo_records()
        self.assertEqual(len(records), 37)
        self.assertTrue(all(r["session_id"] == "synthetic-demo" for r in records))
        self.assertTrue(any(d["values"].get('/Soc', {}).get('status') == 'invalid'
                            for r in records for d in r["devices"]))
        self.assertTrue(any(d["values"].get('/Connected', {}).get('value') == 0
                            for r in records for d in r["devices"]))


if __name__ == "__main__":
    unittest.main()
