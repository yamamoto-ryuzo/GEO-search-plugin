# -*- coding: utf-8 -*-
"""
簡易デモ: 環境変数で変更可能な括弧を使ってテーマ名をグループ化する
実行例:
    python scripts/theme_group_demo.py
環境変数:
    THEME_BRACKET_OPEN  (例: '[' )
    THEME_BRACKET_CLOSE (例: ']' )
"""
import os
import re


def _get_theme_brackets():
    open_b = os.environ.get("THEME_BRACKET_OPEN")
    close_b = os.environ.get("THEME_BRACKET_CLOSE")
    if open_b is None and close_b is None:
        return "【", "】"
    if open_b is None:
        open_b = "【"
    if close_b is None:
        close_b = "】"
    return open_b, close_b


def parse_theme_group(theme_name):
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


def group_themes(theme_names):
    groups = {}
    for name in theme_names:
        grp = parse_theme_group(name)
        groups.setdefault(grp, []).append(name)
    return groups


if __name__ == '__main__':
    sample = [
        "道路【道路種別】_昼",
        "道路【道路種別】_夜",
        "行政区域【市区町村】",
        "公園",
        "公共施設【施設種別】A",
        "公共施設【施設種別】B",
        "その他"
    ]
    print("使用する括弧: {} {}".format(*_get_theme_brackets()))
    grouped = group_themes(sample)
    for k, v in grouped.items():
        print("--- グループ: {} ---".format(k))
        for name in v:
            print("  {}".format(name))
