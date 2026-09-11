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

## Ostrzeżenie po polsku

**Eksperymentalne oprogramowanie do monitorowania instalacji energetycznych.
Korzystasz na własne ryzyko.**

Błędne okablowanie, ustawienia, pomiary, błędy programu lub jego współdziałanie
z innymi urządzeniami mogą przyczynić się do porażenia prądem, pożaru,
przegrzania, przepięcia, uszkodzenia baterii i sprzętu, utraty zasilania,
obrażeń lub śmierci.

Przed użyciem instalator/użytkownik musi samodzielnie sprawdzić model sprzętu,
wariant protokołu, adapter i pinout, izolację, przypisanie faz i baterii,
poprawność pomiarów i jednostek oraz wszystkie istotne ustawienia invertera,
BMS, ładowarek i Venus OS/DVCC. Instalację elektryczną i zabezpieczenia powinien
sprawdzić uprawniony specjalista, zgodnie z instrukcjami producentów i przepisami.

Odczyt danych nie gwarantuje braku wpływu na inne elementy systemu.
Program ani dashboard nie zastępują BMS, bezpieczników, wyłączników,
uziemienia, izolacji i niezależnych zabezpieczeń sprzętowych.
Brakujących lub nieaktualnych danych nie wolno traktować jako pomiaru zero.
Użytkownik odpowiada za dobór ustawień, ocenę przydatności i weryfikację
działania w swojej instalacji.

Program jest udostępniany w stanie "AS IS", bez gwarancji, na licencji MIT.
W maksymalnym zakresie dopuszczalnym przez obowiązujące prawo autorzy,
właściciele praw autorskich i współtwórcy wyłączają odpowiedzialność za
straty, szkody i obrażenia wynikające z używania, instalacji lub zmian programu.
Wyłączenie nie obejmuje odpowiedzialności, której zgodnie z prawem nie można
wyłączyć ani ograniczyć. Ostrzeżenie nie dodaje ograniczeń do licencji MIT.
