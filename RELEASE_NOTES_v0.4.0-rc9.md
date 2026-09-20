# ForeverSVFix v0.4.0 RC9

EllesmereUI compatibility release candidate.

Changes from RC8:

- Add targeted compatibility support for EllesmereUI v9.2.1's Forever profile system.
- Detect the shipped EllesmereUI load-order layout instead of redistributing or replacing EllesmereUI code.
- Generate a tiny compatibility shim that disables only EllesmereUI's temporary `FOREVER_SV_BUG` safety gate after `EllesmereUI_Lite.lua` initializes it.
- Keep `EllesmereUI.IS_FOREVER` enabled, so unrelated Forever-specific compatibility restrictions remain intact.
- Re-enable EllesmereUI's existing Profiles & Presets UI, reload flows, first-install/style flows, and suppress its SavedVariables warning while ForeverSVFix is active.
- Doctor now validates the EllesmereUI compatibility file and exact TOC load order.
- Uninstall removes the generated EllesmereUI compatibility file and TOC entry.
- Fix Status counts to use the current v3 state-file keys.
- SavedVariables restoration mechanism is otherwise unchanged.

Validated SavedVariables behavior remains Linux/Wine only. The EllesmereUI profile integration still requires in-game validation before it should be treated as proven.
