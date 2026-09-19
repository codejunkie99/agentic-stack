# Template: full-app walkthrough sweep

Use when an app must be verified end-to-end — after a build, before a
release, or on request ("walk through the app"). Produces a MECE result:
every screen visited, every defect either fixed or registered.

## Inputs

- app identity (bundle id or pid), the running build
- the feature inventory (docs/spec) that defines "everything"

## Procedure

1. Launch or attach; verify the process is alive (`pgrep`/list_apps) before
   observing.
2. Inventory the app's navigation surfaces (sidebar items, tabs, menu) from
   the accessibility tree.
3. For EACH surface, in order:
   a. Navigate to it.
   b. `get_app_state` with a window screenshot — judge both the tree
      (data present? buttons enabled?) and the pixels (layout, contrast,
      truncation, empty states).
   c. Exercise the primary action if it is safe and reversible.
   d. Record: WORKS / BROKEN(why) / GAP(feature missing).
4. Modal sheets and dialogs count as screens — open each once.
5. Fix all BROKEN/GAP items in code, rebuild, and re-walk only the fixed
   surfaces.
6. Register the sweep: table of surfaces → verdict → fix, appended to the
   project's audit/notes document. Commit fixes separately from features.

## Exit criteria

- Every inventoried surface has a verdict.
- Zero BROKEN items remain unregistered.
- Fixes are committed with the sweep record.
