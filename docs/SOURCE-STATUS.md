# Source status and provenance

Prepared on 2026-09-11. No live deployment was performed.

| Item | Provenance and status |
|---|---|
| src/dbus-anern.py | Copied byte-for-byte from the owner's local file named dbus-anern.running.py |
| SHA-256 of supplied raw file | 77f248ea522884c76831b8338b7bacc4ea8281e31a293f3c409c22bf01806847 |
| Second local file, dbus-anern.py | Same bytes and SHA-256 |
| Fresh remote authentication | Not performed; filename and modification time alone cannot prove live provenance |
| service/run and service/log/run | Conversation-derived templates; not fresh remote captures |
| Earlier package | Reconstructed compact driver; superseded by the supplied local file |
| Replacement USB adapter | Owner reports successful operation; new by-id identity remains unverified |
| Original Word document | Retained in owner's original local folder; not included in public repository |

The baseline retains the old adapter selector, fallback, static mode/metadata,
initial zeros, stale values after failed polls and variant-dependent PV parsing.
The absent /Yield/Power path is confirmed in the imported code; nearby historical
comments referring to it do not make it a registered path.

Git may normalize line endings as specified in .gitattributes. The raw hash above
identifies the supplied local file, not a guarantee of identical checkout bytes
under every Git configuration. No known-working release tag has been created.

Before deployment, capture current source and supervisor scripts, verify hashes
and adapter association and compare to this baseline. Preserve private captures.
Before claiming a hardware-tested release, record installed commit/version,
target firmware, verified measurements and systemcalc/DVCC/VRM behavior.


## Relocation — 2026-09-14

The checkout and complete Git history were moved to
C:/Users/thoma/Documents/Codex/cerbo. Existing local source copies are retained
under ignored private-notes/current-scripts/, and the historical Word document
under ignored private-notes/archive/. work/ contains private preparation records.
outputs/ contains local guides and archives; none of these directories is published.

All moved file contents were hash-verified. No driver, tool, service, test or
monitoring-definition changes were made. No Cerbo connection was attempted.
The owner performs deployment and checks all settings; see OWNER-RULES.md.
