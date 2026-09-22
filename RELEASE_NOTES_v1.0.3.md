# ForeverSVFix v1.0.3

v1.0.3 fixes two issues reported after the first stable releases.

## Per-character SavedVariables

WoW Forever requires first and last names for characters. ForeverSVFix now handles the full character identity more defensively when selecting generated per-character helpers, including safe fallbacks for the beta's inconsistent WTF folder layouts.

Generated per-character helpers are also marked enabled by default.

## Windows addon updates

Some addon updaters can replace ForeverSVFix's Windows directory junctions with normal directories while updating an addon. Apply / Refresh can now remove those stale ForeverSVFix-owned directories and recreate the proper links instead of aborting with "The directory is not empty."

As before, normal SavedVariables under WTF are not deleted by this cleanup.
