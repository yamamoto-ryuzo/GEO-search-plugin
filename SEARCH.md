[Japanese original: `SEARCH_JP.md`](./SEARCH_JP.md)

# Search Function (English)

## Table of Contents

- [Search Function (English)](#search-function-english)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Subsystem Diagram and Boundaries (for developers)](#subsystem-diagram-and-boundaries-for-developers)
  - [Parcel Number (Tiban) Search](#parcel-number-tiban-search)
  - [General Attribute Search](#general-attribute-search)
  - [Owner Search](#owner-search)
  - [Search Logic (Implementation Overview)](#search-logic-implementation-overview)
    - [Full-text-like Search](#full-text-like-search)
    - [Parcel Number Search](#parcel-number-search)
    - [Owner Search](#owner-search-1)
    - [Displayed-Layer / All-Layers Search](#displayed-layer--all-layers-search)
    - [Auxiliary Functions](#auxiliary-functions)
  - [UI Settings Dialog](#ui-settings-dialog)
  - [Configuration Items](#configuration-items)
    - [Key Settings](#key-settings)
    - [Behavior of View Fields](#behavior-of-view-fields)
    - [Map Navigation After Selection](#map-navigation-after-selection)
  - [Configuration Sources (Load Order) and Notes](#configuration-sources-load-order-and-notes)
  - [Configuration File Description (Major Items)](#configuration-file-description-major-items)
    - [Map Theme Feature (Overview)](#map-theme-feature-overview)
  - [Issues and Notes](#issues-and-notes)
  - [Reference Files](#reference-files)

## Overview

This document describes the search subsystem of the GEO Search System. It covers behavior for parcel-number (Tiban) search, owner search, and general attribute searches, the search logic, tab settings, theme integration, and how the subsystem integrates with the overall system.

## Subsystem Diagram and Boundaries (for developers)

Simple textual diagram:

```
 UI (Search dialog / SearchTab settings)
            |
            v
 [Search Subsystem]
     - Search widgets (SearchTibanWidget, SearchOwnerWidget, SearchTextWidget)
     - Search features (SearchTibanFeature, SearchOwnerFeature, SearchTextFeature)
            |
            +--> Theme Management (selectTheme)  <--> Theme subsystem
            |
            v
     Result Presentation (per-layer tabs, ViewFields, paging)
```

Main implementation files:

- `geo_search/widget/searchwidget.py` — SearchTibanWidget / SearchOwnerWidget / SearchTextWidget
- `geo_search/searchfeature.py` — SearchFeature implementation (result retrieval and presentation)
- `geo_search/plugin.py` — Plugin startup, reading tab settings and attaching annotations

Integration points (theme management):

- `selectTheme` (each SearchTab setting): specifies a map theme to apply before performing a search.
- Theme application is delegated to the theme subsystem; additive display mode allows merging theme visibility with the current display (see `THEMES.md`).

---

## Parcel Number (Tiban) Search

- Searches by parcel number (tiban). Supports regular expression, exact match, and fuzzy/neighbor-number search.
- Results are displayed in a paged table, with one tab per layer.

## General Attribute Search

- Searches arbitrary attribute fields. Columns shown and paging are controlled per-tab settings.

## Owner Search

- Searches by owner name. Normalization is performed (e.g., full-width Katakana to half-width, whitespace handling). Searches can combine multiple fields and support prefix/partial match based on configuration.

## Search Logic (Implementation Overview)

### Full-text-like Search
- Implementation files: `geo_search/widget/searchwidget.py` (widgets) and `geo_search/searchfeature.py` (feature implementations).
- Behavior: the input search terms are normalized and LIKE-equivalent conditions are built against configured search fields to execute the search.

### Parcel Number Search
- Implementation files: `geo_search/widget/searchwidget.py` and `geo_search/searchfeature.py`.
- Behavior: accepts input specific to parcel numbers and performs regex or neighbor-number fuzzy searches.

### Owner Search
- Implementation files: `geo_search/widget/searchwidget.py` and `geo_search/searchfeature.py`.
- Behavior: allows searching across multiple fields. Performs Kana normalization and whitespace processing, and searches with LIKE conditions.

### Displayed-Layer / All-Layers Search
- `SearchTextFeature.show_features` will, when a tab title is `Displayed Layers` or `All Layers`, search across currently visible layers or all project layers respectively, and present results in per-layer tabs.

### Auxiliary Functions
- Suggest (autocomplete): uses `unique_values` to build a `QCompleter`.
- Map theme application: the `selectTheme` setting on each tab can be applied at search time.

---

## UI Settings Dialog

- Tab-specific settings (target layers, search fields, view fields, map theme) can be edited via GUI and are saved into the project.

Quick start:

- Installation: place the `geo_search` folder into QGIS user plugins directory or install from the provided ZIP.
- Start: enable the plugin in QGIS and open the search dialog from the toolbar button.
- Search: select or configure a tab, enter parcel number, owner name, or attributes, then press `Search`.
- Results: results appear in per-layer tabs; click a row to select and pan/zoom on the map.

Refer to the README for details.

---

## Configuration Items

See `setting.json.sample` in the plugin bundle for examples. Below are the main items.

```json
{
  "SearchTabs": [
    {
      "Title": "Sample",
      "Layer": { "LayerType": "Database", "DataType": "postgres", "Host": "HostName", "Port": "5432", "Database": "DatabaseName", "User": "UserName", "Password": "Password", "Schema": "public", "Table": "kihonp", "Key": "ogc_fid", "Geometry": "wkb_geometry", "FormatSQL": "format.sql" },
      "TibanField": "parcel field",
      "AzaTable": { "DataType": "postgres", "Host": "...", "Port": "5433", "Database": "...", "User": "...", "Password": "...", "Schema": "public", "Table": "code_table_area", "Columns": [ { "Name": "display attribute name", "View": "display label" } ] },
      "SearchFields": [ { "FieldType": "Text", "ViewName": "label shown in search dialog", "Field": "attribute used for search", "KanaHankaku": true } ],
      "SampleFields": ["attributes shown in temporary table"],
      "ViewFields": ["attributes shown in results"],
      "Message": "Help message shown with ? button",
      "SampleTableLimit": 100,
      "selectTheme": "theme name"
    }
  ]
}
```

### Key Settings
- `Title`: tab display name
- `Layer`: layer loading information (`LayerType` can be `Name`/`File`/`Database`)
- `SearchFields` / `SearchField`: fields used for searching
- `ViewFields`: fields shown in the result (empty array shows all fields)
- `selectTheme`: name of the QGIS map theme to apply on search (`"before-search"` can be used to apply the display state saved at plugin startup)

### Behavior of View Fields
- Unset or empty array: show all layer fields
- Specify only existing fields: show only specified fields
- If a non-existent field is specified, the table will be empty (QGIS will show a warning)

### Map Navigation After Selection
- Zoom to selection (default): zoom to fit selected features
- Center pan (keep zoom): pan to center while keeping current scale
- Fixed scale: center at a specified scale
- Animated pan: move with animation and fit
- Select only: no change to the map view

---

## Configuration Sources (Load Order) and Notes

- Load (merge) order: `setting.json` (inside plugin) → project variable `GEO-search-plugin` (inline JSON or file reference) → external `geo_search_json` (file specified by environment variable or project variable).
- Each tab configuration is annotated at runtime with:
  - `_source`: token identifying the source (e.g., `setting.json`, `project variable`, `geo_search_json`)
  - `_source_index`: 0-based index within that source (based on load order)

- These annotations are used to identify which configuration to edit or delete. Deletion first attempts direct specification by `_source_index`; if out of range or mismatched, it falls back to searching by `Title`.
- File updates are done atomically with backups; after success the plugin rebuilds the UI and recalculates annotations (`_source_index`, etc.).

Example: the UI shows source labels in the form `[{short}]` or `[{short} #{index}]`. For example, the 3rd element in `setting.json` is shown as `[setting.json #2]`.

---

## Configuration File Description (Major Items)

- `Title`: title shown on the tab
- `group`: group name to group tabs
- `Layer`: layer information to load
- `SearchField` / `SearchFields`: attribute info used for searching
- `ViewFields`: attributes to show in the search results (empty array shows all fields)
- `Message`: help text displayed in UI
- `TibanField`: parcel field name
- `AzaTable`: settings for area codes used in parcel search
- `angle`: rotation angle (degrees) applied when navigating on search
- `scale`: scale (denominator) applied when navigating on search
- `selectTheme`: QGIS map theme name to apply when searching

### Map Theme Feature (Overview)

1. On plugin startup the current display state is automatically saved as a theme named `before-search`.
2. A theme selection dropdown is placed on the toolbar to apply any theme immediately.
3. If a tab's `selectTheme` is set, that theme is applied when performing a search (`before-search` restores the display saved at startup).
4. Additive display mode: when ON, applying a theme will keep currently visible layers and add the theme's visible layers on top; when OFF, the theme replaces the displayed layers.

---

## Issues and Notes

- If an external configuration file is updated concurrently by another process, there may be a temporary mismatch between the UI and file indices. UI rebuilding will reconcile the state.
- Specifying non-existent field names in `ViewFields` results in an empty table.

---

## Reference Files

- `geo_search/widget/searchwidget.py`
- `geo_search/searchfeature.py`
- `geo_search/plugin.py`
- `THEMES.md`


