#!/usr/bin/env python3
"""Capture selected project files and read-only diagnostics on a Cerbo GX.

Writes one local archive; does not stop/restart services, change settings,
open serial ports or collect credentials. File contents are not redacted:
review the archive before sharing it or committing selected files.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time

APP = Path('/data/apps/dbus-anern-inverter2')
MAX_FILE_BYTES = 2 * 1024 * 1024


def command(argv: list[str], timeout: float = 8) -> dict:
    try:
        result = subprocess.run(argv, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout,
                                check=False)
        return {'argv': argv, 'returncode': result.returncode,
                'output': result.stdout[-60000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'argv': argv, 'error': str(exc)}


def usb_links() -> dict:
    result = {}
    for directory in ('/dev/serial/by-id', '/dev/serial/by-path'):
        result[directory] = [
            {'link': path, 'target': os.path.realpath(path)}
            for path in sorted(glob.glob(directory + '/*'))
        ]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New .tar.gz file; never overwritten')
    parser.add_argument('--with-logs', action='store_true',
                        help='Include the last 64 KiB of the driver log (may be private)')
    parser.add_argument('--with-startup', action='store_true',
                        help='Include /data/rc.local; review for unrelated/private content')
    args = parser.parse_args()
    if not (APP / 'dbus-anern.py').is_file():
        raise SystemExit(f'Missing {APP / "dbus-anern.py"}; run this on the Cerbo.')
    os.umask(0o077)
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    output = args.output or Path('/data/exports') / f'anern-snapshot-{stamp}.tar.gz'
    if output.exists():
        raise SystemExit(f'Refusing to overwrite {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, bytes] = {}
    manifest = {'captured_utc': stamp, 'source': 'Cerbo filesystem snapshot',
                'note': 'Not a full backup; archive is not automatically redacted.',
                'files': [], 'warnings': []}
    selected = {
        'runtime/dbus-anern.py': APP / 'dbus-anern.py',
        'runtime/service/run': APP / 'service/run',
        'runtime/service/log/run': APP / 'service/log/run',
        'runtime/pv-yield.json': APP / 'pv-yield.json',
        'runtime/venus-version.txt': Path('/opt/victronenergy/version'),
    }
    if args.with_startup:
        selected['private/rc.local'] = Path('/data/rc.local')
    for member, path in selected.items():
        if not path.is_file():
            manifest['warnings'].append(f'Not found: {path}')
            continue
        before = path.stat()
        if before.st_size > MAX_FILE_BYTES:
            manifest['warnings'].append(f'Skipped oversized file: {path}')
            continue
        content = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            manifest['warnings'].append(f'File changed during capture: {path}')
        payload[member] = content
        manifest['files'].append({'source': str(path), 'member': member,
                                  'bytes': len(content),
                                  'sha256': hashlib.sha256(content).hexdigest()})
    if args.with_logs:
        path = Path('/data/log/dbus-anern-inverter2/current')
        if path.is_file():
            with path.open('rb') as stream:
                stream.seek(max(0, path.stat().st_size - 65536))
                payload['private/driver-log-tail.txt'] = stream.read(65536)
    diagnostics = {'usb_links': usb_links(), 'commands': []}
    checks = [
        ['svstat', '/service/dbus-anern-inverter2'],
        ['svstat', '/service/dbus-systemcalc-py'],
        ['svstat', '/service/serial-starter'],
        ['dbus', '-y'],
        ['dbus', '-y', 'com.victronenergy.inverter.anern2', '/Connected', 'GetValue'],
        ['dbus', '-y', 'com.victronenergy.inverter.anern2', '/Mgmt/Connection', 'GetValue'],
        ['dbus', '-y', 'com.victronenergy.inverter.anern2', '/Pv/0/Power', 'GetValue'],
        ['dbus', '-y', 'com.victronenergy.inverter.anern2', '/Yield/Power', 'GetValue'],
    ]
    for path in sorted(glob.glob('/dev/ttyUSB*')):
        checks.append(['fuser', path])
    diagnostics['commands'] = [command(item) for item in checks]
    payload['diagnostics.json'] = json.dumps(diagnostics, indent=2).encode()
    payload['manifest.json'] = json.dumps(manifest, indent=2).encode()
    # Exclusive creation prevents silently replacing an earlier snapshot.
    with output.open('xb') as raw:
        with tarfile.open(fileobj=raw, mode='w:gz') as archive:
            for member, content in payload.items():
                info = tarfile.TarInfo(member)
                info.size = len(content)
                info.mode = 0o600
                info.mtime = int(time.time())
                archive.addfile(info, io.BytesIO(content))
    print(f'Created: {output}')
    print('No service, serial-port or configuration changes were made.')
    print('Download and inspect before sharing. Do not commit the raw archive.')
    for warning in manifest['warnings']:
        print('WARNING:', warning)


if __name__ == '__main__':
    main()
