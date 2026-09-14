# Owner operating rules

Recorded on 2026-09-14 from the owner's explicit instructions.
These rules also appear in AGENTS.md so future project sessions receive them.

## Language

Use English for communication, repository/file/path names, code, comments and
primary documentation. Polish files are supplementary translations, normally
with a .pl.md suffix.

## Cerbo access and settings

The owner personally verifies and approves every Cerbo setting. The owner will
perform all Cerbo driver updates and deployment. Assistants may prepare local
files when requested, but must not deploy, change live settings, restart services
or operate the installation.

Before EVERY proposed connection to Cerbo, including SSH, SCP, SFTP or another
read-only interface, the assistant must state the target and the exact read-only
purpose/commands, ask for permission and wait for an explicit answer.
An earlier approval, existing SSH key, known password or GitHub connection does
not authorize another session.

Never connect to Cerbo autonomously or in the background. Do not launch remote
probes, exporter polling, tunnels, scheduled access or automatic reconnects.
Individually approved access remains read-only and limited to the approved scope.
A later connection requires a fresh prompt.

Use owner-supplied local source files/captures by default. Existing tools are
optional owner-operated utilities; documentation is not permission to run them.

## Current development boundary

Preserve the current driver and other executable files during organization and
publication. The owner will test the baseline. New source changes require a
separate request. Repository publication does not change the live installation.
