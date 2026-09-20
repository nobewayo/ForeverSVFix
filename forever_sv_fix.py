#!/usr/bin/env python3
"""
ForeverSVFix 1.0.0

Temporary workaround for the World of Warcraft: Forever beta SavedVariables
loading bug.

Verified on Forever:
- WoW writes SavedVariables correctly.
- Forever's normal SavedVariables loader fails to restore them.
- Executing the live SavedVariables .lua as an ordinary TOC file, after the
  broken loader stage but before normal addon code, restores account-wide data.

v0.3 adds per-character restoration through a small generated load-on-demand
addon for each (addon, character) pair. The target addon's injected bootstrap
selects only the current character and loads that helper before normal addon
code executes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import certifi
except ImportError:
    certifi = None

VERSION = "1.0.0"
DATA_DIR = "ForeverSVFixData"
CHAR_BOOTSTRAP = "ForeverSVFixCharacter.lua"
ELLESMERE_COMPAT = "ForeverSVFixEllesmereUI.lua"
STATE_DIR_NAME = "ForeverSVFix"
STATE_FILE_NAME = "state-v3.json"
MARKER = "X-ForeverSVFix"
MARKER_VERSION = "4"
INTERFACE = "16001"

GITHUB_REPO = "nobewayo/ForeverSVFix"
GITHUB_RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=20"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"
UPDATE_CHECK_INTERVAL = 24 * 60 * 60
UPDATE_CHECK_TIMEOUT = 2.5
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-rc(\d+))?$")

SV_RE = re.compile(r"^\s*##\s*SavedVariables\s*:\s*(.*?)\s*$", re.IGNORECASE)
SVPC_RE = re.compile(r"^\s*##\s*SavedVariablesPerCharacter\s*:\s*(.*?)\s*$", re.IGNORECASE)
INTERFACE_RE = re.compile(r"^\s*##\s*Interface\s*:\s*(.*?)\s*$", re.IGNORECASE)
MARKER_ANY_RE = re.compile(r"^\s*##\s*X-ForeverSVFix\s*:\s*\d+\s*$", re.IGNORECASE)
FILE_LINE_RE = re.compile(r"^\s*[^#\s].*$")


class FixError(RuntimeError):
    pass


@dataclass(frozen=True)
class TocInfo:
    path: Path
    addon: str
    account_saved: bool
    character_saved: bool
    interfaces: tuple[str, ...]


@dataclass(frozen=True)
class CharacterStore:
    realm_folder: str
    character_folder: str
    saved_dir: Path


@dataclass(frozen=True)
class PerCharTarget:
    addon: str
    toc: Path
    stores: tuple[CharacterStore, ...]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def split_vars(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def inspect_toc(path: Path) -> TocInfo:
    account = False
    character = False
    interfaces: list[str] = []

    for line in read_text(path).splitlines():
        m = SV_RE.match(line)
        if m and split_vars(m.group(1)):
            account = True

        m = SVPC_RE.match(line)
        if m and split_vars(m.group(1)):
            character = True

        m = INTERFACE_RE.match(line)
        if m:
            interfaces.extend(split_vars(m.group(1)))

    return TocInfo(
        path,
        path.parent.name,
        account,
        character,
        tuple(interfaces),
    )


def is_forever_toc(info: TocInfo) -> bool:
    # Forever's current interface number is 16001. Some addons use a dedicated
    # _Camelot TOC, while others include 16001 in a multi-interface base TOC.
    # The primary ## Interface field is the reliable common signal.
    return INTERFACE in info.interfaces


def discover_all_tocs(addons_dir: Path) -> list[TocInfo]:
    result: list[TocInfo] = []
    for folder in sorted(addons_dir.iterdir(), key=lambda p: p.name.lower()):
        if not folder.is_dir() or folder.name.startswith("ForeverSVFixPC_"):
            continue
        for toc in sorted(folder.glob("*.toc"), key=lambda p: p.name.lower()):
            try:
                info = inspect_toc(toc)
            except (OSError, UnicodeError) as exc:
                print(f"WARNING: cannot read {toc}: {exc}", file=sys.stderr)
                continue
            if info.account_saved or info.character_saved:
                result.append(info)
    return result


def discover_tocs(addons_dir: Path) -> list[TocInfo]:
    return [info for info in discover_all_tocs(addons_dir) if is_forever_toc(info)]

def validate_wow(path: Path) -> Path:
    path = path.expanduser().resolve()
    if not (path / "Interface" / "AddOns").is_dir():
        raise FixError(f"Not a WoW install (missing Interface/AddOns): {path}")
    if not (path / "WTF" / "Account").is_dir():
        raise FixError(f"Not a WoW install (missing WTF/Account): {path}")
    return path


def choose_account(wow: Path, requested: str | None) -> Path:
    root = wow / "WTF" / "Account"
    accounts = sorted(
        [p for p in root.iterdir() if p.is_dir() and (p / "SavedVariables").is_dir()],
        key=lambda p: p.name.lower(),
    )
    if requested:
        for p in accounts:
            if p.name == requested:
                return p
        raise FixError(f"Account not found: {requested}")
    if len(accounts) == 1:
        return accounts[0]
    if not accounts:
        raise FixError("No account-wide SavedVariables directory found.")
    raise FixError(
        "Multiple accounts found; use --account NAME. Found: "
        + ", ".join(p.name for p in accounts)
    )


def character_stores(account: Path) -> list[CharacterStore]:
    result: list[CharacterStore] = []
    account_sv = account / "SavedVariables"
    for saved_dir in account.rglob("SavedVariables"):
        if saved_dir == account_sv or not saved_dir.is_dir():
            continue
        rel = saved_dir.relative_to(account)
        parts = rel.parts
        # Expected current Forever layout:
        # <realm-folder>/<character-folder>/SavedVariables
        if len(parts) < 3 or parts[-1] != "SavedVariables":
            continue
        result.append(CharacterStore(parts[-3], parts[-2], saved_dir))
    result.sort(key=lambda c: (c.realm_folder.lower(), c.character_folder.lower()))
    return result


def lexists(path: Path) -> bool:
    return os.path.lexists(path)


def remove_link(path: Path) -> None:
    if not lexists(path):
        return
    if path.is_symlink():
        path.unlink()
        return
    if platform.system() == "Windows":
        result = subprocess.run(
            ["cmd", "/c", "rmdir", str(path)],
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise FixError(
                f"Could not remove Windows junction {path}: "
                + (result.stdout + result.stderr).strip()
            )
        return
    raise FixError(f"Refusing to remove non-link path: {path}")


def make_dir_link(link: Path, target: Path) -> str:
    if lexists(link):
        remove_link(link)

    if platform.system() != "Windows":
        os.symlink(target, link, target_is_directory=True)
        return "symlink"

    try:
        os.symlink(target, link, target_is_directory=True)
        return "symlink"
    except OSError:
        pass

    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise FixError(
            f"Could not create Windows directory junction {link}: "
            + (result.stdout + result.stderr).strip()
        )
    return "junction"


def state_dir(wow: Path) -> Path:
    return wow / "WTF" / STATE_DIR_NAME


def next_backup_dir(wow: Path) -> Path:
    root = state_dir(wow) / "backups"
    root.mkdir(parents=True, exist_ok=True)
    nums = [int(p.name) for p in root.iterdir() if p.is_dir() and p.name.isdigit()]
    dest = root / f"{max(nums, default=0) + 1:04d}"
    dest.mkdir()
    return dest


def backup_toc(toc: Path, backup: Path) -> None:
    dest = backup / "tocs" / toc.parent.name
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(toc, dest / toc.name)


def backup_file(src: Path, backup: Path, rel_root: Path) -> None:
    if not src.is_file():
        return
    rel = src.relative_to(rel_root)
    dest = backup / "savedvariables" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def backup_saved_pair(src: Path, backup: Path, rel_root: Path) -> None:
    backup_file(src, backup, rel_root)
    bak = src.with_name(src.name + ".bak")
    backup_file(bak, backup, rel_root)


def lua_quote(value: str) -> str:
    return (
        '"'
        + value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        + '"'
    )


def pc_helper_name(addon: str, store: CharacterStore) -> str:
    raw = f"{addon}\0{store.realm_folder}\0{store.character_folder}\0{store.saved_dir}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"ForeverSVFixPC_{digest}"


def generate_pc_helper(
    addons_dir: Path,
    addon: str,
    store: CharacterStore,
) -> tuple[str, Path, str]:
    name = pc_helper_name(addon, store)
    root = addons_dir / name

    if root.exists() or lexists(root):
        # Remove only our generated directory. First detach its link.
        link = root / "Data"
        if lexists(link):
            remove_link(link)
        if root.is_dir():
            shutil.rmtree(root)

    root.mkdir(parents=True)
    link_kind = make_dir_link(root / "Data", store.saved_dir)

    toc = "\n".join(
        [
            f"## Interface: {INTERFACE}",
            f"## Title: ForeverSVFix per-character restore ({addon})",
            "## Notes: Generated by ForeverSVFix. Do not edit.",
            "## LoadOnDemand: 1",
            "",
            f"Data\\{addon}.lua",
            "",
        ]
    )
    write_text(root / f"{name}.toc", toc)
    return name, root, link_kind


def generate_char_bootstrap(
    addon_dir: Path,
    addon: str,
    stores: Iterable[CharacterStore],
) -> tuple[list[dict], list[Path]]:
    entries = []
    helper_dirs = []
    addons_dir = addon_dir.parent

    for store in stores:
        name, helper_dir, link_kind = generate_pc_helper(addons_dir, addon, store)
        entries.append(
            {
                "helper": name,
                "realm_folder": store.realm_folder,
                "character_folder": store.character_folder,
                "saved_dir": str(store.saved_dir),
                "link_kind": link_kind,
            }
        )
        helper_dirs.append(helper_dir)

    lines = [
        "-- Generated by ForeverSVFix. Do not edit.",
        "if not ForeverSVFixPCLoaded then ForeverSVFixPCLoaded = {} end",
        "",
        "local addonKey = " + lua_quote(addon),
        "if not ForeverSVFixPCLoaded[addonKey] then",
        "  local function norm(v)",
        '    if not v then return "" end',
        "    v = tostring(v):lower()",
        '    return (v:gsub("[^%w]", ""))',
        "  end",
        "",
        "  local player, realm",
        '  if UnitFullName then player, realm = UnitFullName("player") end',
        '  if (not player or player == "") and UnitName then player = UnitName("player") end',
        '  if (not realm or realm == "") and GetNormalizedRealmName then realm = GetNormalizedRealmName() end',
        '  if (not realm or realm == "") and GetRealmName then realm = GetRealmName() end',
        "",
        "  local np, nr = norm(player), norm(realm)",
        "  local stores = {",
    ]

    for entry in entries:
        lines.append(
            "    { helper = %s, realm = %s, character = %s },"
            % (
                lua_quote(entry["helper"]),
                lua_quote(entry["realm_folder"]),
                lua_quote(entry["character_folder"]),
            )
        )

    lines += [
        "  }",
        "",
        "  local exact, prefix = {}, {}",
        "  for _, item in ipairs(stores) do",
        "    local nc, nrf = norm(item.character), norm(item.realm)",
        "    if nc == np or (nr ~= '' and nc == (np .. nr)) then",
        "      table.insert(exact, item)",
        "    elseif np ~= '' and nc:find(np, 1, true) == 1 then",
        "      if nr == '' or nc:find(nr, 1, true) then",
        "        table.insert(prefix, item)",
        "      end",
        "    elseif np ~= '' and nrf ~= '' and nrf == nr and nc == np then",
        "      table.insert(exact, item)",
        "    end",
        "  end",
        "",
        "  local chosen",
        "  if #exact == 1 then chosen = exact[1]",
        "  elseif #exact == 0 and #prefix == 1 then chosen = prefix[1] end",
        "",
        "  if chosen then",
        "    local ok, reason",
        "    if C_AddOns and C_AddOns.LoadAddOn then",
        "      ok, reason = C_AddOns.LoadAddOn(chosen.helper)",
        "    elseif LoadAddOn then",
        "      ok, reason = LoadAddOn(chosen.helper)",
        "    end",
        "    if ok then",
        "      ForeverSVFixPCLoaded[addonKey] = chosen.helper",
        "    else",
        '      print("|cffff5555ForeverSVFix:|r could not restore per-character data for "',
        '        .. addonKey .. ": " .. tostring(reason))',
        "    end",
        "  elseif #stores > 0 then",
        '    print("|cffffcc00ForeverSVFix:|r skipped ambiguous per-character restore for "',
        '      .. addonKey .. " (" .. tostring(player or "?") .. "-" .. tostring(realm or "?") .. ")")',
        "  end",
        "end",
        "",
    ]

    write_text(addon_dir / CHAR_BOOTSTRAP, "\n".join(lines))
    return entries, helper_dirs


def cleanup_generated_pc(addons_dir: Path) -> None:
    for root in list(addons_dir.glob("ForeverSVFixPC_*")):
        if not root.is_dir():
            continue
        link = root / "Data"
        if lexists(link):
            remove_link(link)
        shutil.rmtree(root)


def owned_injected_line(line: str, addon: str) -> bool:
    stripped = line.strip()
    return (
        stripped == f"{DATA_DIR}\\{addon}.lua"
        or stripped == CHAR_BOOTSTRAP
        or stripped == ELLESMERE_COMPAT
    )


def ellesmere_profile_compat_supported(path: Path) -> bool:
    """Return true only for the EllesmereUI layout this compatibility shim knows.

    EllesmereUI 9.2.1 ships the full profile implementation on Forever, but
    EllesmereUI_Lite.lua sets FOREVER_SV_BUG=true before the rest of the suite
    loads. The shim is safe only when the expected load-order anchors are
    present, so unknown/future layouts fail closed and are left untouched.
    """
    if path.parent.name != "EllesmereUI" or path.name != "EllesmereUI.toc":
        return False
    try:
        text = read_text(path)
    except (OSError, UnicodeError):
        return False
    required = (
        "EllesmereUI_ClientGate.lua",
        "EllesmereUI_Lite.lua",
        "EllesmereUI_Profiles.lua",
        "EllesmereUI_ForeverNotice.lua",
    )
    return all(item in text for item in required)


def generate_ellesmere_compat(addon_dir: Path) -> Path:
    path = addon_dir / ELLESMERE_COMPAT
    write_text(
        path,
        "\n".join(
            [
                "-- Generated by ForeverSVFix. Do not edit.",
                "-- EllesmereUI keeps its profile system in the Forever build, but",
                "-- deliberately disables it while Blizzard's SavedVariables loader is broken.",
                "-- ForeverSVFix restores those live SavedVariables before addon code runs,",
                "-- so disable only EllesmereUI's SavedVariables safety gate.",
                "if EllesmereUI and EllesmereUI.IS_FOREVER then",
                "  EllesmereUI.FOREVER_SV_BUG = false",
                "  EllesmereUI.FOREVER_SV_FIX_ACTIVE = true",
                "end",
                "",
            ]
        ),
    )
    return path


def patch_toc(
    path: Path,
    addon: str,
    inject_account: bool,
    inject_character: bool,
    inject_ellesmere_compat: bool = False,
) -> bool:
    original = read_text(path)
    lines = original.splitlines()

    # Remove any previous ForeverSVFix metadata and owned file entries.
    cleaned = []
    for line in lines:
        if MARKER_ANY_RE.match(line):
            continue
        if owned_injected_line(line, addon):
            continue
        # v0.1 dependency-era leftovers, if present.
        if line.strip().lower().startswith("## dependencies:") and "ForeverSVFix" in line:
            prefix, value = line.split(":", 1)
            deps = [d.strip() for d in value.split(",") if d.strip()]
            deps = [d for d in deps if d.lower() != "foreversvfix"]
            if deps:
                cleaned.append(prefix + ": " + ", ".join(deps))
            continue
        cleaned.append(line)
    lines = cleaned

    marker_at = 0
    for i, line in enumerate(lines):
        if line.lstrip().startswith("##"):
            marker_at = i + 1
    lines.insert(marker_at, f"## {MARKER}: {MARKER_VERSION}")

    first_file = None
    for i, line in enumerate(lines):
        if FILE_LINE_RE.match(line):
            first_file = i
            break

    injected = []
    if inject_account:
        injected.append(f"{DATA_DIR}\\{addon}.lua")
    if inject_character:
        injected.append(CHAR_BOOTSTRAP)

    if first_file is None:
        # Metadata/dependency-only TOCs are valid. In that case our restore
        # entries become the TOC's only executable files.
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.extend(injected)
    else:
        for line in reversed(injected):
            lines.insert(first_file, line)

    if inject_ellesmere_compat:
        # EllesmereUI_Lite.lua creates the FOREVER_SV_BUG safety gate. The
        # compatibility shim must run immediately AFTER Lite creates that gate
        # and BEFORE the rest of EllesmereUI reads it. Never guess on an
        # unfamiliar TOC layout.
        lite_at = next(
            (i for i, line in enumerate(lines) if line.strip() == "EllesmereUI_Lite.lua"),
            None,
        )
        if lite_at is None:
            raise FixError(
                "EllesmereUI compatibility requested but EllesmereUI_Lite.lua "
                f"was not found in {path}"
            )
        lines.insert(lite_at + 1, ELLESMERE_COMPAT)

    updated = "\n".join(lines) + ("\n" if original.endswith(("\n", "\r")) else "")
    if updated == original:
        return False
    write_text(path, updated)
    return True


def unpatch_toc(path: Path, addon: str) -> bool:
    try:
        original = read_text(path)
    except FileNotFoundError:
        return False

    out = []
    changed = False
    for line in original.splitlines():
        if MARKER_ANY_RE.match(line) or owned_injected_line(line, addon):
            changed = True
            continue
        if line.strip().lower().startswith("## dependencies:") and "ForeverSVFix" in line:
            prefix, value = line.split(":", 1)
            deps = [d.strip() for d in value.split(",") if d.strip()]
            filtered = [d for d in deps if d.lower() != "foreversvfix"]
            changed = True
            if filtered:
                out.append(prefix + ": " + ", ".join(filtered))
            continue
        out.append(line)

    if not changed:
        return False

    updated = "\n".join(out) + ("\n" if original.endswith(("\n", "\r")) else "")
    write_text(path, updated)
    return True



def reconcile_old_patches(
    addons_dir: Path,
    target_tocs: set[Path],
    target_folders: set[Path],
) -> int:
    """Remove ForeverSVFix patches/runtime files from TOCs no longer relevant.

    RC1 patched every flavor TOC. RC2+ patches only TOCs whose primary
    ## Interface explicitly contains 16001.
    """
    cleaned = 0

    for info in discover_all_tocs(addons_dir):
        if info.path in target_tocs:
            continue

        try:
            toc_text = read_text(info.path)
        except Exception:
            continue

        if "X-ForeverSVFix" in toc_text:
            if unpatch_toc(info.path, info.addon):
                cleaned += 1

    # Remove runtime artifacts from addon folders which no longer contain any
    # Forever-relevant target TOC.
    for folder in addons_dir.iterdir():
        if not folder.is_dir() or folder.name.startswith("ForeverSVFixPC_"):
            continue
        if folder in target_folders:
            continue

        link = folder / DATA_DIR
        if lexists(link):
            remove_link(link)

        bootstrap = folder / CHAR_BOOTSTRAP
        if bootstrap.is_file():
            bootstrap.unlink()

        compat = folder / ELLESMERE_COMPAT
        if compat.is_file():
            compat.unlink()

    return cleaned


def save_state(wow: Path, state: dict) -> None:
    d = state_dir(wow)
    d.mkdir(parents=True, exist_ok=True)
    (d / STATE_FILE_NAME).write_text(
        json.dumps(state, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_state(wow: Path) -> dict | None:
    p = state_dir(wow) / STATE_FILE_NAME
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def find_targets(wow: Path, account: Path):
    addons_dir = wow / "Interface" / "AddOns"
    account_sv = account / "SavedVariables"
    stores = character_stores(account)
    infos = discover_tocs(addons_dir)

    result = []
    for info in infos:
        account_file = account_sv / f"{info.addon}.lua"
        account_ok = info.account_saved and account_file.is_file()

        pc_stores = tuple(
            s for s in stores
            if info.character_saved and (s.saved_dir / f"{info.addon}.lua").is_file()
        )
        if account_ok or pc_stores:
            result.append((info, account_ok, pc_stores))
    return result


def scan(wow: Path, account_name: str | None) -> int:
    account = choose_account(wow, account_name)
    targets = find_targets(wow, account)

    print(f"WoW:     {wow}")
    print(f"Account: {account.name}")
    print()
    account_count = sum(1 for _, a, _ in targets if a)
    pc_count = sum(1 for _, _, pcs in targets if pcs)
    unique_addons = len({info.path.parent for info, _, _ in targets})
    print(f"Forever-compatible TOCs with account data:  {account_count}")
    print(f"Forever-compatible TOCs with per-char data: {pc_count}")
    print(f"Total Forever-compatible TOCs to patch:     {len(targets)}")
    print(f"Unique addon folders:                        {unique_addons}")
    print()

    metadata_only = 0
    for info, account_ok, pcs in targets:
        modes = []
        if account_ok:
            modes.append("account")
        if pcs:
            modes.append(f"per-char:{len(pcs)}")

        toc_text = read_text(info.path)
        has_file_entry = any(
            FILE_LINE_RE.match(line)
            for line in toc_text.splitlines()
        )
        suffix = " [metadata-only]" if not has_file_entry else ""
        if not has_file_entry:
            metadata_only += 1
        if account_ok and ellesmere_profile_compat_supported(info.path):
            suffix += " [EllesmereUI profiles enabled]"

        print(f"  {info.addon} [{', '.join(modes)}]  ({info.path.name}){suffix}")
        for s in pcs:
            print(f"    - {s.realm_folder}/{s.character_folder}")

    if metadata_only:
        print()
        print(f"Metadata-only TOCs supported: {metadata_only}")
    return 0


def install(wow: Path, account_name: str | None) -> int:
    account = choose_account(wow, account_name)
    account_root = account
    addons_dir = wow / "Interface" / "AddOns"
    account_sv = account / "SavedVariables"
    targets = find_targets(wow, account)

    if not targets:
        raise FixError("No compatible existing SavedVariables files were found.")

    target_tocs = {info.path for info, _, _ in targets}
    target_folders = {info.path.parent for info, _, _ in targets}

    stale_cleaned = reconcile_old_patches(
        addons_dir,
        target_tocs,
        target_folders,
    )

    backup = next_backup_dir(wow)
    cleanup_generated_pc(addons_dir)

    patched = []
    linked_account_dirs: dict[str, str] = {}
    generated_pc_dirs: set[str] = set()
    char_bootstraps: set[str] = set()
    ellesmere_compat_files: set[str] = set()

    # Generate per-addon character bootstraps first. Multiple flavor TOCs in the
    # same folder share the same generated file.
    per_addon_pc: dict[Path, tuple[str, tuple[CharacterStore, ...]]] = {}
    for info, _, pcs in targets:
        if pcs:
            per_addon_pc[info.path.parent] = (info.addon, pcs)

    pc_meta: dict[str, list[dict]] = {}
    for addon_dir, (addon, pcs) in per_addon_pc.items():
        entries, helper_dirs = generate_char_bootstrap(addon_dir, addon, pcs)
        pc_meta[str(addon_dir)] = entries
        char_bootstraps.add(str(addon_dir / CHAR_BOOTSTRAP))
        generated_pc_dirs.update(str(p) for p in helper_dirs)

    try:
        for info, account_ok, pcs in targets:
            backup_toc(info.path, backup)

            if account_ok:
                src = account_sv / f"{info.addon}.lua"
                backup_saved_pair(src, backup, account_root)

                addon_dir = info.path.parent
                if str(addon_dir) not in linked_account_dirs:
                    kind = make_dir_link(addon_dir / DATA_DIR, account_sv)
                    linked_account_dirs[str(addon_dir)] = kind

            for store in pcs:
                backup_saved_pair(
                    store.saved_dir / f"{info.addon}.lua",
                    backup,
                    account_root,
                )

            enable_ellesmere_compat = (
                account_ok and ellesmere_profile_compat_supported(info.path)
            )
            if enable_ellesmere_compat:
                compat = generate_ellesmere_compat(info.path.parent)
                ellesmere_compat_files.add(str(compat))

            patch_toc(
                info.path,
                info.addon,
                inject_account=account_ok,
                inject_character=bool(pcs),
                inject_ellesmere_compat=enable_ellesmere_compat,
            )
            patched.append(
                {
                    "toc": str(info.path),
                    "addon": info.addon,
                    "account": account_ok,
                    "per_character": [
                        {
                            "realm": s.realm_folder,
                            "character": s.character_folder,
                            "saved_dir": str(s.saved_dir),
                        }
                        for s in pcs
                    ],
                }
            )
    except Exception:
        print(
            f"ERROR during install. Safety backup is at: {backup}",
            file=sys.stderr,
        )
        raise

    state = {
        "version": VERSION,
        "wow": str(wow),
        "account": account.name,
        "backup": str(backup),
        "patched": patched,
        "linked_account_dirs": linked_account_dirs,
        "generated_pc_dirs": sorted(generated_pc_dirs),
        "char_bootstraps": sorted(char_bootstraps),
        "pc_meta": pc_meta,
        "ellesmere_compat_files": sorted(ellesmere_compat_files),
    }
    save_state(wow, state)

    # v0.2 state is obsolete after successful migration; keep its backups.
    old = state_dir(wow) / "state-v2.json"
    if old.exists():
        old.unlink()

    print(f"ForeverSVFix {VERSION} installed/refreshed.")
    print(f"Account:              {account.name}")
    print(f"Patched TOCs:         {len(patched)}")
    print(f"Account links:        {len(linked_account_dirs)}")
    print(f"Per-character helpers:{len(generated_pc_dirs)}")
    print(f"EllesmereUI profile fix:{len(ellesmere_compat_files)}")
    print(f"Safety backup:        {backup}")
    print(f"Stale flavor TOCs cleaned: {stale_cleaned}")
    print()
    print("Run Apply / Refresh after installing, updating, or removing addons,")
    print("or after a new character creates SavedVariables for the first time.")
    return 0


def remove_runtime_files(addons_dir: Path) -> None:
    cleanup_generated_pc(addons_dir)

    for folder in addons_dir.iterdir():
        if not folder.is_dir() or folder.name.startswith("ForeverSVFixPC_"):
            continue
        link = folder / DATA_DIR
        if lexists(link):
            remove_link(link)
        bootstrap = folder / CHAR_BOOTSTRAP
        if bootstrap.is_file():
            bootstrap.unlink()
        compat = folder / ELLESMERE_COMPAT
        if compat.is_file():
            compat.unlink()


def uninstall(wow: Path) -> int:
    addons_dir = wow / "Interface" / "AddOns"
    state = load_state(wow)
    candidates: dict[Path, str] = {}

    if state:
        for item in state.get("patched", []):
            candidates[Path(item["toc"])] = item["addon"]

    # Marker sweep handles addon updates and incomplete state.
    for folder in addons_dir.iterdir():
        if not folder.is_dir() or folder.name.startswith("ForeverSVFixPC_"):
            continue
        for toc in folder.glob("*.toc"):
            try:
                text = read_text(toc)
            except Exception:
                continue
            if "X-ForeverSVFix" in text:
                candidates[toc] = folder.name

    cleaned = 0
    for toc, addon in candidates.items():
        if unpatch_toc(toc, addon):
            cleaned += 1

    remove_runtime_files(addons_dir)

    p = state_dir(wow) / STATE_FILE_NAME
    if p.exists():
        p.unlink()

    # Also remove stale v2 active-state file; backups remain.
    old = state_dir(wow) / "state-v2.json"
    if old.exists():
        old.unlink()

    print(f"ForeverSVFix removed. TOCs cleaned: {cleaned}")
    print("SavedVariables and all safety backups were left untouched.")
    return 0


def doctor(
    wow: Path,
    account_name: str | None,
    show_status: bool = False,
) -> int:
    account = choose_account(wow, account_name)
    account_sv = account / "SavedVariables"
    addons_dir = wow / "Interface" / "AddOns"
    state = load_state(wow)

    problems = []
    warnings = []

    if not state:
        problems.append("No v0.3 state file found. Run install.")
    else:
        for item in state.get("patched", []):
            toc = Path(item["toc"])
            addon = item["addon"]
            if not toc.is_file():
                problems.append(f"Missing patched TOC: {toc}")
                continue
            text = read_text(toc)
            if f"## {MARKER}: {MARKER_VERSION}" not in text:
                problems.append(f"Addon update removed patch marker: {toc}")
            if item.get("account"):
                expected = f"{DATA_DIR}\\{addon}.lua"
                if expected not in text:
                    problems.append(f"Account restore line missing: {toc}")
                link = toc.parent / DATA_DIR
                if not lexists(link):
                    problems.append(f"Account data link missing: {link}")
                elif not (link / f"{addon}.lua").is_file():
                    problems.append(f"Live account SavedVariables file unavailable through link: {link}")
            if item.get("per_character"):
                if CHAR_BOOTSTRAP not in text:
                    problems.append(f"Per-character bootstrap line missing: {toc}")
                if not (toc.parent / CHAR_BOOTSTRAP).is_file():
                    problems.append(f"Per-character bootstrap file missing: {toc.parent / CHAR_BOOTSTRAP}")

        for compat_name in state.get("ellesmere_compat_files", []):
            compat = Path(compat_name)
            if not compat.is_file():
                problems.append(f"EllesmereUI compatibility file missing: {compat}")
                continue
            toc = compat.parent / "EllesmereUI.toc"
            if not toc.is_file():
                problems.append(f"EllesmereUI TOC missing: {toc}")
                continue
            lines = read_text(toc).splitlines()
            try:
                lite_at = next(i for i, line in enumerate(lines) if line.strip() == "EllesmereUI_Lite.lua")
                compat_at = next(i for i, line in enumerate(lines) if line.strip() == ELLESMERE_COMPAT)
            except StopIteration:
                problems.append(f"EllesmereUI compatibility TOC entry missing: {toc}")
            else:
                if compat_at != lite_at + 1:
                    problems.append(f"EllesmereUI compatibility load order is wrong: {toc}")

        for helper in state.get("generated_pc_dirs", []):
            root = Path(helper)
            if not root.is_dir():
                problems.append(f"Per-character helper missing: {root}")
            elif not lexists(root / "Data"):
                problems.append(f"Per-character helper data link missing: {root / 'Data'}")

    # Detect stale patches on non-Forever flavor TOCs left by an older RC.
    target_paths_now = {info.path for info, _, _ in find_targets(wow, account)}
    for info in discover_all_tocs(addons_dir):
        if info.path in target_paths_now:
            continue
        try:
            toc_text = read_text(info.path)
        except Exception:
            continue
        if "X-ForeverSVFix" in toc_text:
            warnings.append(f"Stale patch on non-Forever TOC: {info.path}")

    # Detect compatible TOCs that appeared since install.
    current_targets = find_targets(wow, account)
    state_tocs = {p["toc"] for p in state.get("patched", [])} if state else set()
    for info, account_ok, pcs in current_targets:
        if str(info.path) not in state_tocs:
            warnings.append(f"Compatible addon not yet patched: {info.path}")

    if show_status:
        print(f"ForeverSVFix {VERSION} installation check")
        print()
        if state:
            healthy = not problems and not warnings
            print(f"Installation:         {'OK' if healthy else 'NEEDS ATTENTION'}")
            print(f"Installed version:    {state.get('version', 'unknown')}")
            print(f"Account:              {state.get('account', account.name)}")
            print(f"Patched TOCs:         {len(state.get('patched', []))}")
            print(f"Account links:        {len(state.get('linked_account_dirs', {}))}")
            print(f"Character helpers:    {len(state.get('generated_pc_dirs', []))}")
            print(f"EllesmereUI fix:      {len(state.get('ellesmere_compat_files', []))}")
            backup = state.get("backup")
            if backup:
                print(f"Last safety backup:   {backup}")
        else:
            print("Installation:         NOT INSTALLED")
            print(f"Account:              {account.name}")
        print()
    else:
        print(f"ForeverSVFix doctor {VERSION}")
        print(f"Account: {account.name}")
        print()

    if problems:
        print("PROBLEMS:")
        for p in problems:
            print(f"  - {p}")
    elif not warnings:
        print("Active installation checks: OK")

    if warnings:
        print()
        print("REFRESH NEEDED:")
        for w in warnings:
            print(f"  - {w}")

    if problems or warnings:
        print()
        if show_status:
            print("Run Apply / Refresh ForeverSVFix to repair the installation.")
        else:
            print("Run the 'repair' CLI command (or Apply / Refresh in the menu).")
        return 1

    print("No repair needed.")
    return 0


def status(wow: Path) -> int:
    state = load_state(wow)
    if not state:
        print(f"ForeverSVFix {VERSION} is not installed.")
        return 1

    print(f"ForeverSVFix {VERSION} status")
    print(f"WoW:                {wow}")
    print(f"Installed version:  {state.get('version', 'unknown')}")
    print(f"Account:            {state.get('account', 'unknown')}")
    print(f"Patched TOCs:       {len(state.get('patched', []))}")
    print(f"Account links:      {len(state.get('linked_account_dirs', {}))}")
    print(f"Character helpers:  {len(state.get('generated_pc_dirs', []))}")
    print(f"EllesmereUI fix:    {len(state.get('ellesmere_compat_files', []))}")

    backup = state.get("backup")
    if backup:
        print(f"Last safety backup: {backup}")

    return 0




def version_key(value: str) -> tuple[int, int, int, int, int] | None:
    """Return a sortable key for ForeverSVFix release versions.

    Stable releases sort after release candidates of the same base version.
    Unknown tag formats are ignored rather than guessed.
    """
    m = VERSION_RE.match(value.strip())
    if not m:
        return None
    major, minor, patch = (int(m.group(i)) for i in (1, 2, 3))
    rc = m.group(4)
    if rc is None:
        return (major, minor, patch, 1, 0)
    return (major, minor, patch, 0, int(rc))


def select_latest_release(releases: object) -> dict | None:
    """Pick the newest non-draft ForeverSVFix release, including prereleases."""
    if not isinstance(releases, list):
        return None

    best = None
    best_key = None
    for item in releases:
        if not isinstance(item, dict) or item.get("draft"):
            continue
        tag = item.get("tag_name")
        if not isinstance(tag, str):
            continue
        key = version_key(tag)
        if key is None:
            continue
        if best_key is None or key > best_key:
            best = item
            best_key = key
    return best


def https_context() -> ssl.SSLContext:
    """Return a CA-backed HTTPS context that also works in frozen builds.

    Source installs normally use the operating system trust store. Standalone
    PyInstaller builds bundle certifi so HTTPS does not depend on an external
    Python/OpenSSL certificate path being available at runtime.
    """
    if certifi is not None:
        try:
            return ssl.create_default_context(cafile=certifi.where())
        except (OSError, AttributeError):
            pass
    return ssl.create_default_context()


def fetch_latest_release() -> dict | None:
    req = urllib.request.Request(
        GITHUB_RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"ForeverSVFix/{VERSION}",
        },
    )
    try:
        with urllib.request.urlopen(
            req,
            timeout=UPDATE_CHECK_TIMEOUT,
            context=https_context(),
        ) as response:
            payload = response.read()
        releases = json.loads(payload.decode("utf-8"))
        return select_latest_release(releases)
    except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError):
        return None


def update_available(latest_tag: str | None) -> bool:
    if not latest_tag:
        return False
    current = version_key(VERSION)
    latest = version_key(latest_tag)
    return current is not None and latest is not None and latest > current


def check_for_update(config: dict, force: bool = False) -> dict:
    """Check GitHub Releases, with a 24-hour cache for automatic checks.

    Returns a small result dict. Network failures are intentionally non-fatal.
    """
    now = int(time.time())
    cache = config.get("update_check")
    if not isinstance(cache, dict):
        cache = {}

    last_checked = cache.get("last_checked")
    if (
        not force
        and isinstance(last_checked, (int, float))
        and now - int(last_checked) < UPDATE_CHECK_INTERVAL
    ):
        tag = cache.get("latest_tag")
        url = cache.get("latest_url") or GITHUB_RELEASES_URL
        return {
            "checked": False,
            "from_cache": True,
            "available": update_available(tag if isinstance(tag, str) else None),
            "latest_tag": tag if isinstance(tag, str) else None,
            "url": url if isinstance(url, str) else GITHUB_RELEASES_URL,
            "error": None,
        }

    release = fetch_latest_release()
    if release is None:
        # Cache the failed attempt too, so offline users are not delayed by a
        # network timeout on every launch. Keep any previously known release.
        old_tag = cache.get("latest_tag")
        old_url = cache.get("latest_url") or GITHUB_RELEASES_URL
        cache["last_checked"] = now
        config["update_check"] = cache
        try:
            save_config(config)
        except OSError:
            pass
        return {
            "checked": True,
            "from_cache": False,
            "available": update_available(old_tag if isinstance(old_tag, str) else None),
            "latest_tag": old_tag if isinstance(old_tag, str) else None,
            "url": old_url if isinstance(old_url, str) else GITHUB_RELEASES_URL,
            "error": "Could not reach GitHub Releases.",
        }

    tag = release.get("tag_name")
    url = release.get("html_url")
    if not isinstance(tag, str):
        tag = None
    if not isinstance(url, str) or not url.startswith("https://github.com/"):
        url = GITHUB_RELEASES_URL

    cache = {
        "last_checked": now,
        "latest_tag": tag,
        "latest_url": url,
    }
    config["update_check"] = cache
    try:
        save_config(config)
    except OSError:
        pass

    return {
        "checked": True,
        "from_cache": False,
        "available": update_available(tag),
        "latest_tag": tag,
        "url": url,
        "error": None,
    }


def print_update_warning(result: dict) -> None:
    if not result.get("available"):
        return
    latest = result.get("latest_tag") or "newer release"
    url = result.get("url") or GITHUB_RELEASES_URL
    print("=" * 54)
    print("UPDATE AVAILABLE")
    print()
    print(f"You are running: {VERSION}")
    print(f"Latest release:  {latest}")
    print()
    print(url)
    print("=" * 54)
    print()


def manual_update_check(config: dict) -> None:
    result = check_for_update(config, force=True)
    print()
    if result.get("error"):
        print("Could not check for updates right now.")
        print("ForeverSVFix will continue to work normally.")
    elif result.get("available"):
        print_update_warning(result)
    else:
        latest = result.get("latest_tag") or VERSION
        print(f"You are up to date. Latest release: {latest}")
        print(GITHUB_RELEASES_URL)
    pause_menu()

def config_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "ForeverSVFix"
        return Path.home() / "AppData" / "Roaming" / "ForeverSVFix"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "ForeverSVFix"
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "forever-sv-fix"
    return Path.home() / ".config" / "forever-sv-fix"


def config_file() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict:
    p = config_file()
    if not p.is_file():
        return {}
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def save_config(config: dict) -> None:
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    config_file().write_text(
        json.dumps(config, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def known_wow_candidates() -> list[Path]:
    candidates: list[Path] = []
    system = platform.system()
    home = Path.home()

    if system == "Windows":
        for env_name in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
            base = os.environ.get(env_name)
            if base:
                candidates.append(
                    Path(base) / "World of Warcraft" / "_classic_beta_"
                )
        candidates.extend(
            [
                Path("C:/World of Warcraft/_classic_beta_"),
                Path("D:/World of Warcraft/_classic_beta_"),
            ]
        )

    elif system == "Darwin":
        candidates.extend(
            [
                Path("/Applications/World of Warcraft/_classic_beta_"),
                home / "Applications" / "World of Warcraft" / "_classic_beta_",
            ]
        )

    else:
        candidates.extend(
            [
                home / "Games" / "World of Warcraft" / "_classic_beta_",
                home / "World of Warcraft" / "_classic_beta_",
            ]
        )

    result = []
    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        try:
            validate_wow(candidate)
        except Exception:
            continue
        result.append(candidate.resolve())
    return result


def resolve_wow_noninteractive(explicit: str | None) -> Path:
    if explicit:
        return validate_wow(Path(explicit))

    cfg = load_config()
    configured = cfg.get("wow_path")
    if configured:
        try:
            return validate_wow(Path(configured))
        except FixError:
            pass

    found = known_wow_candidates()
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        raise FixError(
            "Multiple WoW Forever installations were detected. "
            "Run without a command to choose one, or use --wow PATH."
        )
    raise FixError(
        "WoW Forever could not be located automatically. "
        "Run without a command for interactive setup, or use --wow PATH."
    )


def account_names(wow: Path) -> list[str]:
    root = wow / "WTF" / "Account"
    return [
        p.name
        for p in sorted(root.iterdir(), key=lambda p: p.name.lower())
        if p.is_dir() and (p / "SavedVariables").is_dir()
    ]


def resolve_account_noninteractive(
    wow: Path,
    explicit: str | None,
) -> str | None:
    if explicit:
        return explicit

    cfg = load_config()
    configured = cfg.get("account")
    if configured and configured in account_names(wow):
        return configured

    names = account_names(wow)
    if len(names) == 1:
        return names[0]
    return None


def clear_screen() -> None:
    # Avoid calling external commands when output is redirected.
    if not sys.stdout.isatty():
        return
    os.system("cls" if platform.system() == "Windows" else "clear")


def pause_menu() -> None:
    try:
        input("\nPress Enter to return to the menu...")
    except EOFError:
        pass


def prompt_path(prompt: str) -> Path:
    while True:
        raw = input(prompt).strip().strip('"').strip("'")
        if not raw:
            continue
        try:
            return validate_wow(Path(raw))
        except FixError as exc:
            print(f"\n{exc}\n")


def select_wow_interactive(config: dict) -> Path:
    configured = config.get("wow_path")
    if configured:
        try:
            return validate_wow(Path(configured))
        except FixError:
            pass

    found = known_wow_candidates()
    if len(found) == 1:
        wow = found[0]
        config["wow_path"] = str(wow)
        save_config(config)
        return wow

    if len(found) > 1:
        print("\nDetected WoW Forever installations:")
        for i, path in enumerate(found, 1):
            print(f"  {i}. {path}")
        print("  0. Enter a different path")
        while True:
            choice = input("\nSelect installation: ").strip()
            if choice == "0":
                break
            try:
                index = int(choice) - 1
                if 0 <= index < len(found):
                    wow = found[index]
                    config["wow_path"] = str(wow)
                    save_config(config)
                    return wow
            except ValueError:
                pass
            print("Invalid selection.")

    print("\nWoW Forever was not found automatically.")
    print("Enter the path to the _classic_beta_ folder.")
    wow = prompt_path("Path: ")
    config["wow_path"] = str(wow)
    save_config(config)
    return wow


def select_account_interactive(
    wow: Path,
    config: dict,
    force: bool = False,
) -> str | None:
    names = account_names(wow)
    if not names:
        raise FixError("No WoW account with a SavedVariables directory was found.")

    configured = config.get("account")
    if not force and configured in names:
        return configured

    if len(names) == 1:
        config["account"] = names[0]
        save_config(config)
        return names[0]

    print("\nWoW accounts:")
    for i, name in enumerate(names, 1):
        print(f"  {i}. {name}")

    while True:
        choice = input("\nSelect account: ").strip()
        try:
            index = int(choice) - 1
            if 0 <= index < len(names):
                config["account"] = names[index]
                save_config(config)
                return names[index]
        except ValueError:
            pass
        print("Invalid selection.")


def run_menu_action(fn, *args) -> None:
    print()
    try:
        fn(*args)
    except FixError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"UNEXPECTED ERROR: {exc}", file=sys.stderr)
    pause_menu()


def settings_menu(
    wow: Path,
    account: str | None,
    config: dict,
) -> tuple[Path, str | None]:
    while True:
        clear_screen()
        print("ForeverSVFix Settings")
        print("=" * 54)
        print(f"WoW:     {wow}")
        print(f"Account: {account or 'automatic'}")
        print()
        print("  1. Change WoW installation")
        print("  2. Change WoW account")
        print("  3. Back")
        print()

        try:
            choice = input("Choose an option: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return wow, account

        if choice == "1":
            config.pop("wow_path", None)
            config.pop("account", None)
            save_config(config)
            clear_screen()
            wow = select_wow_interactive(config)
            account = select_account_interactive(wow, config)
        elif choice == "2":
            account = select_account_interactive(wow, config, force=True)
        elif choice == "3":
            return wow, account
        else:
            print("\nInvalid selection.")
            pause_menu()


def interactive_menu() -> int:
    config = load_config()
    update_result = check_for_update(config, force=False)
    update_warning_shown = False

    try:
        wow = select_wow_interactive(config)
        account = select_account_interactive(wow, config)
    except (FixError, KeyboardInterrupt, EOFError) as exc:
        if isinstance(exc, FixError):
            print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    while True:
        clear_screen()
        installed = load_state(wow) is not None

        if update_result.get("available") and not update_warning_shown:
            print_update_warning(update_result)
            update_warning_shown = True

        print(f"ForeverSVFix {VERSION}")
        print("=" * 54)
        print(f"WoW:     {wow}")
        print(f"Account: {account or 'automatic'}")
        print(f"Status:  {'installed' if installed else 'not installed'}")
        print()
        print("  1. Apply / Refresh ForeverSVFix")
        print("  2. Check installation")
        print("  3. Settings")
        print("  4. Check for updates")
        print("  5. Uninstall ForeverSVFix")
        print("  6. Exit")
        print()

        try:
            choice = input("Choose an option: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if choice == "1":
            run_menu_action(install, wow, account)
        elif choice == "2":
            run_menu_action(doctor, wow, account, True)
        elif choice == "3":
            wow, account = settings_menu(wow, account, config)
        elif choice == "4":
            manual_update_check(config)
            update_result = check_for_update(config, force=False)
            update_warning_shown = True
        elif choice == "5":
            answer = input(
                "\nRemove ForeverSVFix? SavedVariables/backups will be kept. [y/N]: "
            ).strip().lower()
            if answer in ("y", "yes"):
                run_menu_action(uninstall, wow)
            else:
                pause_menu()
        elif choice == "6":
            return 0
        else:
            print("\nInvalid selection.")
            pause_menu()



def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Work around WoW Forever's broken SavedVariables loader."
    )
    p.add_argument(
        "--wow",
        help="Path to the _classic_beta_ directory. Optional in interactive mode.",
    )
    p.add_argument(
        "--account",
        help="WTF/Account folder if multiple accounts exist.",
    )
    sub = p.add_subparsers(dest="command")
    for name in ("scan", "install", "repair", "doctor", "status", "uninstall", "check-update"):
        sub.add_parser(name)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    # No command means normal-user interactive mode.
    if args.command is None:
        return interactive_menu()

    if args.command == "check-update":
        config = load_config()
        result = check_for_update(config, force=True)
        if result.get("error"):
            print("Could not check for updates right now.", file=sys.stderr)
            return 2
        if result.get("available"):
            print_update_warning(result)
            return 0
        print(f"ForeverSVFix {VERSION} is up to date.")
        return 0

    try:
        wow = resolve_wow_noninteractive(args.wow)
        account = resolve_account_noninteractive(wow, args.account)

        if args.command in ("scan", "install", "repair", "doctor") and account is None:
            raise FixError(
                "Multiple WoW accounts exist. Use --account NAME or run "
                "ForeverSVFix without a command to choose interactively."
            )

        if args.command == "scan":
            return scan(wow, account)
        if args.command in ("install", "repair"):
            return install(wow, account)
        if args.command == "doctor":
            return doctor(wow, account)
        if args.command == "status":
            return status(wow)
        if args.command == "uninstall":
            return uninstall(wow)

    except FixError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
