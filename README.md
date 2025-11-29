# GEO Search System — Map Search System for QGIS

[日本語版 / 日本語 (README_JP.md)](./README_JP.md) 

## Overview

This repository implements the GEO Search System — a modular map-search system for QGIS. The project provides search subsystems (lot-number, owner-name and general attribute searches) and complementary subsystems such as theme/visualization management. Search results are shown as per-layer tabs and the presentation (view fields, paging, and map-theme application) is configurable per tab.

A central feature of the plugin is the use of map "themes" (map themes) to control how search results are displayed. Each search tab can specify a `selectTheme` value; when a search runs, the plugin attempts to apply that theme to reproduce layer visibility, symbology, labels and rendering order so that search results appear in a consistent, user-friendly style. Theme application uses stored theme names or user-theme snapshots and falls back safely when exact matches are missing.

The plugin also supports an "additive display mode" that lets the search results be added to the current project view without overwriting the existing display. In additive mode the plugin saves a temporary snapshot of the current view, applies the target theme briefly to collect the theme's visible layers, restores the previous view, then re-applies the theme's visible layers as additions. This preserves the original project layout while showing the search-specific layers.

The codebase is designed to be compatible with both Qt5 and Qt6 (QGIS 3.x). See `THEMES.md` for detailed theme subsystem design and `SEARCH.md` for search configuration details.


## Key features

### Search features

- Lot-number search (cadastral identifiers), owner-name search, and general attribute search.
- Results displayed per-layer in tabs with configurable view fields and paging.
- Click a result row to zoom/select the feature on the map.

### Theme / Additive display mode

- Per-tab `selectTheme` support: apply project themes when showing results to reproduce intended styles/visibility.
- Additive display mode: add selected-theme layers to the current view without destroying existing visibility and legend settings.
- User-themes (snapshot-based) reduce dependence on exact theme names and provide best-effort restoration of styles and legend visibility.


## Quick start

1. Install: copy the `geo_search` folder into your QGIS user plugin directory or install the ZIP via `Plugins → Manage and Install Plugins → Install from ZIP`.
2. Start: enable the plugin in QGIS and click the toolbar button to open the Search dialog.
3. Search: select or create a search tab, enter a query (lot number / owner name / attribute) and press `Search`.
4. View results: results appear in per-layer tabs; click a row to zoom/select on the map.

For detailed examples and per-tab configuration, see `SEARCH.md`.


## Per-tab configuration (SearchTab)

Each search tab is defined by a JSON configuration object. Typical keys:

- `Title`: Tab title (special handling for certain built-in search types such as lot-number)
- `group`: Optional grouping for tabs
- `Layer`: Layer specification (`Name` / `File` / `Database`)
- `SearchField` / `SearchFields`: Field(s) to search
- `ViewFields`: Fields to show in the results table (empty array = all fields)
- `selectTheme`: Optional theme name to apply when showing results
- `angle` / `scale`: Optional rotation / scale to apply when focusing the map

See `setting.json.sample` and `SEARCH.md` for full examples.


## Configuration sources and roles

The plugin supports three configuration sources to suit different users and deployment models:

1. System administrator — `setting.json` (plugin-level defaults)
	- Purpose: provide site-wide defaults or packaged presets.
	- Edited by administrators or plugin maintainers. Changes affect all users of the plugin installation.

2. Editor — `GEO-search-plugin` (project variable)
	- Purpose: project-specific settings that travel with the QGIS project.
	- Edited by project authors or editors. The project variable may contain inline JSON or a path to an external file.

3. Viewer — `geo_search_json` (external JSON file)
	- Purpose: lightweight personal or temporary settings that do not alter the project or plugin installation.
	- Configured via an environment variable `geo_search_json` or a project variable pointing to a file.

Load order (merged): `setting.json` → `GEO-search-plugin` → `geo_search_json`. Entries loaded later are appended. Each loaded tab is annotated at runtime with `_source` and `_source_index` (0-based) so edit/delete flows can target the correct source entry. The plugin prefers `_source_index` when editing/deleting; if that fails it falls back to matching by `Title`.

Security/robustness notes:
- Editing `setting.json` requires appropriate filesystem privileges.
- External files should be located in trusted places. The plugin creates backups when updating files.
- After file updates the plugin rebuilds the UI and recalculates `_source_index`.


## Qt6 / QGIS compatibility

- Designed for QGIS 3.x with compatibility support for Qt5 and Qt6. `metadata.txt` includes `supportsQt6 = True`.
- Uses `qgis.PyQt` imports and a small compatibility shim in `geo_search/qt_compat.py` to handle API differences.
- Includes UI stability improvements for Qt6-related rendering timing differences (table header resize, column stretching, minimum widths).


## Troubleshooting

If the results dialog appears empty or columns are extremely narrow:

- Disable and re-enable the plugin or restart QGIS and try again.
- Right-click the results table header and choose auto-resize, or manually resize the window.
- If the problem persists, run the diagnostic snippet in the README to collect internal state (tab counts, fields, features) and share the output.


## Search logic (implementation overview)

Detailed search implementation and examples are in `SEARCH.md`. Primary implementation files include `geo_search/widget/searchwidget.py` and `geo_search/searchfeature.py`.


## Pan modes (map camera behaviour)

Controls how the map moves after selecting a search result:

- Zoom to selection (default)
- Center-and-pan (keep scale)
- Fixed scale (use a configured scale)
- Animated pan
- Selection only (no map movement)

Configured via the `panModeComboBox` in the search dialog.


## Changelog

- **V3.3.0** — Added three configuration sources (plugin `setting.json`, project variable `GEO-search-plugin`, external `geo_search_json`) and annotated loaded tabs with `_source` and `_source_index`. Improved edit/delete robustness and UI display of source/index.
- **V3.0.0** — Theme selection and additive display mode improvements; snapshot-based legend/style handling.
- **V2.0.0** — UI and compatibility improvements.
- **V1.0.0** — Initial implementation of core search features.


---

For configuration examples and detailed behavior, see `SEARCH.md` and `THEMES.md`.


