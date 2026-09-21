# ForeverSVFix v1.0.1

v1.0.1 fixes a SavedVariables load-order problem found after the first stable release.

Some addons initialize their SavedVariables globals to defaults while their normal Lua/XML files load. ForeverSVFix v1.0.0 restored data before those files, which allowed those addons to overwrite the restored values again.

v1.0.1 restores account-wide and per-character SavedVariables after the addon's normal files by default, matching WoW's normal SavedVariables timing more closely.

Addons that explicitly declare `## LoadSavedVariablesFirst: 1` keep their requested pre-script behavior. The previously validated EllesmereUI compatibility path also keeps its existing ordering.

Existing installations are migrated when you run **Apply / Refresh ForeverSVFix** after updating.

This fix was reproduced and confirmed with the per-character loading issue reported in GitHub issue #2.
