# Operations: preserve the working installation

## Owner rules, effective 2026-09-14

The owner verifies every Cerbo setting and performs all deployment.
Assistants must ask and wait for explicit approval before EACH Cerbo connection,
including read-only SSH/SCP/SFTP. Never connect autonomously or in the background.
Existing exporters and diagnostic tools must not be launched by assistants.
The commands below are reference instructions for owner-operated work.
See [OWNER-RULES.md](OWNER-RULES.md).

The package is for version control, not automatic redeployment. Existing services continue as they are.
For physical wiring, the confirmed adapter and first checks, start with
[Connect the inverter](INVERTER-CONNECTION.md).

## Retrieve just the current source from Windows

Use your actual Cerbo SSH address in place of `CERBO_IP`. Run in PowerShell in a private working directory:

```powershell
New-Item -ItemType Directory -Force .\captures | Out-Null
scp root@CERBO_IP:/data/apps/dbus-anern-inverter2/dbus-anern.py .\captures\dbus-anern.running.py
scp root@CERBO_IP:/data/apps/dbus-anern-inverter2/service/run .\captures\service-run
scp root@CERBO_IP:/data/apps/dbus-anern-inverter2/service/log/run .\captures\service-log-run
Get-FileHash .\captures\dbus-anern.running.py -Algorithm SHA256
```

These are remote reads. Do not put passwords or tokens in commands. Use your established SSH access.
If SCP reports that SFTP is unavailable, use its legacy `-O` option if supported by your local SCP client.
Do not pipe binary archives through a PowerShell text pipeline.

## Targeted snapshot, including adapter identity

The optional `tools/capture_cerbo.py` reads an allowlist of project files and selected diagnostics.
It writes a new archive under `/data/exports`; no source, supervisor or BMS settings are changed.

```powershell
scp .\tools\capture_cerbo.py root@CERBO_IP:/data/capture-anern.py
ssh root@CERBO_IP "python /data/capture-anern.py"
```

Copy the exact newly printed archive path with SCP. The archive contains source, supervisor scripts,
local yield state if present, a manifest with hashes and USB by-id/by-path links. Logs and `/data/rc.local`
are excluded unless explicitly requested with `--with-logs` / `--with-startup`. Review captures before sharing.
Do not import the entire archive into the repo: counters, logs and local startup content remain private.
The capture is a filesystem snapshot, not a guarantee that already-running Python loaded those exact bytes.

## Compare before committing

```sh
python tools/inspect-source.py captures/dbus-anern.running.py
git diff --no-index src/dbus-anern.py captures/dbus-anern.running.py
```

Review the diff, especially adapter selection, `/Yield/Power`, any virtual solarcharger and any writes.
Then deliberately import the reviewed source to a branch and update source-status provenance.

The owner-run comparison on 2026-09-15 showed no difference between the live
driver and the GitHub source. Replacing that file with the current repository
version would therefore make no functional change and would not create VRM Grid power.

## Existing supervisor commands (run only when intended)

```sh
svstat /service/dbus-anern-inverter2
svc -u /service/dbus-anern-inverter2   # want up, restart on exit
svc -d /service/dbus-anern-inverter2   # stop and want down
svc -t /service/dbus-anern-inverter2   # TERM; restart only if supervisor wants up
```

`svc` operates the supervisor. The target evidence establishes svc/svstat behavior, not that all
standard systemd/procps commands exist. A runit vs daemontools implementation should be identified
before implementation-specific maintenance. Use `svrescan` only where it is actually available.

## Read-only health checks

```sh
dbus -y | grep '^com.victronenergy.inverter.anern2$'
dbus -y com.victronenergy.inverter.anern2 /Connected GetValue
dbus -y com.victronenergy.inverter.anern2 /Mgmt/Connection GetValue
svstat /service/dbus-systemcalc-py
tail -n 30 /data/log/dbus-anern-inverter2/current | tai64nlocal
```

After any approved change confirm stable systemcalc uptime, native CAN battery/SmartSolar services,
unchanged controlling BMS and correct live telemetry. Do not infer safety from a process being `up` alone.

## Persistence

Source and state belong under `/data`. `/opt` is firmware-rootfs content; `/service` is a boot overlay.
Victron documents `/data/rc.local` hooks and service-overlay behavior [see sources.md]. Existing startup
files have NOT been exported here. Do not overwrite them with a template. Preserve the existing setup
until it is captured and a controlled persistence/rollback plan is reviewed.
