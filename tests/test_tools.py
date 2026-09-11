"""Offline checks for newly authored tooling. No target or network access."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXTRACT = ROOT / "tools/extract_chat.py"
spec = importlib.util.spec_from_file_location("chat_extract", EXTRACT)
extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract)


def msg(role, text, **extra):
    return {"author": {"role": role}, "content": {"parts": [text]}, **extra}


class ToolTests(unittest.TestCase):
    def test_visible_messages_only(self):
        self.assertEqual(extract.visible_text(msg("user", "question")), "question")
        self.assertEqual(extract.visible_text(msg("assistant", "answer", channel="final")), "answer")
        for role in ("system", "developer", "tool"):
            self.assertIsNone(extract.visible_text(msg(role, "omit")))
        self.assertIsNone(extract.visible_text(msg("assistant", "omit", channel="analysis")))
        self.assertIsNone(extract.visible_text(msg("assistant", "omit", recipient="python")))
        self.assertIsNone(extract.visible_text(msg("user", "omit", metadata={"is_visually_hidden_from_conversation": True})))

    def test_exact_active_branch(self):
        chat = {"current_node": "c", "mapping": {
            "a": {"parent": None, "message": msg("user", "one")},
            "b": {"parent": "a", "message": msg("assistant", "alternate")},
            "c": {"parent": "a", "message": msg("assistant", "selected")},
        }}
        self.assertEqual([extract.visible_text(m) for m in extract.branch(chat)], ["one", "selected"])
        with self.assertRaises(ValueError):
            extract.branch({"mapping": chat["mapping"]})

    def test_cycle_rejected(self):
        with self.assertRaises(ValueError):
            extract.branch({"current_node": "x", "mapping": {"x": {"parent": "x"}}})

    def test_extract_cli_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "conversations.json"
            output = directory / "chat.md"
            source.write_text(json.dumps([{"id": "demo", "title": "Cerbo demo", "current_node": "b", "mapping": {
                "a": {"parent": None, "message": msg("user", "hello")},
                "b": {"parent": "a", "message": msg("assistant", "reply", channel="final")}
            }}]))
            command = [sys.executable, str(EXTRACT), str(source), "--id", "demo", "--output", str(output)]
            first = subprocess.run(command, capture_output=True, text=True, timeout=5)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("hello", output.read_text())
            self.assertIn("reply", output.read_text())
            second = subprocess.run(command, capture_output=True, text=True, timeout=5)
            self.assertNotEqual(second.returncode, 0)

    def test_help_does_not_need_cerbo(self):
        for name in ("capture_cerbo.py", "inspect-source.py", "extract_chat.py"):
            with self.subTest(tool=name):
                result = subprocess.run([sys.executable, str(ROOT / "tools" / name), "--help"],
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
