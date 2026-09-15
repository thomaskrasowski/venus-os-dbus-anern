# Instructions for contributors and coding assistants

## Persistent owner rules — 2026-09-14

These are the owner's explicit operating rules and persistent project memory.
They override older workflow suggestions in this repository.

- Respond in English. Use English filenames, paths, identifiers, comments and
  primary documentation. Polish is supplementary documentation such as README.pl.md.
- The owner personally reviews and approves ALL Cerbo settings.
- The owner performs Cerbo driver updates and deployment. Do not upload/install
  code on Cerbo, change settings, restart services or operate the installation.
- Ask and wait for explicit approval BEFORE EVERY SSH/SCP/SFTP or other Cerbo
  connection, including read-only diagnostics. Describe the target and precise
  read-only purpose/commands. Prior access, saved credentials, keys, successful
  connections and GitHub authorization do not constitute standing permission.
- NEVER connect to Cerbo autonomously or in the background. Do not launch
  exporters, probes, repeated polling, tunnels, scheduled jobs or auto-reconnects.
- Any individually approved access is read-only and limited to the approved
  scope. Ask again before a subsequent connection.
- Prefer local files supplied by the owner. Repository organization/publication
  does not authorize source changes; the owner is testing the existing baseline.
- Existing SSH/exporter scripts are dormant, optional owner-operated tools.
  Their presence and documentation are not authorization for an assistant to run them.

## Git workflow — owner rule added 2026-09-15

- Start every future Git change on a new, purpose-specific branch. Use the
  `codex/` prefix unless the owner requests another branch name.
- Do not commit directly to `main` and do not reuse a branch that already has
  a pull request for a different logical change.
- Push each change branch to GitHub and create a pull request for review.
- Keep each pull request small and state tests, hardware checks not performed,
  deployment status and material safety limitations.
- Do not merge a pull request unless the owner explicitly asks for the merge.

Read `docs/SOURCE-STATUS.md`, `docs/CHAT-HANDOFF.md` and `docs/known-issues.md` first.

## Authority

The actual source exported from the owner's Cerbo takes precedence over reconstructed chat code.
`src/dbus-anern.py` contains the owner's local dbus-anern.running.py import; fresh remote provenance is unverified.
A local source hash is recorded. Do not call it freshly authenticated live source without remote evidence.
The latest user update is that a replacement USB adapter works. Its by-id path is unknown.

## Safety and change boundaries

- This is an operating energy installation. Repository work is not authorization to deploy.
- Keep the existing inverter2 telemetry working. Never automatically restart the GX, core D-Bus,
  systemcalc, CAN services or charge controllers.
- Do not modify BMS, DVCC, inverter charging limits or PI30 setting commands without a separate request.
- No writes to inverter settings in this monitoring driver. Its intended queries are QID, QMN, QMOD, QPIGS.
- Do not reintroduce a virtual Solar Charger just to improve a tile: it previously crashed systemcalc
  with a string FirmwareVersion and can affect DVCC current accounting.
- Read-only D-Bus publication is not a guarantee of zero effects on system calculations.
- Do not aggregate the independent bat1/inverter1 bank with bat2a/inverter2.
- Do not fabricate grid W/A, charger DC current, SOC, charging phase or authoritative firmware identity.
- Do not pin a new adapter to the old serial or silently fall back to the first ttyUSB device.
- Do not edit `/data/rc.local` by replacing its entire contents. First capture and inspect it.
- `serial-starter` ownership must be managed per adapter where possible. Global stops are diagnostic,
  not a permanent installation solution.

## Engineering

Use small branches and reviewable diffs. The owner handles backups and deployment.
Test CRC/framing offline. Distinguish a read query sent over serial from a setting write.
A running process and a D-Bus registration do not prove healthy data or VRM accounting.
Use BusyBox-compatible target commands (`ps`, `head -n 20`, `/proc`, `svc`, `svstat`).
Do not assume systemd/procps tools are available on Venus.
Never vendor Victron libraries without checking their license; import the installed library instead.

## Privacy

Never commit SSH keys, tokens, cookies, complete chat exports, live logs, device dumps, PV yield state,
or screenshots with identifying data by default. Keep captures in ignored directories.
GitHub changes do not authorize copying secrets from the Cerbo or opening router ports.

## Check before claiming completion

State which tests ran, which hardware tests did not run, and whether anything was actually deployed.
Update the handover and source-status file when facts change. The VRM missing PV tile is still open.
