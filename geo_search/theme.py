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
            
            # 凡例ノード（レイヤパネルの表示チェック）のみで判定するユーティリティ群

            # 選択テーマ適用後、レイヤパネルで可視になっているレイヤ一覧をログ出力
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
                        # そのレイヤに対応する凡例ノードを取得し、チェックされているノードのみログ出力
                        # ルールベースレンダラーが使われている場合、各ルールの label と active() をログ出力
                        try:
                            # renderer を安全に取得する
                            try:
                                renderer = layer.renderer()
                            except Exception:
                                renderer = None

                            if renderer is not None:
                                try:
                                    from qgis.core import QgsRuleBasedRenderer
                                    if isinstance(renderer, QgsRuleBasedRenderer):
                                        try:
                                            root_rule = renderer.rootRule()

                                            def _collect_rules(rule):
                                                out = []
                                                for ch in rule.children():
                                                    out.append(ch)
                                                    out.extend(_collect_rules(ch))
                                                return out

                                            for r in _collect_rules(root_rule):
                                                try:
                                                    lbl = r.label() or "(no label)"
                                                except Exception:
                                                    lbl = "(label error)"
                                                try:
                                                    active = bool(r.active())
                                                except Exception:
                                                    active = False
                                                # 非アクティブなルール(active=False)は出力しない
                                                if active:
                                                    messages.append(
                                                        f"[テーマログ][rule] layer={lname} rule_label={lbl}"
                                                    )
                                        except Exception:
                                            # renderer introspection failed; ignore
                                            pass
                                except Exception:
                                    # qgis.core import may fail outside QGIS
                                    pass
                        except Exception:
                            pass

                        order += 1
                    except Exception:
                        continue
            except Exception:
                messages = ["[テーマログ] レイヤ一覧の取得に失敗しました"]

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
