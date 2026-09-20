# ForeverSVFix

ForeverSVFix is a temporary workaround for the **World of Warcraft: Forever beta** bug where addon SavedVariables are written correctly but are not restored by the client's normal SavedVariables loader.

It is not an addon settings manager and it does not invent a new save format. It makes WoW execute the same live SavedVariables files through the ordinary addon-file loader, which is still working.

> [!WARNING]
> **Use ForeverSVFix at your own risk.**
>
> ForeverSVFix is an unofficial workaround for a bug in the WoW Forever beta.
> It modifies addon `.toc` files and creates filesystem links inside the WoW
> installation. Safety backups are created before install/repair operations,
> but **no guarantee is made that ForeverSVFix will work with every addon or
> every WoW installation**.
>
> **Linux/Wine is the only platform currently validated in-game.**
> Windows and macOS builds are provided for testing but have **not yet been
> validated with native WoW Forever installations**.
>
> Keep your own backups of anything you consider important. Simon Ahnfeldt
> Nielsen accepts no responsibility for lost settings, broken addon
> configurations, or other damage resulting from use of ForeverSVFix.

## Simple guide

If you just want your addon settings to save properly, this is the section you need.

You do **not** need Python when using a standalone ForeverSVFix release.

### Install ForeverSVFix

1. **Close World of Warcraft completely.**
2. Download the ForeverSVFix file for your operating system from the GitHub
   **Releases** page.
3. Start ForeverSVFix.
4. The first time you run it, ForeverSVFix may ask where WoW Forever is
   installed. Select the `_classic_beta_` folder.
5. Choose:

```text
1. Install / refresh ForeverSVFix
```

6. When it finishes, choose:

```text
4. Doctor / check installation
```

You want to see:

```text
Active installation checks: OK
No repair needed.
```

You can now close ForeverSVFix and start World of Warcraft normally.

### When you install a new addon

ForeverSVFix can only fix a new addon after World of Warcraft has created that
addon's SavedVariables files.

When you install a new addon:

1. Install the addon normally.
2. Make sure the addon is **enabled** in WoW.
3. Log into a character at least once.
4. If the addon has settings, opening its settings or changing one setting is
   a good idea.
5. **Exit World of Warcraft completely.**
6. Start ForeverSVFix.
7. Choose:

```text
2. Repair after addon updates
```

Then start WoW again.

If ForeverSVFix does not detect the addon, make sure it was enabled and that
you actually entered the game with it once before running Repair.

### When you update an addon

Addon updaters can replace files that ForeverSVFix patched.

After updating addons:

1. Close WoW.
2. Start ForeverSVFix.
3. Choose:

```text
2. Repair after addon updates
```

That is all you normally need to do.

### If something seems wrong

Close WoW, start ForeverSVFix, and choose:

```text
4. Doctor / check installation
```

If Doctor says a refresh is needed, choose:

```text
2. Repair after addon updates
```

### Uninstall ForeverSVFix

1. **Close World of Warcraft completely.**
2. Start ForeverSVFix.
3. Choose:

```text
8. Uninstall ForeverSVFix
```

4. Confirm when asked.

ForeverSVFix removes the changes it made to your addon files.

It does **not** delete your normal WoW SavedVariables or your ForeverSVFix
safety backups.

### The four things to remember

```text
First install:
Close WoW -> start ForeverSVFix -> press 1

Installed or updated an addon:
Enable it -> enter WoW once -> close WoW -> press 2

Something seems wrong:
Close WoW -> start ForeverSVFix -> press 4

Uninstall:
Close WoW -> start ForeverSVFix -> press 8
```

## Status

**Release candidate: v0.4.0 RC7**

Verified in-game on Forever for account-wide SavedVariables:

- a minimal diagnostic addon persisted `12345 → 12346 → 12347` across repeated `/reload`s;
- RareScanner retained a changed setting across `/reload`, logout/login, and a full client restart.

Per-character support is included and has been validated in-game on Forever.


## Validated in-game

The following behavior has been verified on WoW Forever 1.60.1 under Linux/Wine:

- Account-wide SavedVariables:
  - minimal diagnostic counter persisted across repeated `/reload`s;
  - RareScanner retained changed settings across `/reload`, logout/login, and a full client restart.
- Per-character SavedVariables:
  - the generated character helper loaded the correct Yawa-Wahala character store;
  - a direct probe value in the live per-character SavedVariables file was restored in-game.
- Mixed account + per-character addon:
  - Auctionator retained its settings across relogging with both restore paths active.

The underlying bug/workaround model is therefore validated for all three cases:
account-wide, per-character, and mixed SavedVariables.

## How it works

### Account-wide SavedVariables

For an addon such as:

```text
Interface/AddOns/RareScanner/RareScanner.toc
WTF/Account/<account>/SavedVariables/RareScanner.lua
```

ForeverSVFix creates a directory link:

```text
Interface/AddOns/RareScanner/ForeverSVFixData
    -> WTF/Account/<account>/SavedVariables
```

and inserts this before the addon's normal files:

```text
ForeverSVFixData\RareScanner.lua
```

Forever's broken SavedVariables stage has already happened by the time TOC files execute. The live `.lua` therefore restores the database before the addon's normal code initializes.

Because the link points at the directory rather than one inode/file, WoW can rotate/recreate `.lua` files normally and the next reload still sees the newest file.

### Per-character SavedVariables

Per-character paths differ by character, so loading them all would be unsafe.

v0.3 generates a tiny load-on-demand helper for each `(addon, character)` pair and injects `ForeverSVFixCharacter.lua` into the affected addon. At load time it matches the current player/realm against discovered character folders and loads only one matching helper.

If matching is ambiguous, it **refuses to restore per-character data** and prints a warning instead of risking another character's settings.

## Standalone downloads

The release workflow builds separate standalone downloads for:

- Windows x64
- Linux x86_64
- macOS Intel
- macOS Apple Silicon

These builds bundle Python with ForeverSVFix, so end users do not need to
install Python themselves.

Windows and macOS standalone builds are currently **untested in-game** and
should be considered experimental until they have been validated with native
WoW Forever installations.

Because the binaries are not code-signed, Windows SmartScreen or macOS
Gatekeeper may show a warning. The source code and build workflow are public so
users can inspect exactly how the binaries are produced.

## Platforms

- Linux: directory symlinks
- macOS: directory symlinks
- Windows: directory symlink where permitted, otherwise an NTFS directory junction

The full account-wide, per-character, and mixed SavedVariables workaround has
been validated on Linux/Wine. Windows and macOS have **not yet been validated
in-game** and need community testing.

## Requirements

### Standalone releases

Standalone releases do **not** require Python.

Download the build for your operating system from GitHub Releases and run it.

### Running from source

Running `forever_sv_fix.py` directly requires Python 3.10+.

No network access, service, daemon, or telemetry is required by ForeverSVFix
itself. Windows may use a normal NTFS junction if a symbolic link cannot be
created.

## Advanced / command-line usage

**Close WoW first.**

Scan what would be changed:

```bash
python3 forever_sv_fix.py --wow "/path/to/World of Warcraft/_classic_beta_" scan
```

Install:

```bash
python3 forever_sv_fix.py --wow "/path/to/World of Warcraft/_classic_beta_" install
```

If more than one WoW account directory exists:

```bash
python3 forever_sv_fix.py \
  --wow "/path/to/World of Warcraft/_classic_beta_" \
  --account "ACCOUNT#1" \
  install
```

## After addon updates

Addon managers can replace `.toc` files. Check:

```bash
python3 forever_sv_fix.py --wow "/path/to/_classic_beta_" doctor
```

If it reports missing patches or newly compatible addons:

```bash
python3 forever_sv_fix.py --wow "/path/to/_classic_beta_" repair
```

`repair` and `install` are intentionally the same idempotent refresh operation.

Also run `repair` after a new character has created its SavedVariables for the first time.

## Uninstall

Close WoW, then:

```bash
python3 forever_sv_fix.py --wow "/path/to/_classic_beta_" uninstall
```

This removes ForeverSVFix's TOC entries, directory links, generated character bootstraps, and generated helper addons.

It does **not** delete your SavedVariables or safety backups.

## Safety

Before each install/repair, ForeverSVFix creates a new backup generation under:

```text
WTF/ForeverSVFix/backups/
```

It backs up every TOC it patches and every existing `.lua` / `.lua.bak` file it relies on.

ForeverSVFix does not rewrite the live SavedVariables contents.

## Known limitations

- The tool currently relies on the normal convention that an addon's SavedVariables file is named after its addon folder/TOC addon name.
- An addon update can remove the injected TOC entries; run `doctor`/`repair`.
- A newly installed addon or newly created character may need one normal save before a matching `.lua` exists; run `repair` afterward.
- Per-character folder matching is deliberately conservative. Ambiguous matches are skipped.
- EllesmereUI explicitly disables its profile system on the Forever beta. ForeverSVFix cannot persist settings that an addon itself intentionally refuses to write.
- This workaround should be removed once Blizzard fixes Forever's SavedVariables loader.

## Troubleshooting

Run:

```bash
python3 forever_sv_fix.py --wow "/path/to/_classic_beta_" doctor
```

If a per-character restore cannot be matched safely, ForeverSVFix prints a yellow warning in WoW chat. A failed helper load prints a red warning.

## Project scope

ForeverSVFix is a temporary compatibility workaround for a beta client. It is not affiliated with Blizzard Entertainment or individual addon authors.


## License

Copyright (c) 2026 Simon Ahnfeldt Nielsen.

You may use, modify, fork, and publish modified versions of ForeverSVFix.

If you publish a modified version, you must:

- clearly state that it is a modified version of ForeverSVFix;
- retain credit to **Simon Ahnfeldt Nielsen** as the original author; and
- not claim or imply that your modified version is an official release.

You may not simply mirror or re-upload an **unchanged official copy** of
ForeverSVFix or its official release files elsewhere without permission.

Linking to the official repository and official releases is allowed.

See [`LICENSE`](LICENSE) for the full terms.

## Forever TOC selection

v0.3.1 no longer patches every flavor-specific TOC shipped in an addon folder.

A TOC is considered relevant to Forever only when its primary metadata contains:

```text
## Interface: ... 16001 ...
```

This supports both dedicated Forever/Camelot TOCs and multi-interface TOCs. Examples:

- `BetterBlizzFrames_Camelot.toc` → `16001`
- `Prat-3.0_Camelot.toc` → `16001`
- `FishingBuddy.toc` → `20506, 16001, ...`
- `RXPGuides.toc` → includes `16001`

TOCs for Retail, TBC, Wrath, etc. are ignored. `repair` also removes stale patches that older release candidates placed in irrelevant flavor TOCs.


## Metadata-only TOCs

Some addons declare SavedVariables in a TOC that contains no normal Lua/XML file entries. This is valid. ForeverSVFix v0.3.2 supports these manifests by appending the live restore entry as the TOC's only executable file instead of treating the TOC as invalid.


## Interactive console menu

Normal users no longer need to memorize commands. Launch ForeverSVFix without
arguments:

```bash
python3 forever_sv_fix.py
```

or use the platform wrapper/executable.

The menu provides numbered options for install/refresh, repair, scan, doctor,
status, changing the WoW installation/account, uninstall, and exit.

The selected WoW path/account are remembered in the user's normal per-platform
configuration directory.

The existing command-line interface remains available for scripting and
advanced users.

## WoW path discovery

ForeverSVFix checks common native locations on Windows and macOS and remembers
manually selected locations. Linux/Wine installations vary too widely to guess
reliably, so the first launch may ask for the `_classic_beta_` folder.

## Native platform status

The filesystem implementation supports:

- Linux: directory symlinks (validated in-game).
- macOS: directory symlinks (implementation present; native WoW testing still needed).
- Windows: directory symlinks when available, falling back to NTFS directory
  junctions that normally do not require Developer Mode/admin privileges
  (implementation present; native WoW testing still needed).

The SavedVariables workaround itself has been validated on Linux/Wine.
**Windows and macOS have not yet been tested in-game.** Their implementations
exist and are covered by automated tests/builds, but should remain marked as
experimental until native WoW users confirm the behavior.

