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
import uuid
import re
from typing import Iterable, Dict, List, Optional, Tuple

# In-memory store for visible-layer snapshots (for later restore)
# Keyed by snapshot name -> list of per-layer dicts
_visible_layer_snapshots: Dict[str, List[Dict]] = {}

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
                # Include the temporary theme name in log output for clarity
                if summary:
                    log_func(f"[テーマログ　summary] 一時テーマをコレクションに保存しました:  '{tmp_name}' : {summary}", 0)
                else:
                    log_func(f"[テーマログ　else] 一時テーマをコレクションに保存しました '{tmp_name}' ", 0)
            except Exception:
                pass

    return prev_theme, saved


def collect_visible_layer_snapshot(root, log_layer_legend_state_func=None, tag: str = "GEO-search-plugin", snapshot_name: Optional[str] = None):
    """Collect visible layers and optionally save a snapshot.

    Formerly named `collect_visible_layer_messages`. This function collects
    information about visible layers and emits optional log messages. When
    `snapshot_name` is provided the structured snapshot is stored in
    `_visible_layer_snapshots` under that name. Returns the list of emitted
    message strings.
    """
    messages = []
    # Structure that will be saved when snapshot_name is provided
    snapshot: List[Dict] = []
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

                try:
                    style_name = _get_layer_style_name(layer)
                except Exception:
                    style_name = None
                messages.append(f"[テーマログ][visible_layer] order={order} id={lid} name='{lname}' style={style_name}")
                # Collect a structured record for optional snapshot storage
                try:
                    # Try to get legend state for storage (not only for logging)
                    legend_state = None
                    try:
                        legend_state = get_layer_legend_state(layer)
                    except Exception:
                        legend_state = None
                except Exception:
                    legend_state = None

                try:
                    style_name = _get_layer_style_name(layer)
                except Exception:
                    style_name = None
                snapshot.append({
                    "order": order,
                    "id": lid,
                    "name": lname,
                    "legend": legend_state,
                    "style": style_name,
                })
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

    # Save snapshot in-memory if requested (does not perform any restore)
    try:
        if snapshot_name:
            try:
                _visible_layer_snapshots[str(snapshot_name)] = snapshot
                # also emit a short confirmation message
                info = f"[テーマログ] visible-layer snapshot '{snapshot_name}' をメモリに保存しました (layers={len(snapshot)})"
                try:
                    if QgsMessageLog is not None:
                        QgsMessageLog.logMessage(info, tag, 0)
                    else:
                        print(info)
                except Exception:
                    print(info)
            except Exception:
                # ignore snapshot save failures
                pass
    except Exception:
        pass

    return messages

# Backwards-compatible alias: keep old name working
collect_visible_layer_messages = collect_visible_layer_snapshot

def restore_temp_theme(theme_collection, tmp_name: str, root=None, model=None, log_func=None, short_func=None):
    """Apply (restore) a temporary theme by name without removing it.

    Returns True if the apply succeeded, False otherwise. Logging is
    performed via `log_func` when provided.
    """
    if not tmp_name:
        return False

    # Try to resolve a nicer display name for logging (similar to remove_temp_theme)
    display_name = tmp_name
    try:
        theme_obj = None
        if theme_collection is not None:
            for getter in ("mapTheme", "theme", "getMapTheme", "getTheme", "mapThemeByName", "themeByName"):
                if hasattr(theme_collection, getter):
                    try:
                        theme_obj = getattr(theme_collection, getter)(tmp_name)
                        break
                    except Exception:
                        continue
        if theme_obj is not None:
            try:
                name_val = None
                if hasattr(theme_obj, "name"):
                    try:
                        name_val = theme_obj.name() if callable(getattr(theme_obj, "name", None)) else getattr(theme_obj, "name", None)
                    except Exception:
                        name_val = None
                if not name_val and hasattr(theme_obj, "title"):
                    try:
                        name_val = theme_obj.title() if callable(getattr(theme_obj, "title", None)) else getattr(theme_obj, "title", None)
                    except Exception:
                        name_val = None
                if name_val:
                    display_name = str(name_val)
            except Exception:
                pass
    except Exception:
        display_name = tmp_name

    try:
        try:
            try:
                theme_collection.applyTheme(tmp_name, root, model)
            except Exception:
                theme_collection.applyTheme(tmp_name)
            if log_func is not None:
                try:
                    log_func(f"[テーマログ] 一時テーマを適用しました: '{display_name}'", 0)
                except Exception:
                    pass
            return True
        except Exception as e:
            try:
                if log_func is not None:
                    log_func(f"[テーマログ] 一時テーマ '{display_name}' の適用に失敗しました: {short_func(e,200) if short_func is not None else str(e)}", 2)
            except Exception:
                pass
            return False
    except Exception:
        try:
            if log_func is not None:
                log_func(f"[テーマログ] restore_temp_theme('{display_name}') の外側で例外が発生しました", 2)
        except Exception:
            pass
        return False


def remove_temp_theme(theme_collection, tmp_name: str, log_func=None):
    """Remove a temporary theme by name from the collection without applying it.

    Returns True if removal succeeded, False otherwise.
    """
    if not tmp_name:
        return False
    # Try to resolve a nicer display name for logging
    display_name = tmp_name
    try:
        theme_obj = None
        if theme_collection is not None:
            for getter in ("mapTheme", "theme", "getMapTheme", "getTheme", "mapThemeByName", "themeByName"):
                if hasattr(theme_collection, getter):
                    try:
                        theme_obj = getattr(theme_collection, getter)(tmp_name)
                        break
                    except Exception:
                        continue
        if theme_obj is not None:
            try:
                name_val = None
                if hasattr(theme_obj, "name"):
                    try:
                        name_val = theme_obj.name() if callable(getattr(theme_obj, "name", None)) else getattr(theme_obj, "name", None)
                    except Exception:
                        name_val = None
                if not name_val and hasattr(theme_obj, "title"):
                    try:
                        name_val = theme_obj.title() if callable(getattr(theme_obj, "title", None)) else getattr(theme_obj, "title", None)
                    except Exception:
                        name_val = None
                if name_val:
                    display_name = str(name_val)
            except Exception:
                pass
    except Exception:
        display_name = tmp_name
    try:
        for rem_name in ("removeMapTheme", "remove", "deleteTheme", "removeTheme"):
            if hasattr(theme_collection, rem_name):
                try:
                    getattr(theme_collection, rem_name)(tmp_name)
                    if log_func is not None:
                        try:
                            log_func(f"[テーマログ] 一時テーマを削除しました: '{display_name}'", 0)
                        except Exception:
                            pass
                    return True
                except Exception:
                    continue
    except Exception:
        try:
            if log_func is not None:
                try:
                    log_func(f"[テーマログ] 一時テーマ '{display_name}' の削除で例外が発生しました", 2)
                except Exception:
                    pass
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
        tmp_prev = f"__geo_search_tmp__{uuid.uuid4().hex}"
        tmp_sel = f"__geo_search_tmp__{uuid.uuid4().hex}"
        prev_saved = False
        sel_saved = False
        try:
            # 現在の状態を保存（可能ならば） - 関数化して処理を委譲
            prev_theme, saved = save_current_state_as_temp_theme(
                theme_collection, tmp_prev, root, model, log_func=_log, summarize_func=_summarize_theme
            )
            if saved:
                prev_saved = True

            # 選択テーマを適用（root/model バージョンを優先）
            try:
                try:
                    theme_collection.applyTheme(theme_name, root, model)
                except Exception:
                    theme_collection.applyTheme(theme_name)

                # ログ出力: 選択テーマを適用したことをテーマ名付きで記録する
                try:
                    display_name = theme_name
                    try:
                        theme_obj = None
                        if theme_collection is not None:
                            for getter in ("mapTheme", "theme", "getMapTheme", "getTheme", "mapThemeByName", "themeByName"):
                                if hasattr(theme_collection, getter):
                                    try:
                                        theme_obj = getattr(theme_collection, getter)(theme_name)
                                        break
                                    except Exception:
                                        continue
                        if theme_obj is not None:
                            try:
                                name_val = None
                                if hasattr(theme_obj, "name"):
                                    try:
                                        name_val = theme_obj.name() if callable(getattr(theme_obj, "name", None)) else getattr(theme_obj, "name", None)
                                    except Exception:
                                        name_val = None
                                if not name_val and hasattr(theme_obj, "title"):
                                    try:
                                        name_val = theme_obj.title() if callable(getattr(theme_obj, "title", None)) else getattr(theme_obj, "title", None)
                                    except Exception:
                                        name_val = None
                                if name_val:
                                    display_name = str(name_val)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        _log(f"[テーマログ] 選択テーマを適用しました: '{display_name}'", 0)
                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception as e:
                if QgsMessageLog:
                    try:
                        QgsMessageLog.logMessage(f"テーマ適用エラー(ログ用): {e}", "GEO-search-plugin", 2)
                    except Exception:
                        pass
                return
            # 選択テーマを適用した後、その状態を一時テーマとして保存する
            try:
                try:
                    _, sel_saved = save_current_state_as_temp_theme(
                        theme_collection, tmp_sel, root, model, log_func=_log, summarize_func=_summarize_theme
                    )
                except Exception:
                    sel_saved = False
            except Exception:
                sel_saved = False
            
            # 凡例ノード（レイヤパネルの表示チェック）のみで判定
            # レイヤパネルで可視になっているレイヤ一覧をスナップショットとして保存
            # collect_visible_layer_snapshot は内部でメッセージ出力とスナップショット保存を行う
            collect_visible_layer_snapshot(root, log_layer_legend_state, snapshot_name=tmp_sel)
 
 
 
        finally:
            # 元の状態を復元: コレクションに保存した一時テーマ名で適用する
            try:
                if prev_saved:
                    restore_temp_theme(
                        theme_collection, tmp_prev, root, model, log_func=_log, short_func=_short
                    )
            except Exception:
                try:
                    _log("[テーマログ] prev_theme 復元の最外部で例外が発生しました", 2)
                except Exception:
                    pass

            # 元の状態として保存した一時テーマは適用後に削除する
            try:
                if prev_saved:
                    try:
                        remove_temp_theme(theme_collection, tmp_prev, log_func=_log)
                    except Exception:
                        try:
                            _log("[テーマログ] prev temp の削除で例外が発生しました", 2)
                        except Exception:
                            pass
            except Exception:
                try:
                    _log("[テーマログ] prev temp 削除処理で外側の例外が発生しました", 2)
                except Exception:
                    pass

            # 選択テーマのスナップショットを現在の表示に反映（追加可視）
            try:
                if sel_saved:
                    try:
                        # Use QgsProject.instance() if available
                        try:
                            project_for_reload = QgsProject.instance() if QgsProject is not None else None
                        except Exception:
                            project_for_reload = None
                        collect_visible_layer_reload(tmp_sel, project=project_for_reload, root=root, tag="GEO-search-plugin", log_func=_log)
                    except Exception:
                        try:
                            _log("[テーマログ] sel snapshot の反映で例外が発生しました", 2)
                        except Exception:
                            pass
            except Exception:
                try:
                    _log("[テーマログ] sel snapshot 反映処理で外側の例外が発生しました", 2)
                except Exception:
                    pass

            # 選択テーマとして保存した一時テーマは適用しないで削除する
            try:
                if sel_saved:
                    remove_temp_theme(theme_collection, tmp_sel, log_func=_log)
            except Exception:
                try:
                    _log("[テーマログ] sel temp の削除で例外が発生しました", 2)
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


def _get_layer_style_name(layer) -> Optional[str]:
    """Return a layer's style name/ID when available.

    Tries several common APIs in a tolerant way and returns the first
    non-empty string found. Returns None when no style name can be
    determined. This is intentionally conservative: we only save the
    style "name/ID" (not full renderer XML).
    """
    if layer is None:
        return None
    # try style manager on the layer (QgsMapLayerStyleManager)
    try:
        sm = getattr(layer, 'styleManager', None)
        mgr = None
        if callable(sm):
            try:
                mgr = sm()
            except Exception:
                mgr = sm
        else:
            mgr = sm

        if mgr is not None:
            for name in ('currentStyle', 'currentStyleName', 'defaultStyleName', 'currentStyleId'):
                try:
                    fn = getattr(mgr, name, None)
                    if callable(fn):
                        try:
                            val = fn()
                        except Exception:
                            val = None
                    else:
                        val = fn
                    if val:
                        return str(val)
                except Exception:
                    continue
    except Exception:
        pass

    # try layer-level attributes/methods
    for attr in ('styleName', 'style', 'currentStyle', 'defaultStyle', 'defaultStyleName'):
        try:
            v = getattr(layer, attr, None)
            if callable(v):
                try:
                    v = v()
                except Exception:
                    v = None
            if v:
                return str(v)
        except Exception:
            continue

    # try customProperty lookup (some plugins/tools store style info there)
    try:
        cp = getattr(layer, 'customProperty', None)
        if callable(cp):
            try:
                for key in ('style', 'styleName', 'currentStyle'):
                    try:
                        v = cp(key)
                    except Exception:
                        v = None
                    if v:
                        return str(v)
            except Exception:
                pass
    except Exception:
        pass

    return None


def _apply_layer_style_by_name(layer, style_name: str, log_func=None) -> bool:
    """Try to apply a style (by name or id) to a layer in a best-effort way.

    Returns True if any attempted API call succeeded, False otherwise.
    This function is intentionally defensive to support multiple QGIS versions
    and layer types.
    """
    if layer is None or not style_name:
        return False

    # Try style manager on the layer first
    try:
        sm = getattr(layer, 'styleManager', None)
        mgr = None
        if callable(sm):
            try:
                mgr = sm()
            except Exception:
                mgr = sm
        else:
            mgr = sm

        if mgr is not None:
            for setter in (
                'setCurrentStyle',
                'setCurrentStyleName',
                'setStyle',
                'setStyleByName',
                'applyStyle',
                'applyNamedStyle',
            ):
                try:
                    fn = getattr(mgr, setter, None)
                    if callable(fn):
                        fn(style_name)
                        return True
                except Exception:
                    continue
    except Exception:
        pass

    # Try layer-level setters
    for setter in ('setCurrentStyle', 'setStyle', 'setStyleName', 'applyStyle', 'setDefaultStyle'):
        try:
            fn = getattr(layer, setter, None)
            if callable(fn):
                fn(style_name)
                return True
        except Exception:
            continue

    # If style_name looks like a file path, try loadNamedStyle
    try:
        import os

        if os.path.sep in style_name or style_name.lower().endswith(('.qml', '.sld', '.xml')):
            load_fn = getattr(layer, 'loadNamedStyle', None)
            if callable(load_fn):
                try:
                    load_fn(style_name)
                    return True
                except Exception:
                    pass
    except Exception:
        pass

    return False


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


def get_visible_layer_snapshot(name: str) -> Optional[List[Dict]]:
    """Return a previously saved visible-layer snapshot by name.

    Returns the list of per-layer dicts or None if not found.
    """
    try:
        return _visible_layer_snapshots.get(name)
    except Exception:
        return None


def list_visible_layer_snapshots() -> List[str]:
    """Return the list of snapshot names currently stored in memory."""
    try:
        return list(_visible_layer_snapshots.keys())
    except Exception:
        return []


def apply_legend_visibility(layer, legend_state: Optional[Dict], log_func=None, overwrite_all: bool = False):
    """Apply visible-only legend flags from `legend_state` to `layer`.

    Only sets items to visible (enables); does not disable any existing items.
    This is best-effort across renderer types and QGIS API versions.
    """
    if not legend_state or layer is None:
        return

    try:
        renderer = layer.renderer()
    except Exception:
        renderer = None

    if renderer is None:
        return

    items = legend_state.get('items') or []
    if not items:
        return

    def _set_obj_state(obj, enable: bool):
        try:
            if hasattr(obj, 'setActive'):
                try:
                    obj.setActive(bool(enable))
                    return True
                except Exception:
                    pass
            if hasattr(obj, 'setEnabled'):
                try:
                    obj.setEnabled(bool(enable))
                    return True
                except Exception:
                    pass
            if hasattr(obj, 'setVisible'):
                try:
                    obj.setVisible(bool(enable))
                    return True
                except Exception:
                    pass
            if hasattr(obj, 'setRenderState'):
                try:
                    obj.setRenderState(bool(enable))
                    return True
                except Exception:
                    pass
        except Exception:
            pass
        return False

    # Try categorized/graduated by matching labels
    try:
        cats = getattr(renderer, 'categories', None)
        if callable(cats):
            try:
                categories = renderer.categories()
            except Exception:
                categories = []
            for it in items:
                label = it.get('label')
                if label is None:
                    continue
                desired = True if it.get('visible') is True else False
                # If not overwrite_all, we only enable True items
                if not overwrite_all and not desired:
                    continue
                for cat in categories:
                    try:
                        lab = cat.label() if callable(getattr(cat, 'label', None)) else getattr(cat, 'label', None)
                    except Exception:
                        lab = None
                    if lab == label:
                        _set_obj_state(cat, desired)
            # done
    except Exception:
        pass

    # Graduated ranges
    try:
        ranges_fn = getattr(renderer, 'ranges', None)
        if callable(ranges_fn):
            try:
                ranges = renderer.ranges()
            except Exception:
                ranges = []
            for it in items:
                label = it.get('label')
                if label is None:
                    continue
                desired = True if it.get('visible') is True else False
                if not overwrite_all and not desired:
                    continue
                for r in ranges:
                    try:
                        lab = r.label() if callable(getattr(r, 'label', None)) else getattr(r, 'label', None)
                    except Exception:
                        lab = None
                    if lab == label:
                        _set_obj_state(r, desired)
    except Exception:
        pass

    # Rule-based: traverse rules and match labels
    try:
        # rootRule may exist
        root_rule = None
        try:
            root_rule = renderer.rootRule()
        except Exception:
            root_rule = None

        def _collect_rules(rule, out=None):
            if out is None:
                out = []
            try:
                children = rule.children()
            except Exception:
                children = []
            for ch in children:
                out.append(ch)
                _collect_rules(ch, out)
            return out

        all_rules = []
        if root_rule is not None:
            try:
                all_rules = _collect_rules(root_rule)
            except Exception:
                all_rules = []

        for it in items:
            label = it.get('label')
            if label is None:
                continue
            desired = True if it.get('visible') is True else False
            if not overwrite_all and not desired:
                continue
            for r in all_rules:
                try:
                    lab = r.label() if callable(getattr(r, 'label', None)) else getattr(r, 'label', None)
                except Exception:
                    lab = None
                if lab == label:
                    _set_obj_state(r, desired)
    except Exception:
        pass

    # Single-symbol: nothing to enable besides layer visibility
    return


def collect_visible_layer_reload(snapshot_name: str, project=None, root=None, tag: str = "GEO-search-plugin", log_func=None) -> bool:
    """Restore visible-layer state from an in-memory snapshot by making those
    layers visible in the current layer tree.

    This function performs an additive operation: it makes the snapshot's
    layers visible in the current view but does not hide other layers.

    Returns True on (attempted) success, False if the snapshot was missing.
    """
    try:
        from qgis.core import QgsMessageLog
    except Exception:
        QgsMessageLog = None

    def _logmsg(m: str, level: int = 0):
        try:
            if log_func is not None:
                try:
                    log_func(m, level)
                    return
                except Exception:
                    pass
            if QgsMessageLog is not None:
                try:
                    QgsMessageLog.logMessage(m, tag, level)
                    return
                except Exception:
                    pass
            print(m)
        except Exception:
            try:
                print(m)
            except Exception:
                pass

    snap = get_visible_layer_snapshot(snapshot_name)
    if not snap:
        _logmsg(f"[テーマログ] snapshot '{snapshot_name}' が見つかりません", 1)
        return False

    # Try to obtain project instance if not provided
    try:
        from qgis.core import QgsProject
    except Exception:
        QgsProject = None

    if project is None and QgsProject is not None:
        try:
            project = QgsProject.instance()
        except Exception:
            project = None

    applied = 0
    for rec in snap:
        try:
            lid = rec.get("id")
            lname = rec.get("name")
            layer = None
            # Prefer lookup by id when available
            if project is not None and lid:
                try:
                    # QgsProject.mapLayer or mapLayersByName depending on API
                    if hasattr(project, "mapLayer"):
                        layer = project.mapLayer(lid)
                    else:
                        # fallback: iterate mapLayers
                        try:
                            layers = project.mapLayers().values()
                        except Exception:
                            layers = []
                        for L in layers:
                            try:
                                if (callable(getattr(L, "id", None)) and L.id() == lid) or getattr(L, "id", None) == lid:
                                    layer = L
                                    break
                            except Exception:
                                continue
                except Exception:
                    layer = None
            # fallback to name-based search
            if layer is None and project is not None and lname:
                try:
                    candidates = project.mapLayersByName(lname)
                    if candidates:
                        layer = candidates[0]
                except Exception:
                    layer = None

            if layer is None:
                _logmsg(f"[テーマログ] snapshot のレイヤが見つかりません id={lid} name='{lname}'", 1)
                continue

            # Try to find layer tree node and set visibility
            node_found = False
            if root is not None:
                try:
                    # Prefer API that finds node by layer id
                    node = None
                    try:
                        if hasattr(root, 'findLayer'):
                            node = root.findLayer(lid)
                    except Exception:
                        node = None
                    # If findLayer not available or failed, search nodes
                    if node is None:
                        try:
                            nodes = root.findLayers()
                        except Exception:
                            nodes = []
                        for n in nodes:
                            try:
                                L = n.layer()
                                lid2 = None
                                try:
                                    lid2 = L.id() if callable(getattr(L, 'id', None)) else getattr(L, 'id', None)
                                except Exception:
                                    lid2 = None
                                if lid2 == lid:
                                    node = n
                                    break
                            except Exception:
                                continue

                    if node is not None:
                        node_found = True
                        # Detect original node visibility before we change it
                        orig_node_visible = None
                        try:
                            vis_getters = ('isVisible', 'isItemVisibilityChecked', 'isChecked', 'visible', 'checked')
                            for g in vis_getters:
                                try:
                                    getter = getattr(node, g, None)
                                    if callable(getter):
                                        try:
                                            val = getter()
                                            orig_node_visible = bool(val)
                                            break
                                        except Exception:
                                            continue
                                    else:
                                        val = getattr(node, g, None)
                                        if isinstance(val, bool):
                                            orig_node_visible = val
                                            break
                                except Exception:
                                    continue
                        except Exception:
                            orig_node_visible = None
                        # First: ensure parent groups are visible so the layer can actually show
                        try:
                            parent = getattr(node, 'parent', None)
                            # parent may be a callable or attribute depending on API
                            try:
                                parent_node = parent() if callable(parent) else parent
                            except Exception:
                                parent_node = None
                            # Walk upward and set visibility on groups
                            while parent_node is not None:
                                try:
                                    # set visibility on parent node using multiple possible APIs
                                    if hasattr(parent_node, 'setItemVisibilityChecked'):
                                        parent_node.setItemVisibilityChecked(True)
                                    elif hasattr(parent_node, 'setVisible'):
                                        parent_node.setVisible(True)
                                    elif hasattr(parent_node, 'setIsVisible'):
                                        parent_node.setIsVisible(True)
                                    else:
                                        try:
                                            setattr(parent_node, 'visible', True)
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                                # move up
                                try:
                                    up = getattr(parent_node, 'parent', None)
                                    parent_node = up() if callable(up) else up
                                except Exception:
                                    break

                        except Exception:
                            pass

                        # Try several visibility setters on the layer node itself
                        try:
                            if hasattr(node, 'setItemVisibilityChecked'):
                                node.setItemVisibilityChecked(True)
                            elif hasattr(node, 'setVisible'):
                                node.setVisible(True)
                            elif hasattr(node, 'setIsVisible'):
                                node.setIsVisible(True)
                            else:
                                # Last resort: try attribute
                                try:
                                    setattr(node, 'visible', True)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        # Apply legend visibility. If the node was originally non-visible
                        # then overwrite items state (enable/disable) to reproduce legend;
                        # otherwise only enable visible items.
                        try:
                            try:
                                legend_state = rec.get('legend')
                            except Exception:
                                legend_state = None
                            if legend_state:
                                try:
                                    overwrite = not bool(orig_node_visible)
                                    # If the layer was originally non-visible (overwrite==True),
                                    # try to apply the saved style before applying legend on/off
                                    try:
                                        if overwrite:
                                            style_name = rec.get('style')
                                            if style_name:
                                                try:
                                                    applied_style = _apply_layer_style_by_name(layer, style_name, log_func=_logmsg)
                                                    if applied_style:
                                                        _logmsg(f"[テーマログ] レイヤ '{lname}' にスタイル '{style_name}' を適用しました", 0)
                                                    else:
                                                        _logmsg(f"[テーマログ] レイヤ '{lname}' のスタイル '{style_name}' の適用に失敗しました", 1)
                                                except Exception:
                                                    pass
                                    except Exception:
                                        pass
                                    apply_legend_visibility(layer, legend_state, log_func=_logmsg, overwrite_all=overwrite)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    node_found = False

            # If we couldn't operate on the node, try to make layer visible via project layer tree (some APIs)
            if not node_found:
                try:
                    # Some environments allow setting layer visibility via layer.setItemVisibility or similar
                    # Try to set an attribute 'visible' on the layer object as a last resort (non-standard)
                    if hasattr(layer, 'setCustomProperty'):
                        try:
                            # no-op placeholder; keep compatibility
                            pass
                        except Exception:
                            pass
                except Exception:
                    pass

            applied += 1
        except Exception:
            continue

    _logmsg(f"[テーマログ] snapshot '{snapshot_name}' の可視レイヤを現在の表示に反映しました (attempted={applied})", 0)
    return True


__all__ = [
    "apply_theme",
    "_get_theme_brackets",
    "parse_theme_group",
    "group_themes",
    "get_layer_legend_state",
    "log_layer_legend_state",
    "log_layer_legend_state_by_name",
    "get_visible_layer_snapshot",
    "list_visible_layer_snapshots",
    "collect_visible_layer_reload",
]
