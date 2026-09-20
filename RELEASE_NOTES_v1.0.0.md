# ForeverSVFix v1.0.0

ForeverSVFix v1.0.0 is the first stable release of the workaround for the World of Warcraft: Forever beta SavedVariables loading bug.

## Highlights

- Restore account-wide SavedVariables before addon initialization.
- Restore per-character SavedVariables through generated load-on-demand helpers.
- Support addons using account-wide and per-character SavedVariables together.
- Support metadata-only Forever TOCs.
- Automatically clean stale ForeverSVFix runtime files during Apply / Refresh.
- Add targeted EllesmereUI v9.2.1 Profiles & Presets compatibility.
- Create safety backups before applying changes.
- Provide installation checks, uninstall support, and update notifications.
- Provide standalone builds for Windows x64, Linux x86_64, macOS Intel, and macOS Apple Silicon.
- Provide a Linux x86_64 AppImage.
- Simplify the normal interactive menu to:
  1. Apply / Refresh ForeverSVFix
  2. Check installation
  3. Settings
  4. Check for updates
  5. Uninstall ForeverSVFix
  6. Exit

Advanced `scan`, `install`, `repair`, `doctor`, and `status` commands remain available from the command line.

## Validation status

Linux/Wine has been validated in-game across account-wide and per-character settings, `/reload`, relogging, full client restarts, EllesmereUI profiles, and a large mixed addon installation.

Windows and macOS builds are available but remain experimental pending native in-game testing.

ForeverSVFix does not need to remain open while WoW is running. Apply or check the workaround, close ForeverSVFix, then start WoW normally.
