#!/usr/bin/env python3
"""Render a self-contained, offline HTML view of analyzed power captures."""
import json
from pathlib import Path


def render(report):
    template = (Path(__file__).resolve().parents[1] / "monitoring" /
                "power-dashboard.html").read_text(encoding="utf-8")
    # Data cannot close the script element, even when a device label is hostile.
    data = json.dumps(report, ensure_ascii=True, allow_nan=False)
    for char, replacement in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026")):
        data = data.replace(char, replacement)
    return template.replace("__POWER_REPORT_JSON__", data)
