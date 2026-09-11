"""Offline tests: no imports of the driver, D-Bus or serial access."""
import ast
import binascii
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/dbus-anern.py'
TREE = ast.parse(SOURCE.read_text())
FUNCTION = next(node for node in TREE.body if isinstance(node, ast.FunctionDef)
                and node.name == 'crc16_xmodem')
namespace = {}
exec(compile(ast.Module(body=[FUNCTION], type_ignores=[]), str(SOURCE), 'exec'), namespace)
CRC = namespace['crc16_xmodem']

# Fixtures are literal frames observed in the user's PI30 probe output.
FRAMES = [
    bytes.fromhex('28 50 49 33 30 9a 0b 0d'),
    bytes.fromhex('28 42 e7 c9 0d'),
    bytes.fromhex('28 4e 41 4b 73 73 0d'),
    bytes.fromhex('28 56 4d 49 49 2d 4e 58 50 57 35 4b 57 39 b3 0d'),
]


class SnapshotTests(unittest.TestCase):
    def test_syntax_all_python(self):
        for directory in ('src', 'tools', 'tests'):
            for file in (ROOT / directory).glob('*.py'):
                with self.subTest(file=file.name):
                    ast.parse(file.read_text(), filename=str(file))

    def test_transmitted_frames(self):
        for command, checksum in ((b'QPI', 'beac'), (b'QPIGS', 'b7a9'), (b'QPIRI', 'f854')):
            self.assertEqual(CRC(command).hex(), checksum)

    def test_received_frames(self):
        for frame in FRAMES:
            with self.subTest(frame=frame):
                self.assertEqual(CRC(frame[:-3]), frame[-3:-1])

    def test_crc_matches_standard_library(self):
        for n in range(512):
            data = f'QTEST{n}'.encode()
            value = binascii.crc_hqx(data, 0)
            expected = bytearray(value.to_bytes(2, 'big'))
            for i in range(2):
                if expected[i] in (0x28, 0x0d, 0x0a):
                    expected[i] += 1
            self.assertEqual(CRC(data), bytes(expected))

    def test_only_expected_queries(self):
        commands = set()
        for node in ast.walk(TREE):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'pi30' and node.func.attr == 'query'):
                self.assertIsInstance(node.args[0], ast.Constant)
                commands.add(node.args[0].value)
        self.assertEqual(commands, {'QID', 'QMN', 'QMOD', 'QPIGS'})

    def test_no_virtual_charger_or_control_path(self):
        keys = {node.args[0].value for node in ast.walk(TREE)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'add_path' and node.args
                and isinstance(node.args[0], ast.Constant)}
        self.assertNotIn('/Yield/Power', keys)
        self.assertNotIn('/Soc', keys)
        self.assertFalse(any(key.startswith('/Link/') for key in keys))
        self.assertIn('/Pv/0/Power', keys)
        names = [node.value for node in ast.walk(TREE)
                 if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        self.assertFalse(any(value.startswith('com.victronenergy.solarcharger.') for value in names))
        self.assertNotIn('writeable=True', SOURCE.read_text())


if __name__ == '__main__':
    unittest.main()
