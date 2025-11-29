# -*- coding: utf-8 -*-
import os
import json
import shutil
import tempfile
import datetime

from qgis.PyQt.QtCore import QVariant

from qgis.core import QgsProject, QgsFeatureRequest
from qgis.utils import iface

# テーマ関連ユーティリティは `geo_search.theme` に移動しました。互換のため再エクスポートします。
from .theme import parse_theme_group, group_themes


def name2layer(name):
    project = QgsProject.instance()
    layers = project.mapLayersByName(name)
    for layer in layers:
        return layer


def name2layers(name):
    """指定した名前の全てのレイヤを取得する"""
    project = QgsProject.instance()
    layers = project.mapLayersByName(name)
    return layers


def unique_values(layer, field_name):
    fields = layer.fields()
    field_index = fields.indexFromName(field_name)
    if field_index == -1:
        return []
    attrs = []
    for attr in layer.uniqueValues(field_index):
        if isinstance(attr, QVariant) and attr.isNull():
            continue
        if attr is None:
            continue
        attrs.append(attr)
    return attrs


def get_feature_by_id(layer, feature_id):
    request = QgsFeatureRequest()
    request.setFilterFid(feature_id)
    for feature in layer.getFeatures(request):
        return feature


# `parse_theme_group` と `group_themes` は `geo_search.theme` に移しました。


def set_project_variable(project, key, value, group='GEO-search-plugin'):
    """Robustly set a project-scoped variable across QGIS versions.

    Tries multiple methods for compatibility: QgsExpressionContextUtils.setProjectVariable,
    projectScope().setVariable, project.writeEntry, project.setCustomProperty.
    Returns True if any method succeeded.
    """
    ok = False
    try:
        from qgis.core import QgsExpressionContextUtils
    except Exception:
        QgsExpressionContextUtils = None

    # 1) try class-level API
    try:
        if QgsExpressionContextUtils is not None:
            try:
                QgsExpressionContextUtils.setProjectVariable(project, key, value)
                ok = True
            except Exception:
                pass
    except Exception:
        pass

    # 2) try projectScope().setVariable
    try:
        if QgsExpressionContextUtils is not None:
            try:
                scope = QgsExpressionContextUtils.projectScope(project)
                if hasattr(scope, 'setVariable'):
                    scope.setVariable(key, value)
                    ok = True
            except Exception:
                pass
    except Exception:
        pass

    # 3) try writeEntry
    try:
        try:
            project.writeEntry(group, key, value)
            ok = True
        except Exception:
            pass
    except Exception:
        pass
    return ok


def remove_entry_from_json_file(path, title=None, src_idx=None, container_key='SearchTabs', parent=None, logger=None):
    """Remove an entry from a JSON file safely.

    - path: file path to edit
    - title: optional Title to match when src_idx not provided
    - src_idx: optional integer index to remove directly
    - container_key: when file is a dict with this key containing list, use that list
    - parent: optional QWidget used for showing QMessageBox warnings
    - logger: optional callable(message, level) for logging (level: 0/info,1/warn,2/error)

    Returns True on success, False on failure.
    """
    try:
        # Read file content
        with open(path, 'r', encoding='utf-8') as fh:
            text = fh.read()
        try:
            data = json.loads(text)
        except Exception as e:
            # attempt tolerant parsing of multiple top-level JSON values
            try:
                decoder = json.JSONDecoder()
                objs = []
                s = text
                pos = 0
                L = len(s)
                while pos < L:
                    while pos < L and s[pos].isspace():
                        pos += 1
                    if pos >= L:
                        break
                    obj, end = decoder.raw_decode(s, pos)
                    objs.append(obj)
                    pos = end
                    while pos < L and s[pos] in ', \t\r\n ':
                        pos += 1

                if len(objs) == 0:
                    raise ValueError("no JSON objects found")
                if len(objs) == 1:
                    data = objs[0]
                else:
                    merged = []
                    for o in objs:
                        if isinstance(o, dict) and isinstance(o.get(container_key), list):
                            merged.extend(o.get(container_key))
                        elif isinstance(o, list):
                            merged.extend(o)
                        elif isinstance(o, dict):
                            merged.append(o)
                        else:
                            merged.append(o)
                    data = merged
            except Exception:
                if parent is not None:
                    try:
                        from qgis.PyQt.QtWidgets import QMessageBox
                        QMessageBox.warning(parent, "Read error", f"Failed to read the JSON file: {e}")
                    except Exception:
                        pass
                return False
    except Exception as e:
        if parent is not None:
            try:
                from qgis.PyQt.QtWidgets import QMessageBox
                QMessageBox.warning(parent, "Read error", f"Failed to read the JSON file: {e}")
            except Exception:
                pass
        return False

    # Determine target list
    if isinstance(data, dict) and isinstance(data.get(container_key), list):
        target = data[container_key]
        container_is_dict = True
    elif isinstance(data, list):
        target = data
        container_is_dict = False
    else:
        if parent is not None:
            try:
                from qgis.PyQt.QtWidgets import QMessageBox
                QMessageBox.warning(parent, "Unsupported format", "JSON file has unsupported structure; expected {'SearchTabs': [...]} or an array.")
            except Exception:
                pass
        return False

    remove_idx = None
    if isinstance(src_idx, int) and 0 <= src_idx < len(target):
        remove_idx = int(src_idx)

    if remove_idx is None and title:
        for i, it in enumerate(target):
            try:
                if isinstance(it, dict) and it.get('Title') == title:
                    remove_idx = i
                    break
            except Exception:
                continue

    if remove_idx is None:
        if parent is not None:
            try:
                from qgis.PyQt.QtWidgets import QMessageBox
                QMessageBox.information(parent, "Not found", "Could not find corresponding entry to remove.")
            except Exception:
                pass
        return False

    # Backup
    try:
        bak_name = f"{os.path.basename(path)}.{datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.bak"
        bak_path = os.path.join(os.path.dirname(path), bak_name)
        shutil.copy2(path, bak_path)
    except Exception:
        bak_path = None

    # Remove and write atomically
    try:
        del target[remove_idx]
        out = data if container_is_dict else target
        dirn = os.path.dirname(path) or '.'
        fd, tmp_path = tempfile.mkstemp(prefix='geo_search_', dir=dirn, text=True)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as tmpfh:
                json.dump(out, tmpfh, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
    except Exception as e:
        if parent is not None:
            try:
                from qgis.PyQt.QtWidgets import QMessageBox
                QMessageBox.warning(parent, "Write error", f"Failed to update JSON file: {e}")
            except Exception:
                pass
        try:
            if bak_path and os.path.exists(bak_path):
                shutil.copy2(bak_path, path)
        except Exception:
            pass
        return False

    # Log
    try:
        if logger and callable(logger):
            logger(f"Removed entry index={remove_idx} from file: {path} (backup={bak_path})", 0)
        else:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"Removed entry index={remove_idx} from file: {path} (backup={bak_path})", 'GEO-search-plugin', 0)
            except Exception:
                pass
    except Exception:
        pass

    return True
