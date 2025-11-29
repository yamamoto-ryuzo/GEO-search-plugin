# Map Themes — Theme Management Subsystem (Overview)

This document summarizes the design and implementation of the Theme/Display Management subsystem (Map Themes) in the GEO Search System. It works with the Search subsystem to apply display changes when searches run and provides an "additive display" mode.

## User Themes (under development)

The plugin provides a minimal "user theme" feature — a small display snapshot mechanism. This feature is under development. Its goal is to save and restore the minimum visualization state a user expects (visible layers, visible legend items, and, where possible, style names).

Note: This feature does not fully reproduce an entire QGIS project (.qgs). Due to differences in renderers and QGIS versions, restoration may be partial.

- Storage format: JSON (recommended extension example: `.usertheme.json`)
- Stored contents (summary):
  - `meta`: metadata at creation time (version, timestamp, project filepath, etc.)
  - `entries`: array of visible layers (each entry contains `order`, `id`, `name`, `style`, `legend_items`)

Simple JSON example:

```json
{
  "meta": {
    "version": 1,
    "qgis_version": "3.40.0",
    "timestamp": "2025-11-24T12:34:56Z",
    "project": "C:/path/to/project.qgz"
  },
  "entries": [
    {
      "order": 0,
      "id": "c2f3...",
      "name": "roads",
      "style": "default",
      "legend_items": [
        {"label": "major", "visible": true},
        {"label": "minor", "visible": false}
      ]
    }
  ]
}
```

Best-effort application policy:
- Layers are sought by `id` first; if not found, the code falls back to `name`. If names are duplicated, the first match is used.
- If `style` is specified, the plugin attempts to apply it using a best-effort utility `_apply_layer_style_by_name` in `geo_search/theme.py`.
- `legend_items` are matched by `label` to renderer items and visibility flags are applied. For categorized renderers the saved value is split and matched against existing categories.

Known limitations (development):
- Full compatibility is not guaranteed. Complex rule-based renderers and large QGIS version differences may prevent accurate restoration.
- Style application relies on name/ID; if the named style does not exist, it will not be applied.
- Layer-name duplicates are handled by simple fallback (first-match), which may be surprising in some projects.

Developer quick test checklist:
1. Save your QGIS project.
2. Use the settings dialog `Save User Theme...` to save a theme (e.g., into `project/themes/`).
3. Inspect the saved JSON to ensure `entries` are recorded correctly.
4. Change layer states in the project (visibility, style, etc.).
5. Run `Load User Theme...` to test restoration.
6. Check QGIS message log (tag: `GEO-search-plugin`) for which layers were applied or failed to apply.

Implementation notes (maintainers):
- Snapshot collection: `collect_visible_layer_snapshot`; application: `apply_user_theme` in `geo_search/theme.py`.
- Persistence is file-based (JSON) for now; optionally we can store paths in project variables in the future.
- This section documents an in-development feature; final user documentation should be written after stabilization.

---

# Map Themes — Overview and Implementation Notes

This document describes the plugin-provided Map Themes functionality and the plugin-specific "Additive mode". It includes a short user-oriented quick start followed by developer-facing implementation details and caveats.

**Subsystem purpose**
- Provide an API and UI to list and immediately apply QGIS map themes and integrate theme application into the search workflow.
- Automatically apply a preconfigured theme when a search is executed, and optionally save the pre-search display state as a `before-search` theme to allow restoration.

---

**High-level implementation points**

- Add a `QComboBox` on the toolbar for theme selection and populate it from the project's map theme collection.
- Automatically refresh the combo when the project's theme collection changes (add/remove) or when the project is saved/loaded.
- Applying a theme from the combo applies it immediately.
- When a search runs, each tab's `selectTheme` config (from settings or project variable) is consulted and applied if present; if none is specified, the plugin doesn't change the theme.
- On plugin startup the current display state is saved as `before-search`. When `selectTheme` is set to `before-search`, the startup display state is restored.

---

**Main implementation files and functions**

- `geo_search/plugin.py`
  - `initGui()`
    - Create `theme_combobox` on the toolbar and call `update_theme_combobox()`.
    - Connect project load/save and theme collection change events to `update_theme_combobox()`.
  - `update_theme_combobox()`
    - Acquire theme names from `QgsProject.instance().mapThemeCollection().mapThemes()`, clear the combo, and re-add a placeholder `Select theme` plus the theme list.
    - The toolbar also supports a `group_combobox` for group filtering; when the group is unset (placeholder `All`) show all themes, otherwise filter by group.
    - While theme-apply operations are in progress, automatic updates are suppressed with a `_suppress_theme_update` flag to avoid unintended rewrites triggered by QGIS signals.
  - `apply_selected_theme(index)`
    - Handler for combo selection: apply the selected theme with `theme_collection.applyTheme(theme_name, root, model)`.
    - Older logic that recorded internal selection state and auto-restored has been removed to favor explicit user actions.
    - When `applyTheme` causes theme collection changes and QGIS emits `mapThemesChanged` (or similar), the plugin temporarily suppresses `update_theme_combobox()` while applying.
  - `run()`
    - Just before showing the search dialog, the plugin saves the current display state into the map theme collection under the name `before-search` (a pre-search snapshot).

- `geo_search/searchfeature.py`
  - `SearchFeature.show_features()` (and derived callers)
    - Reads `self.setting.get('selectTheme')`; if it exists and the theme is present in the project, apply it.
    - If `selectTheme` is not specified, do nothing. If specified but missing, log a warning.
    - For backward-compatibility, if `selectTheme` is not specified but `before-search` exists, apply `before-search`.

- `README.md`
  - Contains user notes about `selectTheme`, `before-search` auto-save, and how to choose themes in the tab settings editor.

---

**Where to configure**

- `setting.json` (plugin-bundled default)
- QGIS project variable `GEO-search-plugin` (per-project config)

Set `