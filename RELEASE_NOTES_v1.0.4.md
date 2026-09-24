# ForeverSVFix v1.0.4

ForeverSVFix v1.0.4 separates SavedVariables persistence from EllesmereUI-specific compatibility and fixes a confirmed Windows decoding crash.

## EllesmereUI migration

EllesmereUI-specific fixes now live in the standalone **EllesmereUI Forever Fix** addon:

https://www.curseforge.com/wow/addons/ellesmereui-forever-fix

ForeverSVFix is still required for EllesmereUI settings/profile persistence while the WoW Forever SavedVariables loader bug exists.

If Apply / Refresh finds the old `ForeverSVFixEllesmereUI.lua` compatibility shim from v1.0.3 or earlier, it asks before removing it and creates a safety backup first. ForeverSVFix does not download or install the standalone addon automatically.

## Windows fix

v1.0.4 fixes `UnicodeDecodeError` failures caused by localized `cmd.exe` output during Windows junction creation/removal. Both subprocess paths now tolerate bytes that cannot be represented by Python's selected locale codec.

## Scope

This release does not claim fixes for the still-open Wowhead Looter TOC-rewrite issue, the macOS startup issue, or addons that are not currently discovered as SavedVariables targets.
