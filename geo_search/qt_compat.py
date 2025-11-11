"""
Qt5/Qt6 互換ヘルパー (QGIS の qgis.PyQt を優先して使用)

このファイルは移行準備のための最小限の互換層です。静的解析環境や
QGIS がインポートできない環境でも解析/テストが走るよう、動的にインポート
する実装にしてあります。

主な目的:
- qgis.PyQt を通した参照を抽象化して将来的な Qt6 差分をここで吸収する。
- QGIS が提供する shim が存在しない環境でもフォールバックを提供する。
"""
import importlib
import types
from typing import Optional


def _import_module_candidates(candidates):
    """リスト中のモジュール名を順に試し、最初に import できたモジュールを返す。"""
    for name in candidates:
        try:
            return importlib.import_module(name)
        except Exception:
            continue
    return None


# Qt モジュール群を取得 (qgis.PyQt を優先)
QtCore = _import_module_candidates(['qgis.PyQt.QtCore', 'PyQt6.QtCore', 'PyQt5.QtCore', 'PySide6.QtCore', 'PySide2.QtCore'])
QtGui = _import_module_candidates(['qgis.PyQt.QtGui', 'PyQt6.QtGui', 'PyQt5.QtGui', 'PySide6.QtGui', 'PySide2.QtGui'])
QtWidgets = _import_module_candidates(['qgis.PyQt.QtWidgets', 'PyQt6.QtWidgets', 'PyQt5.QtWidgets', 'PySide6.QtWidgets', 'PySide2.QtWidgets'])
uic = _import_module_candidates(['qgis.PyQt.uic', 'PyQt6.uic', 'PyQt5.uic'])

# Qt のバージョン情報
QT_VERSION = (0, 0, 0)
IS_QT6 = False
if QtCore is not None:
    try:
        _qt_version = [int(v) for v in QtCore.qVersion().split('.') if v.isdigit()]
        QT_VERSION = tuple(_qt_version)
        IS_QT6 = _qt_version[0] >= 6
    except Exception:
        pass


# Signal alias: pyqtSignal / Signal のどちらかを使う
Signal = None
if QtCore is not None:
    Signal = getattr(QtCore, 'pyqtSignal', None) or getattr(QtCore, 'Signal', None)


# QRegExp / QRegularExpression の互換名
QRegExpCompat = None
if QtCore is not None:
    QRegExpCompat = getattr(QtCore, 'QRegularExpression', None) or getattr(QtCore, 'QRegExp', None)


def get_enum(enum_container, name: str):
    """列挙型名を安全に取り出す (enum_container は Qt モジュールなど)
    例: get_enum(QtCore.Qt, 'AlignLeft') -> 適切な列挙値
    """
    if enum_container is None:
        return None
    return getattr(enum_container, name, None)


__all__ = [
    'QtCore', 'QtGui', 'QtWidgets', 'uic',
    'QT_VERSION', 'IS_QT6', 'Signal', 'QRegExpCompat', 'get_enum'
]
