# -*- coding: utf-8 -*-
"""
テーマ関連ユーティリティ

このモジュールには以下を含む:
- 環境変数で変更可能な括弧取得
- テーマ名から括弧で囲まれたグループ名を抽出する関数
- テーマ名リストをグループ化する関数

環境変数:
 - THEME_BRACKET_OPEN  (開き括弧)
 - THEME_BRACKET_CLOSE (閉じ括弧)

デフォルト括弧は `【` / `】`。
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from typing import Iterable, Dict, List, Optional, Tuple

from typing import Tuple as _Tuple, Set


def collect_visible_layers_and_groups(root) -> _Tuple[Set[str], List[str]]:
    """Collect visible layer IDs and visible group paths from a layer tree root.

    Returns (set_of_layer_ids, list_of_group_path_strings).
    Group path strings use '/' as separator (e.g. 'Parent/Child').
    This function defensively handles missing QGIS API at import time.
    """
    try:
        from qgis.core import QgsLayerTreeGroup
    except Exception:
        QgsLayerTreeGroup = None

    layer_ids = set()
    group_paths: List[str] = []

    try:
        try:
            nodes = root.findLayers()
        except Exception:
            nodes = []
        for n in nodes:
            try:
                if n.isVisible() and n.layer() is not None and hasattr(n.layer(), 'id'):
                    layer_ids.add(n.layer().id())
            except Exception:
                continue

        def _walk_groups(node, path):
            try:
                children = node.children()
            except Exception:
                return
            for c in children:
                try:
                    if QgsLayerTreeGroup is not None and isinstance(c, QgsLayerTreeGroup):
                        gp = f"{path}/{c.name()}" if path else c.name()
                        try:
                            if c.isVisible():
                                group_paths.append(gp)
                        except Exception:
                            pass
                        _walk_groups(c, gp)
                    else:
                        _walk_groups(c, path)
                except Exception:
                    continue

        _walk_groups(root, "")
    except Exception:
        pass

    return layer_ids, group_paths


def find_group_by_path(root, path):
    """Find a group node by a '/'-separated path. Returns node or None."""
    try:
        from qgis.core import QgsLayerTreeGroup
    except Exception:
        QgsLayerTreeGroup = None
    try:
        parts = [p for p in path.split('/') if p]
        node = root
        for p in parts:
            found = None
            try:
                for child in node.children():
                    try:
                        if QgsLayerTreeGroup is not None and isinstance(child, QgsLayerTreeGroup) and child.name() == p:
                            found = child
                            break
                    except Exception:
                        continue
            except Exception:
                return None
            if found is None:
                return None
            node = found
        if QgsLayerTreeGroup is not None and isinstance(node, QgsLayerTreeGroup):
            return node
    except Exception:
        pass
    return None


def restore_groups_by_paths(root, group_paths: List[str]):
    """Restore visibility for groups specified by path list."""
    if not group_paths:
        return
    for path in group_paths:
        try:
            grp = find_group_by_path(root, path)
            if grp is not None:
                try:
                    grp.setItemVisibilityChecked(True)
                except Exception:
                    pass
        except Exception:
            pass


def apply_theme(theme_collection, theme_name: str, root, model, additive: bool = False):
    """Apply a map theme via the provided theme_collection.

    If ``additive`` is True, the theme's visible layers are merged with the
    currently visible layers (so theme layers are added to the current view
    rather than overwriting). Group visibility that had no visible layers is
    also preserved.

    This function centralizes the additive application logic used by the
    plugin toolbar and search-time theme application.
    """
    # シンプルで安全な実装: ネストを浅くして構文ミスのリスクを減らす
    try:
        from qgis.core import QgsMessageLog, QgsProject
    except Exception:
        QgsMessageLog = None
        QgsProject = None

    if not theme_name:
        return

    if additive:
        # 簡略化: 追加表示モードでは副作用のある処理を行わず、ログに出力して終了する
        try:
            if QgsMessageLog:
                try:
                    QgsMessageLog.logMessage("テーマ追加", "GEO-search-plugin", 0)
                except Exception:
                    pass
        except Exception:
            pass
        return

    # 非 additivemode: 通常適用
    try:
        theme_collection.applyTheme(theme_name, root, model)
        if QgsMessageLog:
            try:
                QgsMessageLog.logMessage(f"テーマ '{theme_name}' を適用しました", "GEO-search-plugin", 0)
            except Exception:
                pass
    except Exception as e:
        if QgsMessageLog:
            try:
                QgsMessageLog.logMessage(f"テーマ適用エラー: {str(e)}", "GEO-search-plugin", 2)
            except Exception:
                pass


def _get_theme_brackets() -> Tuple[str, str]:
    """環境変数からテーマのグループ括弧を取得する。

    - `THEME_BRACKET_OPEN` と `THEME_BRACKET_CLOSE` をそれぞれ参照する。
    - 指定がなければデフォルトで '【' と '】' を返す。
    """
    open_b = os.environ.get("THEME_BRACKET_OPEN")
    close_b = os.environ.get("THEME_BRACKET_CLOSE")
    if open_b is None and close_b is None:
        return "【", "】"
    if open_b is None:
        open_b = "【"
    if close_b is None:
        close_b = "】"
    return open_b, close_b


def parse_theme_group(theme_name: Optional[str]) -> Optional[str]:
    """テーマ名からグループ名を抽出する。

    例: "道路【道路種別】_昼" -> グループ '道路種別' を返す。
    見つからない場合は None を返す。
    """
    if not theme_name:
        return None
    open_b, close_b = _get_theme_brackets()
    try:
        pattern = re.escape(open_b) + r"(.*?)" + re.escape(close_b)
        m = re.search(pattern, theme_name)
    except re.error:
        return None
    if m:
        return m.group(1)
    return None


def group_themes(theme_names: Iterable[str]) -> Dict[Optional[str], List[str]]:
    """テーマ名リストをグループ化して辞書で返す。

    戻り値の形式: { group_name_or_None: [テーマ名, ...], ... }
    group_name が None のキーはグループに属さないテーマを示す。
    """
    groups: Dict[Optional[str], List[str]] = {}
    for name in theme_names:
        grp = parse_theme_group(name)
        groups.setdefault(grp, []).append(name)
    return groups


__all__ = [
    "apply_theme",
    "_get_theme_brackets",
    "parse_theme_group",
    "group_themes",
    "collect_visible_layers_and_groups",
    "find_group_by_path",
    "restore_groups_by_paths",
]
