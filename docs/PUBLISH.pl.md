# Publiczne repozytorium GitHub — PowerShell krok po kroku

Proponowana nazwa: **thomaskrasowski/venus-os-dbus-anern**.
Angielski README jest główny; README.pl.md to polskie wprowadzenie.
Opis i topics pomagają opisać kompatybilność, ale nie gwarantują pozycji wyszukiwania.

## 1. Otwórz katalog gotowego repozytorium

~~~powershell
Set-Location 'SCIEZKA_DO_ROZPAKOWANEGO_REPOZYTORIUMenus-os-dbus-anern'
git status
git log --oneline -5
git remote -v
~~~

Folder przygotowany lokalnie przez Codex ma już historię Git. ZIP zawiera pliki
bez .git; po rozpakowaniu ZIP wykonaj poniższe polecenia tylko jeśli folder
nie jest jeszcze repozytorium. Komenda status nie powinna wskazywać repo rodzica.

~~~powershell
git init -b main
~~~

## 2. GitHub CLI, jeśli nie jest zainstalowane

~~~powershell
winget install --id GitHub.cli --exact --source winget
~~~

Otwórz nowe okno PowerShell, wróć do katalogu repo i sprawdź:

~~~powershell
gh --version
gh auth login --hostname github.com --git-protocol https --web
gh api user --jq .login
gh auth setup-git
~~~

Wynik login musi wskazywać thomaskrasowski.
Jeśli zalogowanych jest kilka kont, wybierz właściwe:

~~~powershell
gh auth switch --hostname github.com --user thomaskrasowski
~~~

## 3. Sprawdź pliki i zapisz lokalne zmiany, jeśli są

~~~powershell
py -m unittest discover -s tests -v
git status --short
git add .
git diff --cached --stat
git diff --cached
~~~

Nie dodawaj haseł, kluczy, logów, captures, całego eksportu rozmowy ani stanu PV.
Jeżeli powyżej są zmiany do zapisania (albo ZIP nie ma pierwszego commitu):

~~~powershell
git commit -m "Prepare public PI30 monitoring integration"
~~~

Git może poprosić o nazwę i adres autora. Użyj swoich danych lub adresu noreply
skopiowanego z GitHub Settings → Emails. Nie używaj cudzego adresu.
Folder przygotowany przez Codex używa lokalnie loginu i adresu
thomaskrasowski@users.noreply.github.com; możesz wybrać swój zweryfikowany noreply.

## 4. Utwórz publiczne repo i opublikuj kod

Te polecenia wykonaj jeden raz, gdy repo jeszcze nie istnieje, a origin jest pusty:

~~~powershell
gh repo create thomaskrasowski/venus-os-dbus-anern --public --source . --remote origin --description "Experimental read-only PI30 driver for Anern 6200 inverters on Victron Venus OS / Cerbo GX. D-Bus telemetry and Grid observability." --push
~~~

LICENSE, README i .gitignore są już w lokalnych plikach. Nie dodawaj ich
ponownie opcjami tworzenia repozytorium.

Jeśli tworzysz repo przez https://github.com/new: wybierz Public i pozostaw
inicjalizację README, .gitignore i licencji wyłączoną, następnie:

~~~powershell
git remote add origin https://github.com/thomaskrasowski/venus-os-dbus-anern.git
git push -u origin main
~~~

Jeżeli origin już istnieje, najpierw sprawdź jego adres. Nie nadpisuj go automatycznie.
Jeżeli GitHub repo ma już commity, najpierw pobierz i porównaj historię.
Nie używaj force push do rozwiązywania konfliktu.

## 5. Topics i sprawdzenie publikacji

~~~powershell
gh repo edit thomaskrasowski/venus-os-dbus-anern --add-topic venus-os --add-topic victron --add-topic cerbo-gx --add-topic anern --add-topic pi30 --add-topic inverter --add-topic solar --add-topic dbus --add-topic rs232 --add-topic vrm --add-topic grafana --add-topic prometheus
gh repo view thomaskrasowski/venus-os-dbus-anern --json nameWithOwner,visibility,url
gh repo view thomaskrasowski/venus-os-dbus-anern --web
~~~

Sprawdź PUBLIC, poprawny README, rozpoznanie licencji MIT i pliki dokumentacji.
Kod i instrukcje nie są dowodem wdrożenia na Cerbo ani działających wykresów.
Nie oznaczaj wydania jako stable/production przed testami na sprzęcie.

Dokumentacja poleceń: https://cli.github.com/manual/gh_repo_create
i https://cli.github.com/manual/gh_repo_edit.
