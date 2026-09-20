# ForeverSVFix v0.4.0 RC10
Standalone update checks now use a bundled CA certificate store so HTTPS works reliably in frozen builds.


RC10 adds update notifications and carries forward the validated EllesmereUI
profile compatibility introduced in RC9.

## Changes

- Automatically check the public GitHub Releases API for newer ForeverSVFix releases.
- Include release candidates as well as stable releases in update checks.
- Cache automatic checks for 24 hours.
- Use a short timeout and continue normally if GitHub is unavailable.
- Add menu option `9. Check for ForeverSVFix updates`.
- Add the `check-update` command-line command.
- Never auto-download or auto-install an update.
- Send no WoW paths, account names, SavedVariables, addon lists, or telemetry.
- Document EllesmereUI compatibility more clearly for normal users.
- Mark EllesmereUI v9.2.1 profile support as validated in-game across profile switching, `/reload`, relogging, and full client restarts.

The core SavedVariables restoration mechanism is unchanged from RC9.

Linux/Wine remains the only platform validated in-game. Windows and macOS builds
remain experimental pending native testing.
