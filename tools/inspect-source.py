#!/usr/bin/env python3
"""Inspect driver source without importing it or accessing serial/D-Bus."""
import argparse
import ast
import hashlib
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('file', type=Path)
args = parser.parse_args()
raw = args.file.read_bytes()
source = raw.decode('utf-8-sig')
tree = ast.parse(source)
print('File:', args.file)
print('SHA256:', hashlib.sha256(raw).hexdigest())
for node in tree.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {
                'SERVICE_NAME', 'INVERTER_SERVICE', 'PV_SERVICE',
                'DEVICE_INSTANCE', 'FTDI_SERIAL', 'POLL_SECONDS'}:
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    value = '<computed>'
                print(f'{target.id} = {value!r}')
constants = {node.value for node in ast.walk(tree)
             if isinstance(node, ast.Constant) and isinstance(node.value, str)}
for item in ('/dev/ttyUSB0', '/Yield/Power', '/Soc', '/Link/ChargeCurrent'):
    print(f'String literal {item!r}:', item in constants)
print('Inspection only: string presence is not proof a D-Bus path is registered.')
