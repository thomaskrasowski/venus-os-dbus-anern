# Monitoring invertera Anern 6200 / PI30 dla Venus OS

[English README](README.md) · [Bezpieczeństwo](SAFETY.md) · [Historia](docs/HISTORY.md)

Niezależny, eksperymentalny sterownik Python/D-Bus do monitorowania invertera
Anern AN-SCI-EVO-6200 na Cerbo GX z Venus OS. Jest dodatkiem społecznościowym;
nie jest oficjalnym ani certyfikowanym pluginem Victron/Anern.

**Uwaga:** błędne ustawienia, okablowanie i dane mogą przyczynić się do pożaru,
porażenia, przepięcia i uszkodzeń. Przed użyciem każdy musi sprawdzić
instalację, ustawienia i pomiary. Pełne ostrzeżenie: [SAFETY.md](SAFETY.md).

## Co zrobiliśmy

- Uruchomiliśmy PI30 po RS232: 2400 baud, 8N1, CRC16/XMODEM z korektą zastrzeżonych bajtów CRC.
- Zbudowaliśmy usługę com.victronenergy.inverter.anern2, instancja 40.
- Odczytujemy AC output, napięcie/częstotliwość AC input, dane baterii po stronie
  invertera, wewnętrzny MPPT, temperaturę, tryb i lokalny szacunek uzysku PV.
- Wewnętrzne PV publikujemy pod /Pv/0/*.
- Usunęliśmy eksperymentalną usługę Solar Charger po problemach z DVCC/SystemCalc.
- Użytkownik wymienił adapter USB i potwierdził działanie.
- Zaimportowaliśmy lokalny plik dbus-anern.running.py; zapisaliśmy jego SHA-256.
  Zgodność z aktualnym plikiem na Cerbo wymaga świeżego porównania.

## Czego jeszcze brakuje

Sterownik ma napięcie i częstotliwość wejścia AC, ale nie zweryfikowaną moc,
prąd ani energię Grid. Nie obliczamy fikcyjnej mocy sieci z innych pomiarów.
Główny kafel PV w VRM, topologia AC i identyfikacja nowego adaptera pozostają
otwarte. Główne szczegóły techniczne utrzymujemy w dokumentacji angielskiej.

## Pliki działającej instalacji

| Cel | Lokalizacja |
|---|---|
| Sterownik | /data/apps/dbus-anern-inverter2/dbus-anern.py |
| Usługa | /service/dbus-anern-inverter2 |
| Log | /data/log/dbus-anern-inverter2/current |

Repozytorium zawiera jeszcze historyczny wybór portu z fallbackiem do ttyUSB0.
Przed instalacją trzeba go zweryfikować; samo działanie nowego adaptera
nie potwierdza stabilnego przypisania przez /dev/serial/by-id/.

[Publikacja na GitHub krok po kroku](docs/PUBLISH.pl.md).
[MIT](LICENSE) pozwala używać, zmieniać i rozpowszechniać kod z zachowaniem
noty copyright i licencji, również komercyjnie. Nie wymaga publikowania zmian.
Zastrzeżenie odpowiedzialności obowiązuje tylko w zakresie dopuszczonym prawem.
Nazwy produktów należą do ich właścicieli i służą opisowi kompatybilności.

## Wykresy Grid

Dodaliśmy sondę D-Bus przez SSH, exporter Prometheus i dashboard Grafana
obejmujące V/Hz wejścia oraz świeżość danych. [Instrukcja i VRM](docs/GRID.md).
Wdrożenie na serwerach, rzeczywiste wykresy i naprawa VRM są jeszcze do wykonania.
