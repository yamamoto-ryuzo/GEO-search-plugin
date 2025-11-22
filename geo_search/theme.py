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
        # 追加表示モード（試験実装）:
        # - 選択テーマを一時的に適用して、表示されるレイヤと
        #   かつシンボルのアルファが0でないルールのみをログ出力します。
        # - それ以外の追加表示（和集合）ロジックはまだ実装しません。
        tmp_name = "__geo_search_tmp__geo_search__"
        prev_saved = False
        try:
            # 現在の状態を保存（可能ならば）
            prev_theme = None
            try:
                if hasattr(theme_collection, "createThemeFromCurrentState"):
                    try:
                        prev_theme = theme_collection.createThemeFromCurrentState(root, model)
                    except Exception:
                        try:
                            prev_theme = theme_collection.createThemeFromCurrentState(root)
                        except Exception:
                            prev_theme = None
            except Exception:
                prev_theme = None

            if prev_theme is not None:
                # いくつかの API 名を試して一時テーマを登録
                for add_name in ("insert", "addMapTheme", "addTheme", "add"):
                    if hasattr(theme_collection, add_name):
                        try:
                            getattr(theme_collection, add_name)(tmp_name, prev_theme)
                            prev_saved = True
                            break
                        except Exception:
                            continue

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

            # テーマ適用後に表示されているレイヤと、ルールごとの
            # フィルタ: ルールがスタイルとして有効（enabled）かを判定し、
            # 有効なルールのみログ対象とします。シンボルの alpha 情報は
            # 参考として収集します（追加の除外条件として維持）。
            messages = []
            # ルールがスタイルとして有効かを判定するユーティリティ
            def _is_rule_enabled(rule):
                try:
                    for name in ("isEnabled", "enabled", "isActive", "active", "isVisible"):
                        if hasattr(rule, name):
                            try:
                                val = getattr(rule, name)
                                v = val() if callable(val) else val
                                if v is False:
                                    return False
                                if v is True:
                                    return True
                            except Exception:
                                continue
                    return True
                except Exception:
                    return True
            try:
                try:
                    nodes = root.findLayers()
                except Exception:
                    nodes = []

                order = 0
                for n in nodes:
                    try:
                        node_visible = False
                        try:
                            node_visible = bool(n.isVisible())
                        except Exception:
                            node_visible = False
                        if not node_visible:
                            continue

                        try:
                            layer = n.layer()
                        except Exception:
                            layer = None
                        if layer is None:
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

                        # ルールベースレンダラーのルールごとにシンボル層のアルファを調べる
                        try:
                            rend = None
                            try:
                                rend = layer.renderer() if callable(getattr(layer, "renderer", None)) else getattr(layer, "renderer", None)
                            except Exception:
                                try:
                                    rend = layer.renderer()
                                except Exception:
                                    rend = None

                            rules = []
                            if rend is not None:
                                root_rule = None
                                try:
                                    root_rule = getattr(rend, "rootRule", lambda: None)()
                                except Exception:
                                    root_rule = getattr(rend, "root", None)
                                if root_rule is not None:
                                    try:
                                        rules = getattr(root_rule, "children", lambda: getattr(root_rule, "rules", lambda: []) )()
                                    except Exception:
                                        try:
                                            rules = root_rule.rules()
                                        except Exception:
                                            rules = []
                                else:
                                    # categorized 等のフォールバック
                                    try:
                                        cats = getattr(rend, "categories", None)
                                        if callable(cats):
                                            rules = cats()
                                    except Exception:
                                        rules = []

                            # ルールが見つからない場合は renderer の要約を出す（ただしシンボルの alpha 判定は困難）
                            if not rules:
                                try:
                                    renderer_info = rend.dump() if hasattr(rend, "dump") else (rend.toJson() if hasattr(rend, "toJson") else repr(rend))
                                except Exception:
                                    renderer_info = repr(rend)
                                messages.append(f"[テーマログ] layer order={order} id={lid} name='{lname}' renderer_summary={renderer_info}")
                                order += 1
                                continue

                            # ルール毎に alpha を調べ、alpha が 0 のルールは除外してログ作成
                            for idx, r in enumerate(rules):
                                try:
                                    # ルールのフィルタや縮尺はログに載せる（縮尺判定は簡易）
                                    fexpr = None
                                    for a in ("filterExpression", "filter", "expression"):
                                        if hasattr(r, a):
                                            try:
                                                val = getattr(r, a)
                                                fexpr = val() if callable(val) else val
                                                break
                                            except Exception:
                                                fexpr = None

                                    min_scale = None
                                    max_scale = None
                                    for mn in ("minimumScale", "scaleMin", "minScale"):
                                        if hasattr(r, mn):
                                            try:
                                                min_scale = getattr(r, mn)()
                                                break
                                            except Exception:
                                                pass
                                    for mx in ("maximumScale", "scaleMax", "maxScale"):
                                        if hasattr(r, mx):
                                            try:
                                                max_scale = getattr(r, mx)()
                                                break
                                            except Exception:
                                                pass

                                    # シンボル取得（rule.symbol() / rule.symbols() を試す）
                                    sym = None
                                    try:
                                        if hasattr(r, "symbol"):
                                            try:
                                                sym = r.symbol()
                                            except Exception:
                                                try:
                                                    sym = getattr(r, "symbol")
                                                    sym = sym() if callable(sym) else sym
                                                except Exception:
                                                    sym = None
                                        if sym is None and hasattr(r, "symbols"):
                                            try:
                                                syms = r.symbols()
                                                sym = syms[0] if syms else None
                                            except Exception:
                                                sym = None
                                    except Exception:
                                        sym = None

                                    # まずルールがスタイルとして有効かを判定（無効ならログ除外）
                                    try:
                                        if not _is_rule_enabled(r):
                                            continue
                                    except Exception:
                                        pass

                                    # sym から各 symbol layer のアルファを集める
                                    alpha_vals = []
                                    if sym is not None:
                                        try:
                                            try:
                                                sls = sym.symbolLayers()
                                            except Exception:
                                                sls = [sym]
                                            for sl in sls:
                                                try:
                                                    col = getattr(sl, "color", None)
                                                    if col and callable(col):
                                                        qc = col()
                                                    else:
                                                        qc = col
                                                    if qc is not None:
                                                        try:
                                                            a_int = qc.alpha()  # 0-255
                                                            a_f = qc.alphaF()   # 0.0-1.0
                                                            alpha_vals.append(("int", a_int, "float", a_f))
                                                        except Exception:
                                                            alpha_vals.append(("repr", repr(qc)))
                                                    else:
                                                        alpha_vals.append(("no_color", repr(sl)))
                                                except Exception:
                                                    alpha_vals.append(("err", repr(sl)))
                                        except Exception:
                                            alpha_vals = []
                                    else:
                                        alpha_vals = []

                                    # 判定: alpha_vals に整数値が含まれるなら全てが 0 か判定
                                    all_transparent = False
                                    try:
                                        int_alphas = [a for t, a, _, _ in alpha_vals if t == "int"] if any(isinstance(x, tuple) and x and x[0] == "int" for x in alpha_vals) else []
                                    except Exception:
                                        int_alphas = []
                                    try:
                                        if int_alphas:
                                            all_transparent = all(a == 0 for a in int_alphas)
                                        else:
                                            all_transparent = False
                                    except Exception:
                                        all_transparent = False

                                    # 全透明ならログ出力から除外（スキップ）
                                    if all_transparent:
                                        continue

                                    # ここまで来たらログ出力対象
                                    messages.append(
                                        f"[テーマログ][rule] layer order={order} id={lid} name='{lname}' rule_index={idx} filter={fexpr!r} scale=[{min_scale},{max_scale}] alpha={alpha_vals}"
                                    )
                                except Exception:
                                    continue

                            order += 1

                        except Exception:
                            try:
                                messages.append(f"[テーマログ] layer order={order} id={lid} name='{lname}' renderer_inspect_failed")
                                order += 1
                            except Exception:
                                pass

                    except Exception:
                        continue
            except Exception:
                messages = ["[テーマログ] エラーによりレイヤ取得失敗"]

            # 出力（QgsMessageLog が使えない場合は print）
            for m in messages:
                try:
                    if QgsMessageLog:
                        try:
                            QgsMessageLog.logMessage(m, "GEO-search-plugin", 0)
                        except Exception:
                            print(m)
                    else:
                        print(m)
                except Exception:
                    try:
                        print(m)
                    except Exception:
                        pass

        finally:
            # 元の状態を復元（登録できた一時テーマ名があれば適用してから削除）
            try:
                if prev_saved:
                    try:
                        try:
                            theme_collection.applyTheme(tmp_name, root, model)
                        except Exception:
                            theme_collection.applyTheme(tmp_name)
                    except Exception:
                        pass
                    # 削除
                    for rem_name in ("removeMapTheme", "remove", "deleteTheme", "removeTheme"):
                        if hasattr(theme_collection, rem_name):
                            try:
                                getattr(theme_collection, rem_name)(tmp_name)
                                break
                            except Exception:
                                continue
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


__all__ = [
    "apply_theme",
    "_get_theme_brackets",
    "parse_theme_group",
    "group_themes",
    
]
