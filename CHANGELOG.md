# Changelog

## 1.0.2

- Reduce the automatic update-check cache from 24 hours to 15 minutes.
- Keep manual update checks forced and uncached.
- Update documentation to reflect the shorter automatic update interval.

## 1.0.1

- Fix SavedVariables restore ordering for addons that initialize or reset their SavedVariables globals while their normal files load.
- Restore account-wide and per-character SavedVariables after normal addon files by default, matching WoW's normal loading semantics.
- Respect `## LoadSavedVariablesFirst: 1` by restoring before addon scripts when explicitly requested.
- Preserve the previously validated EllesmereUI compatibility ordering.
- Migrate existing marker-v4 patches to marker v5 on Apply / Refresh.
- Add regression coverage for default post-script restores, `LoadSavedVariablesFirst`, and v4-to-v5 migration.

## 1.0.0

- Simplify the interactive menu around the actions normal users actually need.
- Merge Install and Repair into a single **Apply / Refresh ForeverSVFix** action.
- Merge Doctor and Status into a single **Check installation** screen with health and installation counts.
- Move WoW installation and account selection into a dedicated **Settings** submenu.
- Keep `scan`, `install`, `repair`, `doctor`, and `status` available as advanced CLI commands.
- Clarify that Apply / Refresh should be run after installing, updating, or removing addons.
- Promote the validated 0.4.0 release-candidate series to the first stable release.
- Keep the validated SavedVariables restoration mechanism unchanged from RC10.

## 0.4.0 RC10

- Add automatic update notifications using the public GitHub Releases API.
- Cache automatic checks for 24 hours and fail quietly when GitHub is unavailable.
- Add a manual `Check for ForeverSVFix updates` menu option and `check-update` CLI command.
- Include prereleases when checking for updates, so RC users are warned about newer RC builds.
- Document that no WoW data, addon data, or telemetry is sent during update checks.
- Document and mark the EllesmereUI v9.2.1 profile compatibility path as validated in-game.
- Keep the SavedVariables restoration mechanism unchanged from RC9.


## 0.4.0 RC9

- Add targeted EllesmereUI v9.2.1 profile compatibility.
- Generate a local shim that disables only EllesmereUI's temporary Forever SavedVariables safety gate after `EllesmereUI_Lite.lua`.
- Preserve `EllesmereUI.IS_FOREVER` and unrelated Forever-specific feature gates.
- Re-enable EllesmereUI's existing Profiles & Presets and reload-dependent settings flows while ForeverSVFix is active.
- Suppress EllesmereUI's SavedVariables warning while the compatibility shim is active.
- Add Doctor and uninstall handling for the generated EllesmereUI compatibility shim.
- Fail closed on unfamiliar EllesmereUI TOC layouts instead of guessing.
- Fix Status counts to match the current state-file schema.
- Add the AI-assisted development disclosure to the README.

## 0.4.0 RC8

- Add a Linux x86_64 AppImage build.
- Make AppImage the recommended Linux standalone package.
- Keep the raw Linux executable as a fallback.
- Add a desktop-friendly AppRun wrapper that opens the console menu in common
  terminal emulators when the AppImage is double-clicked.
- Add AppImage installation notes for non-technical Linux users.
- Keep the SavedVariables mechanism unchanged.


## 0.4.0 RC7

- Remove the duplicate License section from README.
- Add a prominent use-at-your-own-risk warning.
- Make the no-warranty/no-guarantee wording visible before installation steps.
- Clearly mark Windows and macOS as untested in-game and experimental.
- Keep the validated SavedVariables mechanism and standalone build workflow unchanged.


## 0.4.0 RC6

- Add a beginner-friendly installation, addon-update, repair, Doctor, and
  uninstall guide near the top of the README.
- Make standalone releases the recommended installation method.
- Keep Python instructions only for advanced/source usage.
- Build separate standalone executables for Windows x64, Linux x86_64,
  macOS Intel, and macOS Apple Silicon.
- Keep the validated SavedVariables workaround unchanged.


## 0.4.0 RC5

- Align the custom license exactly with the intended redistribution rule.
- Modified versions may be published with clear attribution to Simon Ahnfeldt Nielsen.
- Only unchanged official copies are prohibited from being mirrored or re-uploaded.
- No SavedVariables or interactive-menu behavior changed.


## 0.4.0 RC4

- Fix the standalone Windows build smoke test so it runs correctly under the
  native GitHub Actions shell.
- Make the interactive Status screen human-readable and remove the stale
  `v0.3` status text.
- Replace the old v0.3.2 release-note file with current v0.4.0 RC4 notes.
- Keep the validated SavedVariables workaround unchanged.


## 0.4.0 RC3

- Clarify the custom license.
- Allow forks, modifications, and publication of modified versions.
- Require clear attribution to Simon Ahnfeldt Nielsen.
- Require modified releases to identify themselves as modified/unofficial.
- Prohibit mirrors and redistribution of unchanged or substantially identical
  official copies without permission.


## 0.4.0 RC2

- Simplify the project license to match the intended rules.
- Set the copyright holder to Simon Ahnfeldt Nielsen.
- Allow use and private modification.
- Require original attribution to remain in modified versions.
- Allow patches, diffs, and pull requests to the official repository.
- Prohibit complete mirrors, reuploads, and redistribution without permission.
- Remove conflicting license wording from the README.


## 0.4.0 RC1

- Add interactive numbered console menu as the default user experience.
- Remember selected WoW installation and account per user.
- Add common Windows/macOS WoW path auto-detection.
- Preserve the existing command-line interface.
- Add native GitHub Actions builds for Windows, Linux, and macOS using PyInstaller.
- Replace MIT with a draft restrictive source-available license template.
- Keep the validated v0.3.2 SavedVariables mechanism unchanged.


## 0.3.2

- Support metadata/dependency-only TOCs that declare SavedVariables but contain no normal Lua/XML entries.
- Append ForeverSVFix restore entries as the only executable TOC files in that case.
- Mark metadata-only targets in `scan` output.
- Add regression tests for metadata-only account and mixed account/per-character TOCs.
- Validated account-wide persistence with RareScanner.
- Validated per-character helper routing with a live character SavedVariables probe.
- Validated mixed account/per-character behavior with Auctionator.


## 0.3.1 RC2

- Patch only TOCs whose primary `## Interface:` explicitly includes Forever interface `16001`.
- Support both dedicated `_Camelot.toc` files and multi-interface TOCs.
- Clean stale RC1 patches from Retail/TBC/Wrath/Mists/etc. TOCs during install/repair.
- Remove stale runtime links/bootstrap files from addon folders no longer targeted.
- Improve `scan` output to show the actual selected TOC filename and unique addon-folder count.
- Extend `doctor` to report stale patches on non-Forever TOCs.


## 0.3.0

- Add conservative per-character SavedVariables restoration.
- Add `doctor` command.
- Add `repair` alias for idempotent refresh after addon updates/new characters.
- Automatically migrate v0.2 TOC markers to v0.3.
- Preserve versioned TOC and SavedVariables safety backups.
- Keep the verified live-directory account-wide mechanism unchanged.

## 0.2.0

- Replace the failed central bootstrap design with direct per-addon TOC injection.
- Restore live account-wide SavedVariables before normal addon code.
- Verified on the diagnostic probe and RareScanner.

## 0.1.x

- Experimental bootstrap/dependency prototypes.
- Not suitable for use.
