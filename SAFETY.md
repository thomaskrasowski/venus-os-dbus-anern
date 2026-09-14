# Safety notice and disclaimer

**Experimental software for electrical-energy monitoring. Use at your own risk.**

Incorrect wiring, configuration, measurements, software faults or interaction
with other equipment may contribute to electric shock, fire, overheating,
overvoltage, battery damage, equipment damage, loss of power, injury or death.

Before installation or use, the installer/operator must independently verify
the hardware model, protocol variant, serial adapter and pinout, electrical
isolation, phase and battery-bank mapping, readings, units and all relevant
inverter, battery/BMS, charger and Venus OS/DVCC settings for their installation.
Observe manufacturer instructions and applicable electrical rules. Electrical
installation and protective measures must be checked by a qualified person.

The driver sends telemetry queries; it does not implement inverter setting
commands. However, software receiving its D-Bus data may use that data in
system calculations or control decisions. "Read-only" does not establish
electrical safety or absence of indirect effects.

This software is not a protection device, BMS, certified meter, emergency-stop
system or substitute for fuses, breakers, earthing, isolation and independent
hardware protection. Do not rely on dashboards or this driver for protective
decisions. Missing, delayed, stale or implausible data must be investigated.
Unknown measurements must not be treated as zero.

Keep a backup of the working configuration. Validate changes under appropriate
supervision, verify the resulting measurements independently and maintain a
tested rollback procedure. The operator is responsible for deciding whether
the software and settings are suitable for their installation.

The software is provided "AS IS", without warranties, under the [MIT License](LICENSE).
To the fullest extent permitted by applicable law, the authors, copyright
holders and contributors disclaim liability for loss, damage or injury arising
from use, modification, installation or inability to use this software.
Nothing in this notice excludes or limits liability that cannot lawfully be
excluded or limited. This notice creates no additional license restrictions.

[Additional Polish translation](SAFETY.pl.md).
