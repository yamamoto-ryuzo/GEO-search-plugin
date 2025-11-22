"""
Utilities to merge a map theme's visibility into the current project and
produce/return project XML without permanently saving.

Usage (run inside QGIS Python console where `qgis.core` is available):

from geo_search.tools.merge_theme_into_project import (
    get_project_xml, get_theme_xml, get_theme_visible_layer_ids,
    merge_apply_theme_additive
)

# 1) Get current project XML
xml = get_project_xml()

# 2) Get XML for a named theme
theme_xml = get_theme_xml('MyTheme')

# 3) Merge theme visibility into current project (applies via layer-tree API)
#    and optionally return the merged project XML string
merged_xml = merge_apply_theme_additive('MyTheme', return_xml=True)

This approach applies visibility changes programmatically (layer-tree API)
so it does not require permanently saving the user's project. The final
merged XML is returned by writing the modified project state to a temporary
.qgs and reading it back.

Limitations / notes:
- This script sets layer visibility for layers referenced by the theme.
- Group visibility handling is best-effort: when a layer node is made
  visible, its parent group nodes are also set visible.
- If you need an XML-only merge (no runtime apply), we can add functions
  that edit the project XML directly and write out a merged .qgs.
"""
from __future__ import annotations

import os
import tempfile
import xml.etree.ElementTree as ET
from typing import List, Optional, Set

try:
    from qgis.core import QgsProject
    from qgis.PyQt.QtCore import QCoreApplication
    from qgis.utils import iface  # type: ignore
except Exception:  # pragma: no cover - run inside QGIS
    QgsProject = None  # type: ignore


def _write_project_to_temp() -> str:
    """Write current QgsProject to a temporary .qgs file and return path."""
    if QgsProject is None:
        raise RuntimeError("This function must be run inside QGIS (PyQGIS available)")

    # logging helper
    try:
        from qgis.core import QgsMessageLog
    except Exception:
        QgsMessageLog = None

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".qgs")
    tmp_path = tmp.name
    tmp.close()
    # QgsProject.write returns bool; write to tmp_path
    ok = QgsProject.instance().write(tmp_path)
    if not ok:
        # Clean up and raise
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise RuntimeError(f"Failed to write project to temporary file {tmp_path}")
    return tmp_path


def get_project_xml() -> str:
    """Return the current project XML as a string (writes to a temp .qgs).

    Runs QgsProject.instance().write() to a temporary file, reads it back,
    deletes the temporary file, and returns the XML string.
    """
    tmp_path = _write_project_to_temp()
    try:
        with open(tmp_path, "r", encoding="utf-8") as fh:
            data = fh.read()
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
    return data


def get_theme_xml(theme_name: str) -> Optional[str]:
    """Return the XML string of the named theme inside current project, or None.

    This extracts the <mapTheme ...> element from the project's <mapThemeCollection>.
    """
    xml = get_project_xml()
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        raise RuntimeError(f"Failed to parse project XML: {e}")

    # Find mapTheme elements under any namespace
    for elem in root.findall('.//mapTheme'):
        name = elem.get("name")
        if name == theme_name:
            return ET.tostring(elem, encoding="unicode")
    # try lowercase tag fallback (some qgs files may include different casing)
    for elem in root.findall('.//maptheme'):
        name = elem.get("name")
        if name == theme_name:
            return ET.tostring(elem, encoding="unicode")
    return None


def _extract_visible_layer_ids_from_theme_element(maptheme_elem: ET.Element) -> Set[str]:
    """Return set of layer ids that the theme marks as visible/checked.

    The exact tag/attribute names in mapTheme entries can vary across QGIS
    versions; this function heuristically looks for attributes named
    'layerId', 'layerid', or 'id' and for a 'checked'/'visible' attribute.
    """
    visible_ids: Set[str] = set()
    for node in maptheme_elem.iter():
        # gather potential layer id
        lid = None
        for key in ("layerId", "layerid", "id", "layer_id"):
            if key in node.attrib:
                lid = node.attrib.get(key)
                break
        if not lid:
            continue

        # check if this node marks the layer as visible
        # common attributes: checked='1' or visible='1'
        checked = node.attrib.get("checked") or node.attrib.get("visible") or node.attrib.get("isChecked")
        if checked is None:
            # if no explicit checked flag, assume theme lists explicit visible nodes
            # but to be conservative, skip
            continue
        if checked.lower() in ("1", "true", "yes"):
            visible_ids.add(lid)
    return visible_ids


def get_theme_visible_layer_ids(theme_name: str) -> Set[str]:
    """Return set of layer IDs visible in the named theme (empty set if not found).
    """
    xml_str = get_project_xml()
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as e:
        raise RuntimeError(f"Failed to parse project XML: {e}")

    for elem in root.findall('.//mapTheme') + root.findall('.//maptheme'):
        if elem.get("name") == theme_name:
            return _extract_visible_layer_ids_from_theme_element(elem)
    return set()


def merge_apply_theme_additive(theme_name: str, return_xml: bool = False) -> Optional[str]:
    """Apply an additive merge of `theme_name` into the current project.

    Operation:
    - Collect layer IDs marked visible by the named theme.
    - For each such layer ID, set its corresponding layer-tree node to visible.
    - Ensure parent groups are made visible when making a child visible.

    If `return_xml` is True, write the modified project state to a temporary
    .qgs and return its XML string.
    """
    if QgsProject is None:
        raise RuntimeError("This function must be run inside QGIS (PyQGIS available)")

    theme_ids = get_theme_visible_layer_ids(theme_name)
    if not theme_ids:
        raise ValueError(f"Theme '{theme_name}' not found or has no visible layers")

    proj = QgsProject.instance()
    root = proj.layerTreeRoot()

    # Make union: set these theme layers visible in the current layer-tree
    changed = False
    for lid in theme_ids:
        node = root.findLayer(lid)
        if node is None:
            # Try to locate via project mapLayers by id
            lyr = proj.mapLayer(lid)
            if lyr is None:
                # skip missing layers (theme references layer not present)
                continue
            node = root.findLayer(lyr.id())
            if node is None:
                continue
        if not node.isVisible():
            node.setItemVisibilityChecked(True)
            changed = True
        # ensure parent groups are visible
        parent = node.parent()
        while parent is not None:
            try:
                # parent may be a group node
                parent.setItemVisibilityChecked(True)
            except Exception:
                pass
            parent = parent.parent()

    # Optionally return the new project xml representing the merged state
    if return_xml:
        tmp_path = _write_project_to_temp()
        try:
            with open(tmp_path, "r", encoding="utf-8") as fh:
                data = fh.read()
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        return data

    return None


if __name__ == "__main__":
    # quick manual test when executed from QGIS Python console via execfile or import
    print("This module provides functions to merge a map theme into the current project.")


def _extract_layer_visibility_map(maptheme_elem: ET.Element) -> dict:
    """Return a mapping layer_id -> visibility value ('1'/'0') extracted from a mapTheme element.

    The function searches for attributes commonly used to reference layers
    and for visibility flags like 'checked' or 'visible'. If a node for a
    layer lacks explicit checked/visible attributes it is skipped.
    """
    vis = {}
    for node in maptheme_elem.iter():
        lid = None
        for key in ("layerId", "layerid", "id", "layer_id"):
            if key in node.attrib:
                lid = node.attrib.get(key)
                break
        if not lid:
            continue
        # detect visibility flag
        val = None
        for key in ("checked", "visible", "isChecked"):
            if key in node.attrib:
                val = node.attrib.get(key)
                break
        if val is None:
            continue
        # normalize to '1' or '0'
        if str(val).lower() in ("1", "true", "yes"):
            vis[lid] = "1"
        else:
            vis[lid] = "0"
    return vis


def merge_theme_xml_overwrite_visibility(theme_name: str, return_xml: bool = True) -> Optional[str]:
    """Create a merged project XML where visibility attributes are overwritten
    by those declared in the named theme.

    This function does NOT modify the current in-memory QgsProject. It reads
    the current project XML, parses the specified theme's <mapTheme> element,
    then overwrites any element attributes in the project XML that reference
    the same layer ids with the theme's checked/visible flag. The merged XML
    string is returned if `return_xml` is True.

    This is the simplest, XML-based 'overwrite visible flags' strategy the
    user suggested.
    """
    if QgsProject is None:
        raise RuntimeError("This function must be run inside QGIS (PyQGIS available)")

    theme_xml = get_theme_xml(theme_name)
    if theme_xml is None:
        raise ValueError(f"Theme '{theme_name}' not found in project XML")

    try:
        theme_elem = ET.fromstring(theme_xml)
    except ET.ParseError as e:
        raise RuntimeError(f"Failed to parse theme XML: {e}")

    vis_map = _extract_layer_visibility_map(theme_elem)
    if not vis_map:
        raise ValueError(f"Theme '{theme_name}' contains no explicit visibility flags to merge")

    # parse project XML and modify attributes in-place
    proj_xml = get_project_xml()
    try:
        proj_root = ET.fromstring(proj_xml)
    except ET.ParseError as e:
        raise RuntimeError(f"Failed to parse project XML: {e}")

    # Walk all elements and if any element has an id/layerId matching, set checked/visible
    id_keys = ("id", "layerId", "layerid", "layer_id")
    for el in proj_root.iter():
        for k in id_keys:
            if k in el.attrib:
                lid = el.attrib.get(k)
                if lid in vis_map:
                    el.set("checked", vis_map[lid])
                    el.set("visible", vis_map[lid])
                    break

    # Convert tree back to string. Note: ElementTree may omit DOCTYPE; this
    # function returns the modified XML for inspection or for writing to a file.
    merged = ET.tostring(proj_root, encoding="unicode")

    if return_xml:
        return merged
    return None


def apply_theme_visibility_to_project(
    theme_name: str,
    apply_symbol_layers: bool = False,
    mode: str = 'overwrite',
    only_for_layer_ids: Optional[Set[str]] = None,
) -> None:
    """Apply visibility flags from the named theme to the in-memory QgsProject.

    Modes:
    - 'overwrite' (default): set layer visibility to the theme's checked/visible
        value (True or False) for layers referenced by the theme.
    - 'additive': only ensure layers that the theme marks visible are set
        visible in the current project; do NOT set layers to invisible. This
        implements the "追加表示" behaviour (only adds visibility).

    - If `apply_symbol_layers` is True, the function will attempt to parse
        symbol-layer level enabled/visible flags from the theme XML and apply
        them to the layer's renderer where possible. When `mode=='additive'`,
        symbol-layer handling only enables layers marked enabled in the theme
        and does not disable any existing symbol layers.

    This modifies the current QgsProject instance (no project file is written).
    """
    if QgsProject is None:
        raise RuntimeError("This function must be run inside QGIS (PyQGIS available)")

    theme_xml = get_theme_xml(theme_name)
    if theme_xml is None:
        raise ValueError(f"Theme '{theme_name}' not found in project XML")

    try:
        theme_elem = ET.fromstring(theme_xml)
    except ET.ParseError as e:
        raise RuntimeError(f"Failed to parse theme XML: {e}")

    # If overwrite mode requested, use QGIS's native applyTheme (simple theme switch)
    if mode == 'overwrite':
        try:
            proj = QgsProject.instance()
            # get theme collection; API differs, use mapThemeCollection() if available
            theme_collection = None
            try:
                theme_collection = proj.mapThemeCollection()
            except Exception:
                try:
                    theme_collection = proj.mapThemes()
                except Exception:
                    theme_collection = None

            # get layer tree root and UI model if available
            root = proj.layerTreeRoot()
            model = None
            try:
                if iface is not None:
                    model = iface.layerTreeView().layerTreeModel()
            except Exception:
                model = None

            if theme_collection is not None:
                # prefer using theme_collection.applyTheme API when available
                try:
                    # applyTheme may accept (theme_name, root, model)
                    theme_collection.applyTheme(theme_name, root, model)
                    return
                except Exception:
                    # fallback: try theme_collection.applyTheme(theme_name)
                    try:
                        theme_collection.applyTheme(theme_name)
                        return
                    except Exception:
                        pass
        except Exception:
            # if native apply fails, fall back to XML-driven apply below
            pass

    vis_map = _extract_layer_visibility_map(theme_elem)
    if not vis_map:
        raise ValueError(f"Theme '{theme_name}' contains no explicit visibility flags to apply")

    proj = QgsProject.instance()
    root = proj.layerTreeRoot()

    # Apply layer-level visibility
    for lid, val in vis_map.items():
        node = root.findLayer(lid)
        if node is None:
            # try via mapLayer lookup
            lyr = proj.mapLayer(lid)
            if lyr is None:
                # skip missing layers
                continue
            node = root.findLayer(lyr.id())
            if node is None:
                continue
        theme_state = True if str(val) == "1" else False
        try:
            if mode == 'additive':
                # only turn on visibility for layers the theme marks visible
                if theme_state and not node.isVisible():
                    node.setItemVisibilityChecked(True)
            else:
                # overwrite behaviour: set as theme defines (True/False)
                node.setItemVisibilityChecked(theme_state)
        except Exception:
            pass

    # Symbol-layer handling: only for additive mode when apply_symbol_layers=True.
    # Overwrite (テーマ切替) must not change individual symbol-layer enabled flags.
    # If `only_for_layer_ids` is provided, only apply symbol changes for those
    # layer IDs (used by additive flow to avoid touching symbols of layers
    # that remain invisible after the union merge).
    if mode == 'additive' and apply_symbol_layers:
        # Heuristic: find elements in theme XML that carry both a layer id and an
        # enabled/visible attribute for a sub-symbol. We attempt to extract either
        # an index ('symbolIndex'/'index') or an id ('symbolId') to map to symbolLayers.
        symbol_nodes = []
        for node in theme_elem.iter():
            # find candidate symbol entries
            lid = None
            for k in ("layerId", "layerid", "id", "layer_id"):
                if k in node.attrib:
                    lid = node.attrib.get(k)
                    break
            if not lid:
                continue
            enabled = None
            for k in ("enabled", "visible", "checked", "isEnabled"):
                if k in node.attrib:
                    enabled = node.attrib.get(k)
                    break
            if enabled is None:
                continue
            # optional index/id
            sindex = node.attrib.get("symbolIndex") or node.attrib.get("index")
            sid = node.attrib.get("symbolId") or node.attrib.get("symbolLayerId")
            symbol_nodes.append((lid, sindex, sid, enabled))

        # Apply symbol layer visibility where possible
        from qgis.core import QgsMapLayer, QgsVectorLayer

        for lid, sindex, sid, enabled in symbol_nodes:
            # Skip symbol application when a filter set is provided and the
            # theme's layer id is not in it (preserve existing symbol states).
            try:
                if only_for_layer_ids is not None and lid not in only_for_layer_ids:
                    continue
            except Exception:
                if QgsMessageLog:
                    try:
                        QgsMessageLog.logMessage(f"only_for_layer_ids membership test failed for {lid}", "GEO-search-plugin", 1)
                    except Exception:
                        pass
                continue

            lyr = proj.mapLayer(lid)
            if lyr is None:
                # layer referenced by theme not present in project
                continue

            # Only handle vector layers with renderers
            try:
                if not hasattr(lyr, 'renderer'):
                    continue
                renderer = lyr.renderer()
                if renderer is None:
                    continue
                symbol = None
                if hasattr(renderer, 'symbol'):
                    symbol = renderer.symbol()
                if symbol is None:
                    continue
                # symbol.symbolLayers() may return a list; we try index first
                s_layers = []
                if hasattr(symbol, 'symbolLayers'):
                    s_layers = symbol.symbolLayers()

                if sindex is not None:
                    try:
                        idx = int(sindex)
                        if 0 <= idx < len(s_layers):
                            sl = s_layers[idx]
                            if hasattr(sl, 'setEnabled'):
                                # additive: only enable when theme says enabled
                                if str(enabled).lower() in ("1", "true", "yes"):
                                    sl.setEnabled(True)
                    except Exception as e:
                        if QgsMessageLog:
                            try:
                                QgsMessageLog.logMessage(f"symbol layer enable by index failed for layer {lid}: {e}", "GEO-search-plugin", 1)
                            except Exception:
                                pass
                elif sid is not None:
                    # try to match by id attribute if available on symbol layer
                    try:
                        for sl in s_layers:
                            try:
                                # some symbol layer implementations expose 'layerId' or 'id'
                                if getattr(sl, 'id', None) == sid or getattr(sl, 'layerId', None) == sid:
                                    if hasattr(sl, 'setEnabled'):
                                        if str(enabled).lower() in ("1", "true", "yes"):
                                            sl.setEnabled(True)
                                        break
                            except Exception:
                                continue
                    except Exception as e:
                        if QgsMessageLog:
                            try:
                                QgsMessageLog.logMessage(f"symbol layer enable by id failed for layer {lid}: {e}", "GEO-search-plugin", 1)
                            except Exception:
                                pass

                # After changing symbol layer enabled states, trigger layer repaint
                try:
                    lyr.triggerRepaint()
                except Exception:
                    pass
            except Exception as e:
                # Log unexpected errors for diagnostics but continue
                if QgsMessageLog:
                    try:
                        QgsMessageLog.logMessage(f"symbol application unexpected error for layer {lid}: {e}", "GEO-search-plugin", 2)
                    except Exception:
                        pass
                continue


def apply_theme_symbol_layers_additive(theme_name: str, only_for_layer_ids: Optional[Set[str]] = None) -> None:
    """Apply symbol-layer enabled flags declared in the named theme.

    This is a focused, additive-only operation: it will only attempt to
    enable symbol sub-layers that the theme marks enabled, and will NOT
    modify layer visibility or disable any existing symbol layers.

    - `only_for_layer_ids`: if provided, only apply symbol changes for
      those layer IDs (useful to limit changes to layers visible after an
      additive union).
    """
    if QgsProject is None:
        raise RuntimeError("This function must be run inside QGIS (PyQGIS available)")

    # logging helper
    try:
        from qgis.core import QgsMessageLog
    except Exception:
        QgsMessageLog = None

    theme_xml = get_theme_xml(theme_name)
    if theme_xml is None:
        raise ValueError(f"Theme '{theme_name}' not found in project XML")

    try:
        theme_elem = ET.fromstring(theme_xml)
    except ET.ParseError as e:
        raise RuntimeError(f"Failed to parse theme XML: {e}")

    # collect symbol nodes (layer id + optional index/id + enabled flag)
    symbol_nodes = []
    for node in theme_elem.iter():
        lid = None
        for k in ("layerId", "layerid", "id", "layer_id"):
            if k in node.attrib:
                lid = node.attrib.get(k)
                break
        if not lid:
            continue
        enabled = None
        for k in ("enabled", "visible", "checked", "isEnabled"):
            if k in node.attrib:
                enabled = node.attrib.get(k)
                break
        if enabled is None:
            continue
        sindex = node.attrib.get("symbolIndex") or node.attrib.get("index")
        sid = node.attrib.get("symbolId") or node.attrib.get("symbolLayerId")
        symbol_nodes.append((lid, sindex, sid, enabled))

    proj = QgsProject.instance()

    # Apply symbol layer visibility where possible (best-effort)
    for lid, sindex, sid, enabled in symbol_nodes:
        try:
            if only_for_layer_ids is not None and lid not in only_for_layer_ids:
                continue
        except Exception:
            if QgsMessageLog:
                try:
                    QgsMessageLog.logMessage(f"only_for_layer_ids membership test failed for {lid}", "GEO-search-plugin", 1)
                except Exception:
                    pass
            continue

        lyr = proj.mapLayer(lid)
        if lyr is None:
            continue

        try:
            if not hasattr(lyr, 'renderer'):
                continue
            renderer = lyr.renderer()
            if renderer is None:
                continue
            symbol = None
            if hasattr(renderer, 'symbol'):
                symbol = renderer.symbol()
            if symbol is None:
                continue
            s_layers = []
            if hasattr(symbol, 'symbolLayers'):
                s_layers = symbol.symbolLayers()

            if sindex is not None:
                try:
                    idx = int(sindex)
                    if 0 <= idx < len(s_layers):
                        sl = s_layers[idx]
                        if hasattr(sl, 'setEnabled') and str(enabled).lower() in ("1", "true", "yes"):
                            sl.setEnabled(True)
                except Exception as e:
                    if QgsMessageLog:
                        try:
                            QgsMessageLog.logMessage(f"symbol layer enable by index failed for layer {lid}: {e}", "GEO-search-plugin", 1)
                        except Exception:
                            pass
            elif sid is not None:
                try:
                    for sl in s_layers:
                        try:
                            if getattr(sl, 'id', None) == sid or getattr(sl, 'layerId', None) == sid:
                                if hasattr(sl, 'setEnabled') and str(enabled).lower() in ("1", "true", "yes"):
                                    sl.setEnabled(True)
                                break
                        except Exception:
                            continue
                except Exception as e:
                    if QgsMessageLog:
                        try:
                            QgsMessageLog.logMessage(f"symbol layer enable by id failed for layer {lid}: {e}", "GEO-search-plugin", 1)
                        except Exception:
                            pass

            try:
                lyr.triggerRepaint()
            except Exception:
                pass
        except Exception as e:
            if QgsMessageLog:
                try:
                    QgsMessageLog.logMessage(f"symbol application unexpected error for layer {lid}: {e}", "GEO-search-plugin", 2)
                except Exception:
                    pass
            continue


def get_symbol_layer_details(layer) -> list:
    """Return a list of info dicts for each symbol layer of a layer's renderer.

    Each dict contains: index, class_name, enabled (if detectable), and a
    small properties dict (if available). This is best-effort and depends on
    the PyQGIS symbols API present in the running QGIS.
    """
    info = []
    try:
        renderer = layer.renderer()
        if renderer is None:
            return info
        symbol = None
        if hasattr(renderer, 'symbol'):
            symbol = renderer.symbol()
        if symbol is None:
            return info
        # Obtain symbol layers
        s_layers = []
        if hasattr(symbol, 'symbolLayers'):
            s_layers = symbol.symbolLayers()
        for idx, sl in enumerate(s_layers):
            cls = sl.__class__.__name__
            enabled = None
            try:
                if hasattr(sl, 'isEnabled') and callable(getattr(sl, 'isEnabled')):
                    enabled = bool(sl.isEnabled())
                elif hasattr(sl, 'enabled'):
                    attr = getattr(sl, 'enabled')
                    enabled = bool(attr() if callable(attr) else attr)
                else:
                    # try properties dict
                    if hasattr(sl, 'properties') and callable(getattr(sl, 'properties')):
                        props = sl.properties() or {}
                        if 'enabled' in props:
                            enabled = str(props.get('enabled')).lower() in ('1', 'true', 'yes')
            except Exception:
                enabled = None
            props = None
            try:
                if hasattr(sl, 'properties') and callable(getattr(sl, 'properties')):
                    props = sl.properties()
            except Exception:
                props = None
            info.append({
                'index': idx,
                'class': cls,
                'enabled': enabled,
                'properties': props,
            })
    except Exception:
        return info
    return info


def get_all_layers_symbol_info() -> dict:
    """Return a mapping layer_id -> list(symbol layer info dicts).

    Useful to inspect which symbol layers exist and whether enabled state
    can be detected for each layer in the current project.
    """
    if QgsProject is None:
        raise RuntimeError("This function must be run inside QGIS (PyQGIS available)")
    proj = QgsProject.instance()
    out = {}
    for lid, lyr in proj.mapLayers().items():
        try:
            out[lid] = get_symbol_layer_details(lyr)
        except Exception:
            out[lid] = []
    return out


def _get_layer_renderer_xml(layer_id: str) -> Optional[ET.Element]:
    """Return the renderer XML element for the given layer id from project XML, or None."""
    try:
        proj_xml = get_project_xml()
        root = ET.fromstring(proj_xml)
    except Exception:
        return None
    # find maplayer element with matching id attribute
    for ml in root.findall('.//maplayer'):
        if ml.get('id') == layer_id:
            # look for renderer-v2 or renderer child
            r = ml.find('.//renderer-v2') or ml.find('.//renderer')
            return r
    return None


def get_layer_symbol_visibility_from_xml(layer_id: str) -> list:
    """Extract symbol layer enabled flags from project XML for a layer, if present.

    Returns a list aligned with symbol layer indexes; entries are '1' or '0' or None.
    """
    r = _get_layer_renderer_xml(layer_id)
    if r is None:
        return []
    vis = []
    # Look for symbolLayer/tag patterns; heuristically search for 'symbol' nodes with child 'symbolLayer'
    # Some QGIS XML stores <symbol><layers><layer enabled="1">...</layer></layers></symbol>
    # We'll search for any element with attribute 'enabled' or 'visible' under renderer
    for node in r.iter():
        # if node represents a symbol layer element
        if 'enabled' in node.attrib or 'visible' in node.attrib or 'checked' in node.attrib:
            val = node.attrib.get('enabled') or node.attrib.get('visible') or node.attrib.get('checked')
            vis.append(str(val))
    # If none found, try to detect <symbolLayer enabled="..."> patterns specifically
    if not vis:
        for sl in r.findall('.//symbolLayer') + r.findall('.//layer'):
            if 'enabled' in sl.attrib:
                vis.append(str(sl.attrib.get('enabled')))
    return vis


def get_layer_symbol_visibility(layer_id: str, layer_obj=None) -> list:
    """Return best-effort per-symbol-layer visibility for the given layer id.

    Strategy:
    - Try in-memory symbol layer API (`get_symbol_layer_details`) to read enabled flag.
    - If enabled not available, fall back to project XML parsed visibility (`get_layer_symbol_visibility_from_xml`).
    - Return list of dicts: {index, class, enabled (True/False/None), source: 'api'|'xml'|'unknown', properties}
    """
    results = []
    # prefer using provided layer_obj if available
    if layer_obj is None and QgsProject is not None:
        layer_obj = QgsProject.instance().mapLayer(layer_id)

    api_details = []
    if layer_obj is not None:
        try:
            api_details = get_symbol_layer_details(layer_obj)
        except Exception:
            api_details = []

    xml_vis = get_layer_symbol_visibility_from_xml(layer_id)

    # merge by index
    max_n = max(len(api_details), len(xml_vis))
    for i in range(max_n):
        api = api_details[i] if i < len(api_details) else None
        xmlv = xml_vis[i] if i < len(xml_vis) else None
        enabled = None
        source = 'unknown'
        if api is not None and api.get('enabled') is not None:
            enabled = bool(api.get('enabled'))
            source = 'api'
        elif xmlv is not None:
            if str(xmlv).lower() in ('1', 'true', 'yes'):
                enabled = True
            elif str(xmlv).lower() in ('0', 'false', 'no'):
                enabled = False
            else:
                enabled = None
            source = 'xml'
        entry = {
            'index': i,
            'class': api.get('class') if api else None,
            'enabled': enabled,
            'source': source,
            'properties': api.get('properties') if api else None,
        }
        results.append(entry)
    return results


def _symbol_to_brief(symbol):
    """Return a brief dict for a QgsSymbol: its layer count and symbol layer summaries."""
    try:
        if not symbol:
            return None
        s_layers = []
        if hasattr(symbol, 'symbolLayers'):
            s_layers = symbol.symbolLayers()
        layers = []
        for idx, sl in enumerate(s_layers):
            layers.append({
                'index': idx,
                'class': sl.__class__.__name__,
            })
        return {'symbolLayerCount': len(s_layers), 'symbolLayers': layers}
    except Exception:
        return None


def get_renderer_summary(layer) -> dict:
    """Return a summary of the layer's renderer and which symbol(s) it uses.

    The summary includes a `type` (best-effort string) and details depending on
    renderer type:
    - single: symbol brief
    - categorized: list of categories (value, label) with symbol brief
    - graduated: list of ranges with symbol brief
    - rule-based: list of rules (label, filter) with symbol brief

    This helps determine which symbol definitions exist and which are the
    candidates for display. Note: for categorized/graduated/rule-based renderers
    the actual symbol used depends on feature attribute values and map state.
    """
    out = {'type': None}
    try:
        renderer = layer.renderer()
        if renderer is None:
            out['type'] = 'none'
            return out

        clsname = renderer.__class__.__name__
        out['type'] = clsname

        # Single symbol
        if hasattr(renderer, 'symbol') and not hasattr(renderer, 'categories') and not hasattr(renderer, 'rootRule'):
            sym = renderer.symbol()
            out['symbol'] = _symbol_to_brief(sym)
            return out

        # Categorized renderer
        if hasattr(renderer, 'categories'):
            cats = []
            try:
                for c in renderer.categories():
                    try:
                        val = getattr(c, 'value', None)
                    except Exception:
                        val = None
                    try:
                        lab = getattr(c, 'label', None)
                    except Exception:
                        lab = None
                    try:
                        sym = c.symbol()
                    except Exception:
                        sym = None
                    cats.append({'value': val, 'label': lab, 'symbol': _symbol_to_brief(sym)})
            except Exception:
                pass
            out['categories'] = cats
            return out

        # Graduated renderer
        if hasattr(renderer, 'ranges'):
            rngs = []
            try:
                for r in renderer.ranges():
                    try:
                        lower = getattr(r, 'lowerValue', None)
                        upper = getattr(r, 'upperValue', None)
                    except Exception:
                        lower = upper = None
                    try:
                        sym = r.symbol()
                    except Exception:
                        sym = None
                    rngs.append({'lower': lower, 'upper': upper, 'symbol': _symbol_to_brief(sym)})
            except Exception:
                pass
            out['ranges'] = rngs
            return out

        # Rule based
        if hasattr(renderer, 'rootRule'):
            rules = []
            try:
                root = renderer.rootRule()
                children = []
                try:
                    children = root.children()
                except Exception:
                    children = []
                for rule in children:
                    try:
                        lab = getattr(rule, 'label', None)
                    except Exception:
                        lab = None
                    try:
                        filt = getattr(rule, 'filterExpression', None)
                        if callable(filt):
                            filt = filt()
                    except Exception:
                        try:
                            filt = getattr(rule, 'filterExpression', None)
                        except Exception:
                            filt = None
                    try:
                        sym = rule.symbol()
                    except Exception:
                        sym = None
                    rules.append({'label': lab, 'filter': filt, 'symbol': _symbol_to_brief(sym)})
            except Exception:
                pass
            out['rules'] = rules
            return out

        # Fallback: include any accessible symbol
        try:
            sym = renderer.symbol() if hasattr(renderer, 'symbol') else None
            out['symbol'] = _symbol_to_brief(sym)
        except Exception:
            pass
    except Exception:
        out['error'] = True
    return out


def get_all_renderers_summary() -> dict:
    """Return renderer summaries for all layers in the current project.

    Returns a dict layer_id -> renderer summary (see `get_renderer_summary`).
    """
    if QgsProject is None:
        raise RuntimeError("This function must be run inside QGIS (PyQGIS available)")
    proj = QgsProject.instance()
    out = {}
    for lid, lyr in proj.mapLayers().items():
        try:
            out[lid] = get_renderer_summary(lyr)
        except Exception:
            out[lid] = {'error': True}
    return out


def get_layer_symbol_overview(layer_id: str, layer_obj=None) -> dict:
    """Return a structured overview of symbol candidates for the layer.

    The overview includes renderer type and a list of symbol entries. For
    complex renderers (categorized, graduated, rule-based) each category/rule
    produces an entry with a brief of its symbol (symbol layer count and
    layer classes). This helps inspect which symbol definitions exist even
    when there are no features to sample.

    Returns dict: {'renderer_type': str, 'symbols': [ {source, index, label, symbol_brief, symbol_layer_details} ]}
    """
    if QgsProject is None:
        raise RuntimeError("This function must be run inside QGIS (PyQGIS available)")

    proj = QgsProject.instance()
    if layer_obj is None:
        layer_obj = proj.mapLayer(layer_id)
    if layer_obj is None:
        raise ValueError(f"Layer not found: {layer_id}")

    out = {'renderer_type': None, 'symbols': []}
    try:
        renderer = layer_obj.renderer()
        if renderer is None:
            out['renderer_type'] = 'none'
            return out
        clsname = renderer.__class__.__name__
        out['renderer_type'] = clsname

        # Helper to produce symbol-layer details list from a QgsSymbol instance
        def _symbol_layers_from_symbol(sym):
            try:
                return _symbol_to_brief(sym)
            except Exception:
                return None

        # Single symbol
        if hasattr(renderer, 'symbol') and not hasattr(renderer, 'categories') and not hasattr(renderer, 'rootRule'):
            sym = None
            try:
                sym = renderer.symbol()
            except Exception:
                sym = None
            out['symbols'].append({'source': 'single', 'index': 0, 'label': None, 'symbol_brief': _symbol_layers_from_symbol(sym), 'symbol_layer_details': None})
            return out

        # Categorized
        if hasattr(renderer, 'categories'):
            try:
                for idx, c in enumerate(renderer.categories() or []):
                    try:
                        lab = getattr(c, 'label', None)
                    except Exception:
                        lab = None
                    try:
                        sym = c.symbol()
                    except Exception:
                        sym = None
                    out['symbols'].append({'source': 'categorized', 'index': idx, 'label': lab, 'symbol_brief': _symbol_layers_from_symbol(sym), 'symbol_layer_details': None})
            except Exception:
                pass
            return out

        # Graduated
        if hasattr(renderer, 'ranges'):
            try:
                for idx, r in enumerate(renderer.ranges() or []):
                    try:
                        lab = f"{getattr(r, 'lowerValue', None)} - {getattr(r, 'upperValue', None)}"
                    except Exception:
                        lab = None
                    try:
                        sym = r.symbol()
                    except Exception:
                        sym = None
                    out['symbols'].append({'source': 'graduated', 'index': idx, 'label': lab, 'symbol_brief': _symbol_layers_from_symbol(sym), 'symbol_layer_details': None})
            except Exception:
                pass
            return out

        # Rule-based
        if hasattr(renderer, 'rootRule'):
            try:
                root = renderer.rootRule()
                children = []
                try:
                    children = root.children()
                except Exception:
                    children = []
                for idx, rule in enumerate(children):
                    try:
                        lab = getattr(rule, 'label', None)
                    except Exception:
                        lab = None
                    try:
                        sym = rule.symbol()
                    except Exception:
                        sym = None
                    # for each rule include the symbol brief and, if possible, per-layer details
                    sym_brief = _symbol_layers_from_symbol(sym)
                    # try to get per-symbol-layer enabled info by creating a temporary entry
                    sym_layer_details = None
                    try:
                        if sym is not None and hasattr(sym, 'symbolLayers'):
                            s_layers = sym.symbolLayers()
                            details = []
                            for sidx, sl in enumerate(s_layers):
                                en = None
                                try:
                                    if hasattr(sl, 'isEnabled') and callable(getattr(sl, 'isEnabled')):
                                        en = bool(sl.isEnabled())
                                    elif hasattr(sl, 'enabled'):
                                        attr = getattr(sl, 'enabled')
                                        en = bool(attr() if callable(attr) else attr)
                                except Exception:
                                    en = None
                                details.append({'index': sidx, 'class': sl.__class__.__name__, 'enabled': en})
                            sym_layer_details = details
                    except Exception:
                        sym_layer_details = None

                    out['symbols'].append({'source': 'rule', 'index': idx, 'label': lab, 'symbol_brief': sym_brief, 'symbol_layer_details': sym_layer_details})
            except Exception:
                pass
            return out

        # Fallback: include accessible symbol if any
        try:
            sym = renderer.symbol() if hasattr(renderer, 'symbol') else None
            out['symbols'].append({'source': 'fallback', 'index': 0, 'label': None, 'symbol_brief': _symbol_layers_from_symbol(sym), 'symbol_layer_details': None})
        except Exception:
            pass
    except Exception:
        out['error'] = True
    return out


def sample_layer_symbol_usage(layer_id: str, max_features: int = 10) -> list:
    """Sample features in the current map canvas extent and return which symbol
    is used for each sampled feature.

    Returns a list of dicts: {'fid': feature.id(), 'symbol': symbol_brief}
    If the layer is not a vector layer or no features found, returns empty list.
    """
    if QgsProject is None:
        raise RuntimeError("This function must be run inside QGIS (PyQGIS available)")

    proj = QgsProject.instance()
    lyr = proj.mapLayer(layer_id)
    if lyr is None:
        return []

    # Only vector-like layers have features and renderers that support symbolForFeature
    try:
        from qgis.core import QgsFeatureRequest, QgsRenderContext
        from qgis.PyQt.QtCore import QRectF
        # map settings / render context
        ms = None
        try:
            ms = iface.mapCanvas().mapSettings()
        except Exception:
            ms = None
        ctx = None
        if ms is not None and hasattr(QgsRenderContext, 'fromMapSettings'):
            try:
                ctx = QgsRenderContext.fromMapSettings(ms)
            except Exception:
                ctx = None

        # sample features within canvas extent if possible
        req = QgsFeatureRequest()
        try:
            if ms is not None:
                rect = iface.mapCanvas().extent()
                req.setFilterRect(rect)
        except Exception:
            pass
        req.setLimit(max_features)

        feats = []
        for f in lyr.getFeatures(req):
            feats.append(f)
            if len(feats) >= max_features:
                break

        results = []
        renderer = None
        try:
            renderer = lyr.renderer()
        except Exception:
            renderer = None

        for f in feats:
            sym = None
            try:
                if renderer is not None and ctx is not None and hasattr(renderer, 'symbolForFeature'):
                    sym = renderer.symbolForFeature(f, ctx)
                elif renderer is not None and hasattr(renderer, 'symbolForFeature'):
                    # try without context
                    sym = renderer.symbolForFeature(f)
            except Exception:
                sym = None
            brief = _symbol_to_brief(sym)
            results.append({'fid': f.id(), 'symbol': brief})
        return results
    except Exception:
        return []


def set_symbol_layer_enabled(layer_id: str, index: int, enabled: bool) -> bool:
    """Set enabled state for a specific symbol layer by index on a layer.

    Returns True if successful, False otherwise.
    """
    if QgsProject is None:
        return False
    proj = QgsProject.instance()
    lyr = proj.mapLayer(layer_id)
    if lyr is None:
        return False
    try:
        renderer = lyr.renderer()
        if renderer is None:
            return False
        symbol = renderer.symbol() if hasattr(renderer, 'symbol') else None
        if symbol is None:
            return False
        if not hasattr(symbol, 'symbolLayers'):
            return False
        s_layers = symbol.symbolLayers()
        if not (0 <= index < len(s_layers)):
            return False
        sl = s_layers[index]
        if hasattr(sl, 'setEnabled'):
            sl.setEnabled(bool(enabled))
            try:
                lyr.triggerRepaint()
            except Exception:
                pass
            return True
    except Exception:
        return False
    return False


def enable_all_symbol_layers_for_layer(layer_id: str) -> int:
    """Enable all symbol layers for the given layer id.

    Returns the number of symbol layers successfully enabled.
    """
    if QgsProject is None:
        return 0
    proj = QgsProject.instance()
    lyr = proj.mapLayer(layer_id)
    if lyr is None:
        return 0
    count = 0
    try:
        renderer = lyr.renderer()
        if renderer is None:
            return 0
        symbol = renderer.symbol() if hasattr(renderer, 'symbol') else None
        if symbol is None:
            return 0
        if not hasattr(symbol, 'symbolLayers'):
            return 0
        s_layers = symbol.symbolLayers()
        for sl in s_layers:
            try:
                if hasattr(sl, 'setEnabled'):
                    sl.setEnabled(True)
                    count += 1
            except Exception:
                continue
        try:
            lyr.triggerRepaint()
        except Exception:
            pass
    except Exception:
        return count
    return count


def enable_all_symbol_layers_for_all_layers() -> int:
    """Enable all symbol layers for all layers in the current project.

    Returns the total number of symbol layers enabled across all layers.
    """
    if QgsProject is None:
        return 0
    proj = QgsProject.instance()
    total = 0
    for lid, lyr in proj.mapLayers().items():
        try:
            total += enable_all_symbol_layers_for_layer(lid)
        except Exception:
            continue
    return total

