# Third-party software and names

This is an independent community integration maintained by Thomas Krasowski.
It is not affiliated with, endorsed by, certified by or supported by Victron Energy,
Anern, Voltronic Power or their affiliates.

Victron Energy, Cerbo GX, Venus OS, VRM, Anern and other product names belong
to their respective owners. Names are used only to identify products and describe
intended compatibility. No trademark rights are granted by this repository.
No manufacturer logos or official-product presentation are included.

The D-Bus service namespace follows the platform interface convention. Its use
does not mean that this is an official Victron driver.

External runtime dependencies (not copied into this repository):

| Dependency | Upstream |
|---|---|
| velib_python / vedbus | https://github.com/victronenergy/velib_python (upstream MIT) |
| dbus-python | https://dbus.freedesktop.org/doc/dbus-python/ |
| PyGObject / GLib | https://pygobject.gnome.org/ |
| Python | https://www.python.org/ |
| Venus OS | https://github.com/victronenergy/venus |

Check the license of the actual version before redistributing a dependency.
Venus OS contains multiple components with different licenses; compatibility
with Venus OS does not automatically determine this project's license.
