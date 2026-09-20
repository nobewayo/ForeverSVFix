# ForeverSVFix v0.4.0 RC11

RC11 simplifies the interactive app without changing the underlying
SavedVariables workaround.

## Changes

- Replace separate Install and Repair menu entries with **Apply / Refresh ForeverSVFix**.
- Combine Doctor and Status into **Check installation**, which shows both health checks and installation counts.
- Move WoW installation and account selection into a **Settings** submenu.
- Keep manual update checking and uninstall directly on the main menu.
- Remove Scan and other advanced/debug actions from the normal interactive menu.
- Preserve the existing advanced CLI commands for troubleshooting and scripting.
- Clarify that Apply / Refresh should be run after installing, updating, or removing addons, or after a new character first creates SavedVariables.

The account-wide, per-character, EllesmereUI, update-checking, backup, and
uninstall mechanisms are unchanged from RC10.

Linux/Wine remains the only platform validated in-game. Windows and macOS
builds remain experimental pending native testing.
