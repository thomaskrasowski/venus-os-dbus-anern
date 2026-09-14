# Publish the repository from Windows

Repository: **thomaskrasowski/venus-os-dbus-anern**

Local checkout: **C:\Users\thoma\Documents\Codex\cerbo**

The local checkout already has a main branch and commits. Do not initialize
it again. The ZIP in outputs/ excludes Git history; these commands refer to
the existing local checkout.

This workflow uses HTTPS for GitHub. It does not connect to Cerbo.
The owner performs Cerbo deployment and checks all settings separately.

## 1. Install GitHub CLI if needed

On 2026-09-14, Git was present but GitHub CLI was not found on this laptop.
WinGet was found at the following path:

~~~powershell
& "$env:LOCALAPPDATA\Microsoft\WindowsApps\winget.exe" install --id GitHub.cli --exact --source winget
~~~

Complete the installer, then open a new PowerShell window:

~~~powershell
gh --version
Set-Location 'C:\Users\thoma\Documents\Codex\cerbo'
~~~

If gh is still absent from PATH but its standard installation exists, this
session-only alias can be used:

~~~powershell
Set-Alias gh 'C:\Program Files\GitHub CLI\gh.exe'
~~~

## 2. Verify or establish GitHub authentication

~~~powershell
gh auth status --hostname github.com
~~~

If not authenticated, log in using the browser:

~~~powershell
gh auth login --hostname github.com --git-protocol https --web
~~~

Confirm the account and configure Git's HTTPS credential helper:

~~~powershell
gh api user --jq .login
gh auth setup-git
~~~

The login must be thomaskrasowski. If another saved account is active:

~~~powershell
gh auth switch --hostname github.com --user thomaskrasowski
~~~

The GitHub connector in an application is separate from local gh authentication.
Do not paste tokens or passwords into the repository or conversation.

## 3. Review the local checkout and destination

~~~powershell
git status --short --branch
git log --oneline -5
git remote -v
gh repo view thomaskrasowski/venus-os-dbus-anern --json nameWithOwner,visibility,defaultBranchRef,url
~~~

The local working tree should be clean. A repository-not-found result after
successful account verification means you should check the name/access before
creating it. A network or authentication error is not proof of absence.

The local work/, outputs/, private-notes/ and captures/ directories are ignored.
They contain preparation material, archives or local captures, not public source.
English is the primary documentation; .pl.md files are additional translations.

## 4. Create and push a new public repository

Run once, when the repository does not already exist and there is no origin remote:

~~~powershell
gh repo create thomaskrasowski/venus-os-dbus-anern --public --source . --remote origin --description "Experimental read-only PI30 monitoring for Anern 6200 inverters on Victron Venus OS / Cerbo GX." --push
~~~

README, MIT LICENSE and .gitignore are already committed. Do not initialize
additional files through the GitHub website or creation flags.

If you create an EMPTY public repository at https://github.com/new instead,
leave README/license/gitignore initialization disabled, then use:

~~~powershell
git remote add origin https://github.com/thomaskrasowski/venus-os-dbus-anern.git
git push -u origin main
~~~

If origin already exists, verify its URL and use it rather than adding it twice.
If the remote has commits, fetch and compare histories before proceeding.
Do not use force push to resolve a mismatch.

## 5. Add topics and verify

~~~powershell
gh repo edit thomaskrasowski/venus-os-dbus-anern --add-topic venus-os --add-topic victron --add-topic cerbo-gx --add-topic anern --add-topic pi30 --add-topic inverter --add-topic dbus --add-topic rs232 --add-topic vrm --add-topic grafana --add-topic prometheus
gh repo view thomaskrasowski/venus-os-dbus-anern --json nameWithOwner,visibility,url
gh repo view thomaskrasowski/venus-os-dbus-anern --web
~~~

Check PUBLIC visibility, the latest commit, English README, MIT recognition and
supplementary Polish documents. No stable/hardware-tested tag is implied.
This publication does not deploy anything to Cerbo.

References: [GitHub CLI creation](https://cli.github.com/manual/gh_repo_create),
[authentication](https://cli.github.com/manual/gh_auth_login),
[topics and metadata](https://cli.github.com/manual/gh_repo_edit).
