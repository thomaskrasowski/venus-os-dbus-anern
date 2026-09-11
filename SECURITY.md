# Security and operational boundaries

Start with a private repository. Do not commit tokens, passwords, SSH private keys, cookies,
complete chat exports, live source captures, startup files, screenshots, device serial inventories,
logs or local energy counter data without review.

The capture helper has an explicit file allowlist and does not read credential directories.
It cannot guarantee that arbitrary user-edited source or startup scripts contain no secrets.
`.gitignore` is a guardrail, not a security scanner and not a remedy for already committed data.

Keep SSH on the established trusted LAN/VPN. This repository does not require forwarding Cerbo SSH
or D-Bus to the Internet. Do not install an unattended deployment runner on the live GX.

For suspected control impact, stop only the experimental bridge after an authorized operational check,
verify native battery/charger services and systemcalc health, and preserve logs. Never disable BMS protection
or raise charge limits to hide a software alarm.
