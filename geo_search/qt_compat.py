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


def get_enum_value(container, name: str):
    """汎用の enum 取得ヘルパー。
    - まず container.<name> を探す
    - なければ container.SelectionBehavior.<name> や container.OpenMode.<name> 等の
      ネストされた列挙型の中を探す
    - 見つからなければ None を返す
    """
    if container is None:
        return None
    # direct
    val = getattr(container, name, None)
    if val is not None:
        return val

    # common nested enum containers to try
    nested_names = (
        'SelectionBehavior', 'OpenMode', 'OpenModeFlag',
        'DockWidgetFeature', 'DockWidgetFeatures', 'Feature', 'Enum'
    )
    for attr in nested_names:
        nested = getattr(container, attr, None)
        if nested is not None:
            v = getattr(nested, name, None)
            if v is not None:
                return v

    # some bindings expose enums as classes under Qt namespace
    try:
        # try Qt.<Container>.<name> where container may be a class object
        qtmod = QtCore if 'QtCore' in globals() else None
        if qtmod is not None:
            for attr in dir(qtmod):
                try:
                    c = getattr(qtmod, attr)
                    if hasattr(c, name):
                        return getattr(c, name)
                except Exception:
                    continue
    except Exception:
        pass
    return None


def get_qiode_writeonly(qiode):
    """Qt6/Qt5 の差分を吸収して QIODevice.WriteOnly 相当の値を返す。
    優先順:
      1) getattr(QIODevice, 'WriteOnly', None)
      2) getattr(QIODevice, 'OpenMode', None).WriteOnly
      3) getattr(QIODevice, 'OpenModeFlag', None).WriteOnly
      4) フォールバックで整数 1
    """
    if qiode is None:
        return 1
    v = getattr(qiode, 'WriteOnly', None)
    if v is not None:
        return v
    openmode = getattr(qiode, 'OpenMode', None)
    if openmode is not None:
        v = getattr(openmode, 'WriteOnly', None)
        if v is not None:
            return v
    openmodeflag = getattr(qiode, 'OpenModeFlag', None)
    if openmodeflag is not None:
        v = getattr(openmodeflag, 'WriteOnly', None)
        if v is not None:
            return v
    # last resort
    return 1


def get_dock_feature(dock_cls, name: str):
    """QDockWidget のフラグ名を互換的に取り出すヘルパー。
    例: get_dock_feature(QDockWidget, 'DockWidgetMovable')
    """
    if dock_cls is None:
        return None
    val = getattr(dock_cls, name, None)
    if val is not None:
        return val
    # try nested enum containers
    for attr in ('DockWidgetFeature', 'DockWidgetFeatures', 'Feature'):
        nested = getattr(dock_cls, attr, None)
        if nested is not None:
            v = getattr(nested, name, None)
            if v is not None:
                return v
    return None


def exec_dialog(dialog):
    """QDialog 等の exec 呼び出しを互換的に行う。
    Qt5 では exec_(), Qt6 では exec() となるため両方対応。
    """
    if dialog is None:
        return None
    if hasattr(dialog, 'exec_'):
        return dialog.exec_()
    # fallback: exec (Qt6)
    return dialog.exec()


__all__ = [
    'QtCore', 'QtGui', 'QtWidgets', 'uic',
    'QT_VERSION', 'IS_QT6', 'Signal', 'QRegExpCompat', 'get_enum',
    'get_enum_value', 'get_qiode_writeonly', 'get_dock_feature', 'exec_dialog'
]


# Monkey-patch QgsMessageLog.logMessage to accept legacy integer levels (0/1/2)
try:
    from qgis.core import QgsMessageLog, Qgis
    _orig_log = getattr(QgsMessageLog, 'logMessage', None)

    def _patched_log_message(message, tag='', level=None):
        try:
            # map legacy ints to Qgis.MessageLevel
            if isinstance(level, int):
                level = {0: Qgis.Info, 1: Qgis.Warning, 2: Qgis.Critical}.get(level, level)
            if level is None:
                level = Qgis.Info
        except Exception:
            # fallback: leave level as-is
            pass
        try:
            if _orig_log is not None:
                return _orig_log(message, tag, level)
        except Exception:
            # best-effort: print to stdout
            try:
                print(f"{tag}: {message}")
            except Exception:
                pass

    try:
        setattr(QgsMessageLog, 'logMessage', _patched_log_message)
    except Exception:
        # ignore if we cannot patch
        pass
except Exception:
    # qgis not available in this environment; ignore
    pass
