# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QVariant

from qgis.core import QgsProject, QgsFeatureRequest
from qgis.utils import iface
import os
import re


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


def _get_theme_brackets():
    """環境変数からテーマのグループ括弧を取得する。

    - `THEME_BRACKET_OPEN` と `THEME_BRACKET_CLOSE` をそれぞれ参照する。
    - 指定がなければデフォルトで '【' と '】' を返す。
    """
    open_b = os.environ.get("THEME_BRACKET_OPEN")
    close_b = os.environ.get("THEME_BRACKET_CLOSE")
    if open_b is None and close_b is None:
        return "【", "】"
    # 部分的にしか与えられない場合は片側だけ上書き
    if open_b is None:
        open_b = "【"
    if close_b is None:
        close_b = "】"
    return open_b, close_b


def parse_theme_group(theme_name):
    """テーマ名からグループ名を抽出する。

    例: "道路【道路種別】_昼" -> グループ '道路種別' を返す。
    見つからない場合は None を返す。
    """
    if not theme_name:
        return None
    open_b, close_b = _get_theme_brackets()
    # 正規表現で最初の開閉ペアを抽出（非貪欲）
    try:
        pattern = re.escape(open_b) + r"(.*?)" + re.escape(close_b)
        m = re.search(pattern, theme_name)
    except re.error:
        # 万が一環境変数で与えられた文字列が正規表現として扱えない場合の保険
        return None
    if m:
        return m.group(1)
    return None


def group_themes(theme_names):
    """テーマ名リストをグループ化して辞書で返す。

    戻り値の形式: { group_name_or_None: [テーマ名, ...], ... }
    group_name が None のキーはグループに属さないテーマを示す。
    """
    groups = {}
    for name in theme_names:
        grp = parse_theme_group(name)
        groups.setdefault(grp, []).append(name)
    return groups
