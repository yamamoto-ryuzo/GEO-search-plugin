# -*- coding: utf-8 -*-
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
