# -*- coding: utf-8 -*-
"""
簡易デモ: 環境変数で変更可能な括弧を使ってテーマ名をグループ化する
実行例:
    python scripts/theme_group_demo.py
環境変数:
    THEME_BRACKET_OPEN  (例: '[' )
    THEME_BRACKET_CLOSE (例: ']' )
"""
import sys
import os

# スクリプト直実行時にリポジトリルートをパスに追加してパッケージ import を可能にする
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from geo_search.theme import _get_theme_brackets, group_themes


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
