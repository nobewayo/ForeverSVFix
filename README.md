# ForeverSVFix

ForeverSVFix is a temporary workaround for a **World of Warcraft: Forever beta** bug where addon SavedVariables are written correctly but are not restored by the client's normal SavedVariables loader.

It restores those existing SavedVariables before addon code starts. It does not create a new save format or replace an addon's settings system.

> [!IMPORTANT]
> **ForeverSVFix does not need to stay open while you play WoW.**
>
> Run it when you need to **install, repair, check, or uninstall** the workaround. Once Install or Repair has finished, close ForeverSVFix and start WoW normally.
>
> **There is no background service or process that needs to remain running.**

> [!WARNING]
> **Use ForeverSVFix at your own risk.**
>
> ForeverSVFix is an unofficial workaround for a beta client bug. It modifies addon `.toc` files and creates filesystem links inside the WoW installation. Safety backups are created before changes are made.
>
> Linux/Wine is currently the only platform validated in-game. Windows and macOS builds are available but should be considered experimental until they have been tested with native WoW Forever installations.
>
> ForeverSVFix is not affiliated with, endorsed by, or approved by Blizzard Entertainment. World of Warcraft and Blizzard are trademarks of Blizzard Entertainment.

## Download and install

You do **not** need Python when using a release build.

Download the latest version from the [Releases](https://github.com/nobewayo/ForeverSVFix/releases) page.

| Platform | Download |
| --- | --- |
| Windows x64 | `ForeverSVFix-Windows-x64.exe` |
| Linux x86_64 | `ForeverSVFix-Linux-x86_64.AppImage` |
| macOS Intel | `ForeverSVFix-macOS-Intel` |
| macOS Apple Silicon | `ForeverSVFix-macOS-Apple-Silicon` |

Linux users should normally use the AppImage.

1. **Close World of Warcraft completely.**
2. Start ForeverSVFix.
3. If asked, select your WoW Forever `_classic_beta_` folder.
4. Choose **1. Install / refresh ForeverSVFix**.
5. Choose **4. Doctor / check installation**.

A healthy installation should report:

```text
Active installation checks: OK
No repair needed.
```

Then **close ForeverSVFix** and start WoW normally.

**You do not need to leave ForeverSVFix running in the background.** The workaround is already installed in the WoW/addon files.

### Linux AppImage

If the AppImage does not start when double-clicked, mark it as executable:

```bash
chmod +x ForeverSVFix-Linux-x86_64.AppImage
./ForeverSVFix-Linux-x86_64.AppImage
```

A raw Linux standalone binary is also provided as a fallback.

## Normal use

ForeverSVFix only needs to be opened when you want it to do something:

```text
First installation:
Close WoW -> start ForeverSVFix -> option 1 -> close ForeverSVFix -> start WoW

After updating an addon:
Close WoW -> start ForeverSVFix -> option 2 -> close ForeverSVFix -> start WoW

Something seems wrong:
Close WoW -> start ForeverSVFix -> option 4

Uninstall:
Close WoW -> start ForeverSVFix -> option 8
```

When installing a **new addon**, WoW must first create that addon's SavedVariables file. Enable the addon, enter the game once, optionally change one of its settings, then exit WoW completely and run **2. Repair after addon updates**.

Addon updates may replace files patched by ForeverSVFix, so running Repair after addon updates is recommended.

Uninstalling ForeverSVFix removes the changes it created but does **not** delete your normal WoW SavedVariables or safety backups.

## EllesmereUI support

ForeverSVFix can also restore **Profiles & Presets** functionality in EllesmereUI on WoW Forever.

EllesmereUI contains its normal profile system on Forever but disables it because of the SavedVariables bug. When ForeverSVFix recognizes a supported EllesmereUI installation, it adds a small local compatibility shim that disables only that SavedVariables-related safety gate.

It does **not** redistribute or replace EllesmereUI and does not disable other Forever-specific compatibility restrictions.

This has been validated in-game with **EllesmereUI v9.2.1**, including profile creation, profile switching, `/reload`, relogging, and full client restarts.

After updating EllesmereUI, close WoW and run **Repair** again.

## Current status

**Current release candidate: v0.4.0 RC10**

The workaround has been validated in-game on WoW Forever under Linux/Wine for:

- account-wide SavedVariables;
- per-character SavedVariables;
- addons using both types at the same time;
- settings persistence across `/reload`, relogging, and full client restarts;
- EllesmereUI profile persistence.

Testing included RareScanner, Auctionator, direct diagnostic SavedVariables, and EllesmereUI v9.2.1.

### Platform status

| Platform | Status |
| --- | --- |
| Linux / Wine | Validated in-game |
| Windows | Implemented, native WoW testing still needed |
| macOS | Implemented, native WoW testing still needed |

Windows builds use directory symlinks where available and fall back to an NTFS directory junction when needed.

The standalone binaries are not code-signed, so Windows SmartScreen or macOS Gatekeeper may display a warning.

## How it works

Normally, WoW restores an addon's SavedVariables before loading the addon. On the Forever beta, that restore stage is currently broken even though WoW still writes the SavedVariables files correctly.

ForeverSVFix links the addon's live SavedVariables directory into the addon and adds the appropriate SavedVariables file to the addon's TOC before its normal code.

For example:

```text
WTF/Account/<account>/SavedVariables/RareScanner.lua
```

is made available through:

```text
Interface/AddOns/RareScanner/ForeverSVFixData/RareScanner.lua
```

The existing SavedVariables file is then executed through WoW's normal addon-file loader before RareScanner initializes.

Per-character SavedVariables use a small generated load-on-demand helper that selects only the current character. If ForeverSVFix cannot identify the character safely, it refuses to restore that data rather than risk loading another character's settings.

ForeverSVFix does **not** rewrite the contents of your SavedVariables files.

## Update checks and privacy

ForeverSVFix checks the public GitHub Releases API for newer versions when you start it.

Automatic checks are cached for 24 hours and include both release candidates and stable releases. No update is downloaded or installed automatically.

You can also choose:

```text
9. Check for ForeverSVFix updates
```

The update check sends only a normal HTTPS request to GitHub. ForeverSVFix does **not** send WoW paths, account names, addon lists, SavedVariables, or telemetry.

All SavedVariables repair functionality works without internet access.

Because ForeverSVFix does not stay running in the background, update notifications are shown the next time you open it.

## Running from source

Running `forever_sv_fix.py` directly requires **Python 3.10+**.

Start the interactive menu with:

```bash
python3 forever_sv_fix.py
```

Common command-line operations:

```bash
python3 forever_sv_fix.py --wow "/path/to/_classic_beta_" scan
python3 forever_sv_fix.py --wow "/path/to/_classic_beta_" install
python3 forever_sv_fix.py --wow "/path/to/_classic_beta_" repair
python3 forever_sv_fix.py --wow "/path/to/_classic_beta_" doctor
python3 forever_sv_fix.py --wow "/path/to/_classic_beta_" uninstall
python3 forever_sv_fix.py check-update
```

If more than one WoW account exists, add `--account "ACCOUNT#1"`.

## Safety and limitations

Before each install or repair, ForeverSVFix creates a safety backup under:

```text
WTF/ForeverSVFix/backups/
```

Current limitations:

- newly installed addons may need to enter the game once before they can be detected;
- addon updates can remove ForeverSVFix patches, requiring Repair;
- ambiguous per-character folder matches are deliberately skipped;
- EllesmereUI compatibility currently targets the known v9.2.1 layout and fails safely if an unfamiliar layout is detected;
- Windows and macOS still need native in-game validation.

ForeverSVFix is intended only as a temporary workaround and should no longer be needed once Blizzard fixes the Forever SavedVariables loader.

## Development disclosure

AI tools were used during development to assist with coding, review, testing support, and documentation.

Development decisions, iteration, and in-game validation were performed manually by the project author.

## License

Copyright © 2026 Simon Ahnfeldt Nielsen.

You may use, modify, fork, and publish modified versions of ForeverSVFix, provided modified releases clearly identify themselves as unofficial and retain credit to Simon Ahnfeldt Nielsen as the original author.

Unchanged official releases may not be mirrored or re-uploaded elsewhere without permission. Linking to the official repository or releases is allowed.

See [`LICENSE`](LICENSE) for the full terms.
