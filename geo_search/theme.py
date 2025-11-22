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




def save_current_state_as_temp_theme(
    theme_collection,
    tmp_name: str,
    root=None,
    model=None,
    log_func=None,
    summarize_func=None,
):
    """Create a theme object from the current project state and save it
    into `theme_collection` under `tmp_name`.

    Returns a tuple ``(prev_theme, saved)`` where ``saved`` is True when the
    temporary theme was successfully inserted/updated into the collection.
    ``log_func`` (callable) and ``summarize_func`` (callable) are optional
    hooks used for logging.
    """
    prev_theme = None
    try:
        # テーマオブジェクトを作成（API の違いに対応）
        if hasattr(theme_collection, "createThemeFromCurrentState"):
            try:
                prev_theme = theme_collection.createThemeFromCurrentState(root, model)
            except Exception:
                try:
                    prev_theme = theme_collection.createThemeFromCurrentState(root)
                except Exception:
                    prev_theme = None
        else:
            # クラスメソッド経由の生成を試す
            try:
                from qgis.core import QgsMapThemeCollection

                try:
                    prev_theme = QgsMapThemeCollection.createThemeFromCurrentState(root, model)
                except Exception:
                    prev_theme = QgsMapThemeCollection.createThemeFromCurrentState(root)
            except Exception:
                prev_theme = None
    except Exception:
        prev_theme = None

    saved = False
    if prev_theme is not None:
        try:
            # 既存の API 名を試す
            if hasattr(theme_collection, "hasMapTheme") and hasattr(theme_collection, "update"):
                try:
                    if theme_collection.hasMapTheme(tmp_name):
                        theme_collection.update(tmp_name, prev_theme)
                        saved = True
                    else:
                        theme_collection.insert(tmp_name, prev_theme)
                        saved = True
                except Exception:
                    saved = False
            else:
                for add_name in ("insert", "addMapTheme", "addTheme", "add"):
                    if hasattr(theme_collection, add_name):
                        try:
                            getattr(theme_collection, add_name)(tmp_name, prev_theme)
                            saved = True
                            break
                        except Exception:
                            continue
        except Exception:
            saved = False

        if saved and log_func is not None:
            try:
                summary = summarize_func(prev_theme) if summarize_func else None
            except Exception:
                summary = "<unable to summarize>"
            try:
                if summary:
                    log_func(f"[テーマログ] prev_theme をコレクションに保存しました: {summary}", 0)
                else:
                    log_func("[テーマログ] prev_theme をコレクションに保存しました", 0)
            except Exception:
                pass

    return prev_theme, saved


def collect_visible_layer_messages(root, log_layer_legend_state_func=None, tag: str = "GEO-search-plugin"):
    """Collect messages for layers that are visible in the layer tree and emit
    them to the QGIS message log (or stdout when unavailable).

    If `log_layer_legend_state_func` is supplied it will be called for each
    visible layer to emit additional legend-state logs; failures are ignored.

    Returns the list of message strings that were emitted.
    """
    messages = []
    try:
        try:
            nodes = root.findLayers()
        except Exception:
            nodes = []

        order = 0
        for n in nodes:
            try:
                is_vis = False
                try:
                    is_vis = bool(n.isVisible())
                except Exception:
                    is_vis = False
                if not is_vis:
                    order += 1
                    continue

                try:
                    layer = n.layer()
                except Exception:
                    layer = None
                if layer is None:
                    order += 1
                    continue

                try:
                    lid = layer.id() if callable(getattr(layer, "id", None)) else getattr(layer, "id", None)
                except Exception:
                    try:
                        lid = layer.id()
                    except Exception:
                        lid = None
                try:
                    lname = layer.name()
                except Exception:
                    try:
                        lname = getattr(layer, "name", "")
                    except Exception:
                        lname = ""

                messages.append(f"[テーマログ][visible_layer] order={order} id={lid} name='{lname}'")
                # Optionally emit legend-state logs for each layer
                if log_layer_legend_state_func is not None:
                    try:
                        log_layer_legend_state_func(layer, tag=tag)
                    except Exception:
                        pass

                order += 1
            except Exception:
                continue
    except Exception:
        messages = ["[テーマログ] レイヤ一覧の取得に失敗しました"]

    # Emit messages using QgsMessageLog when available, otherwise print
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

    return messages


def restore_and_remove_temp_theme(
    theme_collection,
    tmp_name: str,
    root=None,
    model=None,
    log_func=None,
    short_func=None,
):
    """Apply a temporary theme by name to restore previous state and then
    remove the temporary theme from the collection.

    Returns True if removal succeeded (or at least an attempt was made),
    False otherwise. Logging is performed via `log_func` when provided.
    """
    try:
        if not tmp_name:
            return False

        # apply the temp theme (prefer applyTheme with root/model)
        try:
            try:
                theme_collection.applyTheme(tmp_name, root, model)
            except Exception:
                theme_collection.applyTheme(tmp_name)
            if log_func is not None:
                try:
                    log_func("[テーマログ] 一時テーマを適用しました", 0)
                except Exception:
                    pass
        except Exception as e:
            try:
                if log_func is not None:
                    log_func(f"[テーマログ] 一時テーマの適用に失敗しました: {short_func(e,200) if short_func is not None else str(e)}", 2)
            except Exception:
                pass
            # continue to attempt deletion even if apply failed

        # attempt to remove the temporary theme from the collection
        try:
            for rem_name in ("removeMapTheme", "remove", "deleteTheme", "removeTheme"):
                if hasattr(theme_collection, rem_name):
                    try:
                        getattr(theme_collection, rem_name)(tmp_name)
                        if log_func is not None:
                            try:
                                log_func("[テーマログ] 一時テーマを削除しました", 0)
                            except Exception:
                                pass
                        return True
                    except Exception:
                        continue
        except Exception:
            try:
                if log_func is not None:
                    log_func("[テーマログ] 一時テーマの削除で例外が発生しました", 2)
            except Exception:
                pass

        return False
    except Exception:
        try:
            if log_func is not None:
                log_func("[テーマログ] prev_theme 復元の最外部で例外が発生しました", 2)
        except Exception:
            pass
        return False


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

    # ログ出力用ユーティリティ（QGIS の QgsMessageLog を優先、なければ print）
    def _log(msg: str, level: int = 0) -> None:
        try:
            if QgsMessageLog is not None:
                try:
                    QgsMessageLog.logMessage(msg, "GEO-search-plugin", level)
                    return
                except Exception:
                    pass
            print(msg)
        except Exception:
            try:
                print(msg)
            except Exception:
                pass

    def _short(s: object, maxlen: int = 200) -> str:
        try:
            text = str(s)
        except Exception:
            try:
                text = repr(s)
            except Exception:
                return "<unrepresentable>"
        if len(text) <= maxlen:
            return text
        return text[: maxlen - 3] + "..."

    def _summarize_theme(t) -> str:
        parts = []
        try:
            parts.append(f"type={type(t).__name__}")
        except Exception:
            parts.append("type=<unknown>")
        # try to get a name
        try:
            name = None
            if hasattr(t, "name"):
                try:
                    name = t.name() if callable(getattr(t, "name", None)) else getattr(t, "name", None)
                except Exception:
                    name = None
            if not name and hasattr(t, "title"):
                try:
                    name = t.title() if callable(getattr(t, "title", None)) else getattr(t, "title", None)
                except Exception:
                    name = None
            if name:
                parts.append(f"name={_short(name,80)}")
        except Exception:
            pass
        # try to get layer count
        try:
            layer_count = None
            for attr in ("layerIds", "layers", "layer_count", "layerCount", "layersCount"):
                try:
                    val = getattr(t, attr, None)
                    if val is None:
                        continue
                    maybe = val() if callable(val) else val
                    if isinstance(maybe, (list, tuple, set)):
                        layer_count = len(maybe)
                        break
                    if isinstance(maybe, int):
                        layer_count = maybe
                        break
                except Exception:
                    continue
            if layer_count is not None:
                parts.append(f"layers={layer_count}")
        except Exception:
            pass
        # short repr
        try:
            parts.append(f"repr={_short(getattr(t, 'toString', getattr(t, 'toXml', getattr(t, '__repr__', None))) or t, 120)}")
        except Exception:
            try:
                parts.append(_short(repr(t), 120))
            except Exception:
                pass
        return ", ".join(parts)

    if not theme_name:
        return

    if additive:
        # 追加表示モード（試験実装）:
        # - 選択テーマを一時的に適用して、表示されるレイヤと
        #   かつシンボルのアルファが0でないルールのみをログ出力します。
        # - それ以外の追加表示（和集合）ロジックはまだ実装しません。
        tmp_name = "__geo_search_tmp__geo_search__"
        prev_saved = False
        try:
            # 現在の状態を保存（可能ならば） - 関数化して処理を委譲
            prev_theme, saved = save_current_state_as_temp_theme(
                theme_collection, tmp_name, root, model, log_func=_log, summarize_func=_summarize_theme
            )
            if saved:
                prev_saved = True

            # 選択テーマを適用（root/model バージョンを優先）
            try:
                try:
                    theme_collection.applyTheme(theme_name, root, model)
                except Exception:
                    theme_collection.applyTheme(theme_name)
            except Exception as e:
                if QgsMessageLog:
                    try:
                        QgsMessageLog.logMessage(f"テーマ適用エラー(ログ用): {e}", "GEO-search-plugin", 2)
                    except Exception:
                        pass
                return
            
            # 凡例ノード（レイヤパネルの表示チェック）のみで判定
            # 選択テーマ適用後、レイヤパネルで可視になっているレイヤ一覧をログ出力
            # collect_visible_layer_messages は内部でメッセージ出力を行う
            collect_visible_layer_messages(root, log_layer_legend_state)
 
        finally:
            # 元の状態を復元: コレクションに保存した一時テーマ名で適用して削除する
            try:
                if prev_saved:
                    restore_and_remove_temp_theme(
                        theme_collection, tmp_name, root, model, log_func=_log, short_func=_short
                    )
            except Exception:
                try:
                    _log("[テーマログ] prev_theme 復元の最外部で例外が発生しました", 2)
                except Exception:
                    pass
        # 追加表示の実装はまだ行わない
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
