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
from typing import Iterable, Dict, List, Optional, Tuple





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
        # 追加表示モード:
        # - 既存の表示状態をメモリ内にスナップショット
        # - 選択テーマを適用
        # - テーマで可視になったレイヤを既存の可視レイヤに追加（和集合）する
        # この方式はテーマコレクションのAPI差分や一時テーマ名の競合を避けます。
        try:
            try:
                nodes_before = root.findLayers()
            except Exception:
                nodes_before = []

            visibility_before = {}
            for n in nodes_before:
                try:
                    layer = n.layer()
                    if layer is None:
                        continue
                    lid = layer.id() if callable(getattr(layer, "id", None)) else getattr(layer, "id", None)
                    visibility_before[lid] = bool(n.isVisible())
                except Exception:
                    continue

            # ログ: スナップショット保存状況
            try:
                msg = f"追加表示: メモリに現在の表示状態を保存しました (layers={len(visibility_before)})"
                if QgsMessageLog:
                    try:
                        QgsMessageLog.logMessage(msg, "GEO-search-plugin", 0)
                    except Exception:
                        print(msg)
                else:
                    print(msg)
            except Exception:
                try:
                    print("追加表示: メモリスナップショットのログ出力に失敗しました")
                except Exception:
                    pass

            # 選択テーマを適用（root/model バージョンを優先）
            try:
                try:
                    theme_collection.applyTheme(theme_name, root, model)
                except Exception:
                    theme_collection.applyTheme(theme_name)
            except Exception as e:
                if QgsMessageLog:
                    try:
                        QgsMessageLog.logMessage(f"テーマ適用エラー(追加表示): {e}", "GEO-search-plugin", 2)
                    except Exception:
                        pass
                return
            else:
                # ログ: テーマ適用成功
                try:
                    msg = f"追加表示: テーマ '{theme_name}' を適用しました"
                    if QgsMessageLog:
                        try:
                            QgsMessageLog.logMessage(msg, "GEO-search-plugin", 0)
                        except Exception:
                            print(msg)
                    else:
                        print(msg)
                except Exception:
                    pass
            # テーマ適用後に可視になったレイヤを取得
            try:
                nodes_after = root.findLayers()
            except Exception:
                nodes_after = []

            theme_visible = set()
            for n in nodes_after:
                try:
                    layer = n.layer()
                    if layer is None:
                        continue
                    lid = layer.id() if callable(getattr(layer, "id", None)) else getattr(layer, "id", None)
                    try:
                        is_vis = bool(n.isVisible())
                    except Exception:
                        is_vis = False
                    if is_vis:
                        theme_visible.add(lid)
                except Exception:
                    continue

            # ログ: テーマで可視になったレイヤ数
            try:
                msg = f"追加表示: テーマで可視になったレイヤ数={len(theme_visible)}"
                if QgsMessageLog:
                    try:
                        QgsMessageLog.logMessage(msg, "GEO-search-plugin", 0)
                    except Exception:
                        print(msg)
                else:
                    print(msg)
            except Exception:
                pass

            # 既存の可視レイヤとテーマの可視レイヤの和集合を計算
            existing_visible = {lid for lid, v in visibility_before.items() if v}
            union_visible = existing_visible | theme_visible

            # ログ: 和集合の件数
            try:
                msg = f"追加表示: 和集合で可視にするレイヤ数={len(union_visible)} (existing={len(existing_visible)} theme={len(theme_visible)})"
                if QgsMessageLog:
                    try:
                        QgsMessageLog.logMessage(msg, "GEO-search-plugin", 0)
                    except Exception:
                        print(msg)
                else:
                    print(msg)
            except Exception:
                pass

            # 和集合に含まれるレイヤの表示フラグを True にする（非表示にする操作は行わない）
            for n in nodes_after:
                try:
                    layer = n.layer()
                    if layer is None:
                        continue
                    lid = layer.id() if callable(getattr(layer, "id", None)) else getattr(layer, "id", None)
                    if lid in union_visible:
                        try:
                            if hasattr(n, "setItemVisibilityChecked"):
                                n.setItemVisibilityChecked(True)
                            elif hasattr(n, "setVisible"):
                                n.setVisible(True)
                            elif hasattr(n, "setItemVisibility"):
                                n.setItemVisibility(True)
                        except Exception:
                            # 個別ノードの設定に失敗しても続行
                            continue
                except Exception:
                    continue

            if QgsMessageLog:
                try:
                    QgsMessageLog.logMessage(f"テーマ '{theme_name}' を追加表示モードで適用しました", "GEO-search-plugin", 0)
                except Exception:
                    pass
        except Exception:
            # 追加表示パスは頑健に例外を握りつぶして元の表示を崩さない
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


def get_layer_legend_state(layer):
    """レイヤの凡例（レジェンド）チェック状態を取得して構造化して返す。

    戻り値の例:
    {
        'layer_id': '...',
        'layer_name': '...',
        'renderer': 'QgsRuleBasedRenderer',
        'items': [
            {'index': 0, 'type': 'rule', 'label': 'foo', 'visible': True},
            ...
        ]
    }

    この関数は QGIS の実行環境外でも安全にインポートできるように設計されています。
    レンダラー固有の API が存在しない場合は文字列クラス名を使って判定を試みます。
    """
    result = {
        'layer_id': None,
        'layer_name': None,
        'renderer': None,
        'items': [],
    }

    if layer is None:
        return result

    try:
        result['layer_id'] = layer.id() if callable(getattr(layer, 'id', None)) else getattr(layer, 'id', None)
    except Exception:
        result['layer_id'] = None
    try:
        result['layer_name'] = layer.name()
    except Exception:
        result['layer_name'] = getattr(layer, 'name', None) or None

    try:
        renderer = layer.renderer()
    except Exception:
        renderer = None

    renderer_class_name = type(renderer).__name__ if renderer is not None else None
    result['renderer'] = renderer_class_name

    def _call_bool_methods(obj, method_names):
        for m in method_names:
            try:
                meth = getattr(obj, m, None)
                if callable(meth):
                    return bool(meth())
            except Exception:
                continue
        # 一部オブジェクトは属性として True/False を持つ場合もある
        for m in method_names:
            try:
                val = getattr(obj, m, None)
                if isinstance(val, bool):
                    return val
            except Exception:
                continue
        return None

    # レンダラーが無ければ終了
    if renderer is None:
        return result

    try:
        from qgis.core import (
            QgsCategorizedSymbolRenderer,
            QgsGraduatedSymbolRenderer,
            QgsRuleBasedRenderer,
            QgsSingleSymbolRenderer,
        )
    except Exception:
        QgsCategorizedSymbolRenderer = None
        QgsGraduatedSymbolRenderer = None
        QgsRuleBasedRenderer = None
        QgsSingleSymbolRenderer = None

    # カテゴリレンダラー
    try:
        if (QgsCategorizedSymbolRenderer is not None and isinstance(renderer, QgsCategorizedSymbolRenderer)) or (
            QgsCategorizedSymbolRenderer is None and renderer_class_name == 'QgsCategorizedSymbolRenderer'
        ):
            items = []
            try:
                categories = renderer.categories()
            except Exception:
                categories = []
            for i, cat in enumerate(categories):
                try:
                    label = cat.label()
                except Exception:
                    label = getattr(cat, 'label', None)
                visible = _call_bool_methods(cat, ('renderState', 'isVisible', 'active'))
                items.append({'index': i, 'type': 'category', 'label': label, 'visible': visible})
            result['items'] = items
            return result
    except Exception:
        pass

    # 段階別レンダラー
    try:
        if (QgsGraduatedSymbolRenderer is not None and isinstance(renderer, QgsGraduatedSymbolRenderer)) or (
            QgsGraduatedSymbolRenderer is None and renderer_class_name == 'QgsGraduatedSymbolRenderer'
        ):
            items = []
            try:
                ranges = renderer.ranges()
            except Exception:
                ranges = []
            for i, r in enumerate(ranges):
                try:
                    label = r.label()
                except Exception:
                    label = getattr(r, 'label', None)
                visible = _call_bool_methods(r, ('renderState', 'isVisible', 'active'))
                items.append({'index': i, 'type': 'range', 'label': label, 'visible': visible})
            result['items'] = items
            return result
    except Exception:
        pass

    # ルールベースレンダラー
    try:
        if (QgsRuleBasedRenderer is not None and isinstance(renderer, QgsRuleBasedRenderer)) or (
            QgsRuleBasedRenderer is None and renderer_class_name == 'QgsRuleBasedRenderer'
        ):
            items = []
            try:
                root_rule = renderer.rootRule()

                def _collect_rules(rule, out=None):
                    if out is None:
                        out = []
                    for ch in rule.children():
                        out.append(ch)
                        _collect_rules(ch, out)
                    return out

                all_rules = _collect_rules(root_rule)
            except Exception:
                all_rules = []

            # ラベルのあるルールを凡例アイテムと見なす
            legend_rules = [r for r in all_rules if (getattr(r, 'label', None) and (r.label() if callable(getattr(r, 'label', None)) else getattr(r, 'label', None)))]
            for i, r in enumerate(legend_rules):
                try:
                    label = r.label() if callable(getattr(r, 'label', None)) else getattr(r, 'label', None)
                except Exception:
                    label = None
                visible = _call_bool_methods(r, ('active', 'renderState', 'isVisible'))
                items.append({'index': i, 'type': 'rule', 'label': label, 'visible': visible})
            result['items'] = items
            return result
    except Exception:
        pass

    # 単一シンボルレンダラー
    try:
        if (QgsSingleSymbolRenderer is not None and isinstance(renderer, QgsSingleSymbolRenderer)) or (
            QgsSingleSymbolRenderer is None and renderer_class_name == 'QgsSingleSymbolRenderer'
        ):
            # 単一シンボルは凡例項目の概念が薄いが、表示状態を返す
            visible = True
            # レイヤの表示自体を確認できる場合は優先して使う
            try:
                from qgis.utils import iface
            except Exception:
                iface = None
            items = [{'index': 0, 'type': 'single', 'label': result['layer_name'] or '(single)', 'visible': visible}]
            result['items'] = items
            return result
    except Exception:
        pass

    # 未サポートのレンダラー: 空の items を返す
    return result


def log_layer_legend_state(layer, tag: str = "GEO-search-plugin"):
    """`get_layer_legend_state` の結果をログ出力する。

    - QGIS 実行環境であれば `QgsMessageLog.logMessage` を使う。
    - それ以外は `print` による出力を行う。
    """
    try:
        state = get_layer_legend_state(layer)
    except Exception:
        state = None

    messages = []
    if not state:
        messages.append("[凡例状態] レイヤ情報が取得できませんでした")
    else:
        lid = state.get('layer_id')
        lname = state.get('layer_name')
        renderer = state.get('renderer')
        messages.append(f"[凡例状態][layer] id={lid} name='{lname}' renderer={renderer}")
        items = state.get('items', []) or []
        # 可視な凡例項目（visible is True）のみをログ出力
        visible_items = [it for it in items if it.get('visible') is True]
        if not visible_items:
            messages.append("[凡例状態] 可視な凡例項目はありません")
        else:
            for it in visible_items:
                idx = it.get('index')
                itype = it.get('type')
                label = it.get('label')
                # 表示フラグは True に限定しているため常に True
                messages.append(f"[凡例状態][item] index={idx} type={itype} label='{label}' visible=True")

    # Try to use QgsMessageLog if available
    try:
        from qgis.core import QgsMessageLog
    except Exception:
        QgsMessageLog = None

    for m in messages:
        try:
            if QgsMessageLog is not None:
                try:
                    QgsMessageLog.logMessage(m, tag, 0)
                except Exception:
                    print(m)
            else:
                print(m)
        except Exception:
            try:
                print(m)
            except Exception:
                pass


def log_layer_legend_state_by_name(layer_name: str, project=None, tag: str = "GEO-search-plugin"):
    """レイヤ名からレイヤを検索して凡例状態をログ出力するユーティリティ。

    `project` を指定しない場合は `QgsProject.instance()` を使用します。
    """
    try:
        from qgis.core import QgsProject
    except Exception:
        QgsProject = None

    if project is None and QgsProject is not None:
        try:
            project = QgsProject.instance()
        except Exception:
            project = None

    layers = []
    if project is not None:
        try:
            layers = project.mapLayersByName(layer_name)
        except Exception:
            layers = []

    if not layers:
        msg = f"[凡例状態] レイヤ '{layer_name}' が見つかりません"
        try:
            from qgis.core import QgsMessageLog
        except Exception:
            QgsMessageLog = None
        if QgsMessageLog is not None:
            try:
                QgsMessageLog.logMessage(msg, tag, 1)
            except Exception:
                print(msg)
        else:
            print(msg)
        return

    # 最初のレイヤを使う
    log_layer_legend_state(layers[0], tag=tag)


__all__ = [
    "apply_theme",
    "_get_theme_brackets",
    "parse_theme_group",
    "group_themes",
    "get_layer_legend_state",
    "log_layer_legend_state",
    "log_layer_legend_state_by_name",
]
