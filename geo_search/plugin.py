# -*- coding: utf-8 -*-
from ast import IsNot
from asyncio.windows_events import NULL
from collections import OrderedDict
from contextlib import nullcontext
import json
import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QComboBox, QWidget, QToolButton, QHBoxLayout
from qgis.core import (
    QgsProject,
    QgsExpressionContextUtils,
)
"""QGIS プラグイン Qt 互換インポート

PyQt5 を直接参照していた箇所を qgis.PyQt 経由に統一し、
将来の Qt6 / PyQt6 互換 (QGIS の shim) に備える。
"""

from .constants import OTHER_GROUP_NAME
from .searchfeature import (
    SearchTextFeature,
    SearchTibanFeature,
    SearchOwnerFeature,
)
from .searchdialog import SearchDialog
from .theme import apply_theme

# TODO: Fieldの確認
# TODO: 表示テーブルの順番変更


class plugin(object):
    def __init__(self, iface):
        # Ensure compatibility shim is loaded when plugin instance is created.
        # This is defensive: classFactory also attempts to import the shim, but
        # importing it here guarantees the monkey-patch for QgsMessageLog is
        # applied before any logMessage calls executed by this instance.
        try:
            import importlib
            importlib.import_module('geo_search.qt_compat')
        except Exception:
            # ignore failures; plugin should still attempt to run
            pass
        self.iface = iface
        # GUI-ready flag: set to True at the end of initGui(). Some QGIS
        # signals (projectRead, etc.) may fire before initGui runs; checking
        # this flag avoids noisy warnings when widgets like theme_combobox
        # are not yet created.
        self._gui_ready = False
        # guard to avoid connecting theme collection signals multiple times
        self._theme_signals_connected = False
        # last time we logged a missing theme_combobox warning (seconds)
        self._last_missing_combobox_warning = 0.0
        # diagnostic call counter for update_theme_combobox
        self._theme_update_call_count = 0
        self._init_language()
        self.current_feature = None
        self._current_group_widget = None
        self._search_features = []
        self._search_group_features = OrderedDict()
        self.current_layers = []  # 追加されたレイヤを管理するリスト

    def _init_language(self):
        """QGISとプラグインの言語設定を自動化"""
        try:
            from qgis.PyQt.QtCore import QSettings, QLocale, QTranslator, QCoreApplication
            import os
            # QGIS の設定から言語取得（なければ OS のロケール）
            settings = QSettings()
            raw_locale = settings.value('locale/userLocale', None)
            if raw_locale is None:
                raw_locale = QLocale.system().name()

            # raw_locale may be 'ja_JP' or 'en' etc. Normalize to language code 'ja', 'en', ...
            try:
                if isinstance(raw_locale, str) and '_' in raw_locale:
                    lang_code = raw_locale.split('_')[0]
                elif isinstance(raw_locale, str) and '-' in raw_locale:
                    lang_code = raw_locale.split('-')[0]
                else:
                    lang_code = str(raw_locale)
                lang_code = lang_code.lower()
            except Exception:
                lang_code = QLocale.system().name().split('_')[0]

            # Supported languages (keep in sync with i18n/*.qm)
            supported = { 'en', 'fr', 'de', 'es', 'it', 'pt', 'ja', 'zh', 'ru', 'hi' }

            # If English, no translator needed (source strings are English)
            if lang_code == 'en' or lang_code not in supported:
                return

            # Try to load a matching .qm file from the i18n folder.
            qm_name = f"{lang_code}.qm"
            qm_path = os.path.join(os.path.dirname(__file__), 'i18n', qm_name)
            if os.path.exists(qm_path):
                translator = QTranslator()
                loaded = translator.load(qm_path)
                if loaded:
                    QCoreApplication.installTranslator(translator)
        except Exception as e:
            # エラーは無視（QGIS外実行時など）。開発時はログで確認する。
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"_init_language error: {e}", "GEO-search-plugin", 1)
            except Exception:
                pass

    def initGui(self):
        # プラグイン開始時に動作
        # mark GUI not-ready at start to avoid spurious warnings during init
        try:
            self._gui_ready = False
        except Exception:
            pass
        # メッセージ表示
        # QMessageBox.information(None, "iniGui", "Gui構築", QMessageBox.Yes)

        # ダイヤログ構築
        self.create_search_dialog()

        # アイコン設定
        icon_path = os.path.join(os.path.dirname(__file__), "icon/qgis-icon.png")
        self.action = QAction(QIcon(icon_path), "地図検索", self.iface.mainWindow())
        self.action.setObjectName("地図検索")
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("地図検索", self.action)
        # 追加表示切替アクション（検索アイコンの直後に置く）
        # reload 時に重複して追加されないよう既存チェックを行う
        try:
            if not hasattr(self, 'additive_theme_action') or self.additive_theme_action is None:
                try:
                    try:
                        # prefer custom icons: OFF state 'theme-switch.PNG', ON state 'theme-additive.png'
                        icon_dir = os.path.join(os.path.dirname(__file__), "icon")
                        on_icon_path = os.path.join(icon_dir, "theme-additive.png")
                        off_icon_path = os.path.join(icon_dir, "theme-switch.png")
                        fallback_icon_path = os.path.join(icon_dir, "qgis-icon.png")
                        # decide initial icon (start OFF)
                        initial_icon_path = off_icon_path if os.path.exists(off_icon_path) else fallback_icon_path
                        self.additive_theme_action = QAction(QIcon(initial_icon_path), "", self.iface.mainWindow())
                    except Exception:
                        self.additive_theme_action = QAction("", self.iface.mainWindow())
                    self.additive_theme_action.setCheckable(True)
                    self.additive_theme_action.setChecked(False)
                    self.additive_theme_action.setToolTip("選択したテーマの表示レイヤを現在の表示に追加します（オン：追加表示、オフ：通常上書き）")
                    try:
                        # connect to handler that updates internal flag and icon
                        try:
                            self.additive_theme_action.toggled.connect(self._on_additive_toggled)
                        except Exception:
                            # fallback to simple lambda if method not available
                            self.additive_theme_action.toggled.connect(lambda checked: setattr(self, '_theme_additive_mode', bool(checked)))
                    except Exception:
                        pass
                    try:
                        self.iface.addToolBarIcon(self.additive_theme_action)
                    except Exception:
                        try:
                            self.iface.addToolBarWidget(self.additive_theme_action)
                        except Exception:
                            pass
                except Exception:
                    try:
                        self._theme_additive_mode = False
                    except Exception:
                        pass
            else:
                # 既に存在する場合は状態を初期化しておく
                try:
                    self.additive_theme_action.setChecked(False)
                except Exception:
                    pass
        except Exception:
            pass
        
        # テーマ一覧のドロップダウンを作成
        # グループ選択用コンボ（グループを選んでテーマ表示を絞れる）
        self.group_combobox = QComboBox()
        self.group_combobox.setToolTip("グループを選択して表示するテーマを絞ります（すべて/グループ単位）")
        self.group_combobox.setMinimumWidth(140)
        self.iface.addToolBarWidget(self.group_combobox)

        # グループ選択の前回値を保持する（update時に復元するため）
        self._last_group_selected = None

        # テーマ適用中に自動更新を抑止するフラグ
        self._suppress_theme_update = False

        self.theme_combobox = QComboBox()
        self.theme_combobox.setToolTip("レイヤの表示/非表示を設定するマップテーマを選択（「テーマ選択」で基本表示に戻す）")
        self.theme_combobox.setMinimumWidth(180)

        # テーマ選択の右側に設定アイコンを表示するためのコンテナウィジェットを作成
        try:
            # 再ロード時に重複して追加しないよう既存の widget を流用する
            if not hasattr(self, 'theme_widget') or self.theme_widget is None:
                self.theme_widget = QWidget()
                self.theme_layout = QHBoxLayout()
                # マージンを無くしてツールバーに馴染ませる
                try:
                    self.theme_layout.setContentsMargins(0, 0, 0, 0)
                except Exception:
                    pass
                try:
                    self.theme_layout.setSpacing(4)
                except Exception:
                    pass
                self.theme_widget.setLayout(self.theme_layout)
                # add combobox to layout
                try:
                    self.theme_layout.addWidget(self.theme_combobox)
                except Exception:
                    pass

                # 設定用アイコン（実装は不要、表示のみ）
                try:
                    self.setting_button = QToolButton()
                    icon_path = os.path.join(os.path.dirname(__file__), "icon", "setting.png")
                    try:
                        self.setting_button.setIcon(QIcon(icon_path))
                    except Exception:
                        pass
                    self.setting_button.setToolTip("テーマ設定")
                    # 設定ダイアログを開く処理を接続
                    try:
                        self.setting_button.clicked.connect(self.open_settings_dialog)
                    except Exception:
                        pass
                    try:
                        self.setting_button.setEnabled(True)
                        self.setting_button.setVisible(True)
                    except Exception:
                        pass
                    self.theme_layout.addWidget(self.setting_button)
                except Exception:
                    # fallback: 何もせずにコンボだけ追加
                    pass

                # ツールバーにはコンテナを追加
                try:
                    self.iface.addToolBarWidget(self.theme_widget)
                except Exception:
                    # fallback to adding combobox directly
                    try:
                        self.iface.addToolBarWidget(self.theme_combobox)
                    except Exception:
                        pass
            else:
                # 既に widget が存在する場合は再追加を行わない。
                # ただし古い状態で combobox が別の親にいる可能性があるため
                # layout に含まれていなければ追加しておく。
                try:
                    if hasattr(self, 'theme_layout') and self.theme_layout is not None:
                        # combobox が既に layout に属しているか簡易チェック
                        try:
                            parent = self.theme_combobox.parent()
                        except Exception:
                            parent = None
                        try:
                            if parent is not self.theme_widget:
                                self.theme_layout.addWidget(self.theme_combobox)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            # 保守的に元の方法で追加
            try:
                self.iface.addToolBarWidget(self.theme_combobox)
            except Exception:
                pass

        self._theme_additive_mode = False

        # 内部キャッシュ: グループ -> [テーマ名,...]
        self._theme_groups = {}

        # 接続: グループ選択でテーマを絞る
        try:
            self.group_combobox.currentIndexChanged.connect(self.on_group_changed)
        except Exception:
            pass

        # 初回更新
        self.update_theme_combobox()
        
        # (以前はテーマの前回選択を内部保持していましたが、
        #  ユーザー操作による自動復元は不要なため削除しました)
        
        # テーマ選択時のイベント接続
        # Note: connect only to `activated` to avoid duplicate calls because
        # `currentIndexChanged` may also fire for programmatic changes.
        try:
            self.theme_combobox.activated.connect(self.apply_selected_theme)
        except Exception:
            pass

        # トリガー構築
        self.action.triggered.connect(self.run)
        self.iface.projectRead.connect(self.create_search_dialog)
        self.iface.projectRead.connect(self.update_theme_combobox)
        
        # プロジェクト変数とテーマ変更を検知するための接続
        try:
            # プロジェクト保存時
            QgsProject.instance().projectSaved.connect(self.on_project_saved)
            QgsProject.instance().projectSaved.connect(self.update_theme_combobox)
            
            # テーマコレクションの変更を検知（重要：テーマが追加/削除された時に自動更新）
            project = QgsProject.instance()
            theme_collection = project.mapThemeCollection()
            # Connect theme collection signals only once to avoid duplicate handlers
            try:
                if not getattr(self, '_theme_signals_connected', False):
                    try:
                        # connect to wrapper handlers so we can log which signal fired
                        try:
                            theme_collection.mapThemesChanged.connect(self._on_map_themes_changed)
                        except Exception:
                            # fallback to direct connection if wrapper can't be connected
                            theme_collection.mapThemesChanged.connect(self.update_theme_combobox)
                    except Exception:
                        # 古いバージョン向けの代替手段
                        try:
                            try:
                                theme_collection.changed.connect(self._on_theme_collection_changed)
                            except Exception:
                                theme_collection.changed.connect(self.update_theme_combobox)
                        except Exception:
                            pass
                    try:
                        self._theme_signals_connected = True
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"theme signals connected (instance={id(self)})", "GEO-search-plugin", 0)
                    except Exception:
                        pass
                else:
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"theme signals already connected (instance={id(self)})", "GEO-search-plugin", 0)
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"テーマ監視エラー: {str(e)}", "GEO-search-plugin", 2)
            except:
                pass

        # GUI is now ready for warnings/updates
        try:
            self._gui_ready = True
        except Exception:
            pass

    def _safe_current_text(self, widget):
        """Safely return currentText() from a combo-like widget or empty string.

        This avoids crashing when the widget is None or currentText() returns None.
        """
        try:
            if widget is None:
                return ""
            if hasattr(widget, 'currentText'):
                t = widget.currentText()
                return t if t is not None else ""
        except Exception:
            pass
        return ""


    def _on_additive_toggled(self, checked):
        """Handler for additive_theme_action.toggled

        Updates internal flag and switches the icon between OFF/ON images.
        """
        try:
            # set internal flag
            self._theme_additive_mode = bool(checked)
        except Exception:
            pass
        try:
            # update icon according to state
            icon_dir = os.path.join(os.path.dirname(__file__), "icon")
            on_icon = os.path.join(icon_dir, "theme-additive.png")
            off_icon = os.path.join(icon_dir, "theme-switch.PNG")
            fallback_icon = os.path.join(icon_dir, "qgis-icon.png")
            if checked:
                path = on_icon if os.path.exists(on_icon) else fallback_icon
            else:
                path = off_icon if os.path.exists(off_icon) else fallback_icon
            try:
                self.additive_theme_action.setIcon(QIcon(path))
            except Exception:
                pass
        except Exception:
            pass
        # propagate state to search feature instances so search-time theme application
        # uses the same additive/overwrite behavior
        try:
            v = bool(getattr(self, '_theme_additive_mode', False))
            try:
                for f in getattr(self, '_search_features', []):
                    try:
                        setattr(f, 'theme_additive_mode', v)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                for group, flist in getattr(self, '_search_group_features', {}).items():
                    try:
                        for f in flist:
                            try:
                                setattr(f, 'theme_additive_mode', v)
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass

    def _populate_group_combobox(self, grouped):
        """Populate the group combobox from grouped dict."""
        try:
            self.group_combobox.blockSignals(True)
            self.group_combobox.clear()
            # Placeholder, then only actual groups
            self.group_combobox.addItem("すべて")
            for g in sorted([k for k in grouped.keys() if k is not None]):
                self.group_combobox.addItem(str(g))
        except Exception:
            pass
        finally:
            try:
                self.group_combobox.blockSignals(False)
            except Exception:
                pass

    def on_group_changed(self, index):
        """Called when user selects a group; filter themes accordingly."""
        try:
            sel = self._safe_current_text(self.group_combobox)
            # 記録しておく（次回 update の際に復元に使う）
            try:
                self._last_group_selected = sel
            except Exception:
                pass
            # グループ未選択(プレースホルダ 'すべて') の場合は全てのテーマを表示する
            if not sel or sel == "すべて":
                try:
                    themes_to_show = [t for lst in self._theme_groups.values() for t in lst]
                except Exception:
                    themes_to_show = []
            else:
                # 選択されたグループのテーマのみを表示
                themes_to_show = self._theme_groups.get(sel, [])

            try:
                self.theme_combobox.blockSignals(True)
            except Exception:
                pass
            try:
                self.theme_combobox.clear()
                self.theme_combobox.addItem("テーマ選択")
                for t in themes_to_show:
                    self.theme_combobox.addItem(t)
            finally:
                try:
                    self.theme_combobox.blockSignals(False)
                except Exception:
                    pass
        except Exception:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage("group change handling error", "GEO-search-plugin", 2)
            except Exception:
                pass

    def update_theme_combobox(self):
        """マップテーマのコンボボックスを更新する"""
        try:
            # diagnostic: log entry with instance and flags
            try:
                from qgis.core import QgsMessageLog
                try:
                    # increment per-instance call counter for diagnostics
                    self._theme_update_call_count = int(getattr(self, '_theme_update_call_count', 0)) + 1
                except Exception:
                    pass
                QgsMessageLog.logMessage(
                    f"update_theme_combobox called (instance={id(self)} call={getattr(self, '_theme_update_call_count', 0)} _gui_ready={getattr(self, '_gui_ready', False)} _suppress={getattr(self, '_suppress_theme_update', False)})",
                    "GEO-search-plugin",
                    0,
                )
            except Exception:
                pass
            # apply_selected_theme 実行中は外部シグナルによる自動更新を抑止する
            if getattr(self, '_suppress_theme_update', False):
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage("update_theme_combobox: suppressed during theme apply", "GEO-search-plugin", 0)
                except Exception:
                    pass
                return
            from qgis.core import QgsProject, QgsMessageLog
            project = QgsProject.instance()
            theme_collection = project.mapThemeCollection()
            try:
                raw_themes = theme_collection.mapThemes()
            except Exception:
                raw_themes = []

            # normalize to list of names (mapThemes may return strings or theme objects)
            themes = []
            for t in (raw_themes or []):
                try:
                    if isinstance(t, str):
                        themes.append(t)
                    else:
                        if hasattr(t, 'name') and callable(getattr(t, 'name')):
                            themes.append(t.name())
                        elif hasattr(t, 'name'):
                            themes.append(getattr(t, 'name'))
                        elif hasattr(t, 'displayName') and callable(getattr(t, 'displayName')):
                            themes.append(t.displayName())
                        elif hasattr(t, 'displayName'):
                            themes.append(getattr(t, 'displayName'))
                        else:
                            themes.append(str(t))
                except Exception:
                    continue
            # safety: theme_combobox may not exist (initGui not yet run or unloaded)
            if not hasattr(self, 'theme_combobox') or self.theme_combobox is None:
                # During startup/unload the combobox may legitimately be absent.
                # Only emit a warning when GUI is ready and updates are not being
                # deliberately suppressed (e.g. during theme apply). This avoids
                # plugin init/unload or while applying a theme.
                try:
                    gui_ready = bool(getattr(self, '_gui_ready', False))
                    suppressed = bool(getattr(self, '_suppress_theme_update', False))
                    if gui_ready and not suppressed:
                        # rate-limit duplicate warnings to avoid log spam when multiple
                        # map-theme related signals fire in quick succession.
                        try:
                            import time
                            now = time.time()
                            last = float(getattr(self, '_last_missing_combobox_warning', 0.0))
                            # only log once per second per instance
                            if now - last < 1.0:
                                return
                            try:
                                self._last_missing_combobox_warning = now
                            except Exception:
                                pass
                        except Exception:
                            pass
                        import traceback
                        stack = ''.join(traceback.format_stack(limit=6))
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(
                            f"update_theme_combobox: theme_combobox is not available (instance={id(self)} _gui_ready={gui_ready} _suppress={suppressed}). stack:\n{stack}",
                            "GEO-search-plugin",
                            1,
                        )
                except Exception:
                    pass
                return

            # 現在選択されているテーマを保存（安全に取得）
            current_theme = self._safe_current_text(self.theme_combobox)
            
            # コンボボックスをクリア
            self.theme_combobox.blockSignals(True)
            self.theme_combobox.clear()
            # 「テーマ選択」というプレースホルダーを追加
            self.theme_combobox.addItem("テーマ選択")

            # マップテーマをグループ化して管理（グループ名は括弧で囲まれた部分を抽出）
            try:
                from .theme import group_themes

                grouped = group_themes(themes)
                # 保存
                self._theme_groups = grouped

                # group_combobox を更新（シグナルをブロックして復元を試みる）
                try:
                    prev_group = self._safe_current_text(self.group_combobox)
                    # ブロックして populate + restore を行う（on_group_changed の誤発火を防ぐ）
                    try:
                        self.group_combobox.blockSignals(True)
                    except Exception:
                        pass
                    try:
                        self._populate_group_combobox(grouped)
                        # まず以前の表示（UI 上の選択）を優先して復元
                        if prev_group:
                            idx_prev = self.group_combobox.findText(prev_group)
                            if idx_prev >= 0:
                                self.group_combobox.setCurrentIndex(idx_prev)
                        # 次にプロセス内で最後に記録された選択を試す
                        if (not prev_group or self.group_combobox.currentIndex() <= 0) and hasattr(self, '_last_group_selected') and self._last_group_selected:
                            idx_last = self.group_combobox.findText(self._last_group_selected)
                            if idx_last >= 0:
                                self.group_combobox.setCurrentIndex(idx_last)
                    finally:
                        try:
                            self.group_combobox.blockSignals(False)
                        except Exception:
                            pass

                    # 復元後の group 選択に基づいてテーマを表示
                    cur_group_txt = self._safe_current_text(self.group_combobox)
                    # グループ未選択(プレースホルダ 'すべて') の場合は全てのテーマを表示する
                    if not cur_group_txt or cur_group_txt == "すべて":
                        themes_to_show = [t for lst in grouped.values() for t in lst]
                    else:
                        themes_to_show = grouped.get(cur_group_txt, [])
                except Exception:
                    themes_to_show = [t for lst in grouped.values() for t in lst]
                # 表示順: グループ名のあるものを先、グループなし (None) を最後に
                named_groups = [g for g in grouped.keys() if g is not None]
                named_groups.sort()

                # themes_to_show をコンボに追加
                for t in themes_to_show:
                    self.theme_combobox.addItem(t)
            except Exception:
                # フォールバック: グループ化できない場合は従来通り追加
                for theme in themes:
                    self.theme_combobox.addItem(theme)
            
            # 前回選択されていたテーマがまだ存在するなら、それを選択状態に
            if current_theme in themes:
                index = self.theme_combobox.findText(current_theme)
                if index >= 0:
                    self.theme_combobox.setCurrentIndex(index)
            
            # デバッグログ
            QgsMessageLog.logMessage(f"テーマリスト更新: {', '.join(themes)}", "GEO-search-plugin", 0)
                
            self.theme_combobox.blockSignals(False)
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"テーマコンボボックスの更新エラー: {str(e)}", "GEO-search-plugin", 2)
            except Exception:
                pass
    

    
    def apply_selected_theme(self, index):
        """選択されたテーマを適用する"""
        # prevent re-entrant/duplicate applies
        if getattr(self, '_applying_theme', False):
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage("apply_selected_theme: re-entrant call ignored", "GEO-search-plugin", 0)
            except Exception:
                pass
            return
        try:
            self._applying_theme = True
        except Exception:
            pass
        try:
            from qgis.core import QgsProject, QgsMessageLog
            project = QgsProject.instance()
            theme_collection = project.mapThemeCollection()
            # safety: theme_combobox may not exist
            if not hasattr(self, 'theme_combobox') or self.theme_combobox is None:
                try:
                    QgsMessageLog.logMessage("apply_selected_theme: theme_combobox is not available", "GEO-search-plugin", 1)
                except Exception:
                    pass
                # Ensure applying flag is cleared before returning so subsequent
                # activations aren't blocked by a stale re-entrant guard.
                try:
                    self._applying_theme = False
                except Exception:
                    pass
                return

            # 現在のテーマテキストを取得（安全に取得）
            current_theme_text = self._safe_current_text(self.theme_combobox)
            
            # 「テーマ選択」の場合は何もしない（プレースホルダ選択は無視）
            if current_theme_text == "テーマ選択" or index <= 0:
                # Clear any in-progress flag so the re-entrant guard does not remain set.
                try:
                    self._suppress_theme_update = False
                except Exception:
                    pass
                try:
                    self._applying_theme = False
                except Exception:
                    pass
                return
                
            # 選択されたテーマを適用
            theme_name = current_theme_text
            
            # 同じテーマを再選択した場合も適用する
            # (前回と同じ選択でも強制的にテーマを適用)
            root = project.layerTreeRoot()
            model = self.iface.layerTreeView().layerTreeModel()

            # apply 中に mapThemesChanged 等のシグナルが発生して
            # update_theme_combobox が走ると UI 候補が書き換わる可能性があるため
            # 一時的に更新を抑止するフラグを立てる
            try:
                    self._suppress_theme_update = True
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"apply_selected_theme: set _suppress_theme_update=True (instance={id(self)})", "GEO-search-plugin", 0)
                    except Exception:
                        pass
            except Exception:
                pass

            # apply theme: if additive mode is requested use centralized helper
            # which implements the union logic; otherwise perform a simple
            # theme switch using the theme collection API (equivalent to
            # changing the theme selection in the UI).
            try:
                if bool(getattr(self, '_theme_additive_mode', False)):
                    from .theme import apply_theme
                    apply_theme(theme_collection, theme_name, root, model, additive=True)
                else:
                    try:
                        # prefer applyTheme with root+model when available
                        try:
                            theme_collection.applyTheme(theme_name, root, model)
                        except Exception:
                            theme_collection.applyTheme(theme_name)
                    except Exception:
                        # fallback to centralized helper if direct call fails
                        from .theme import apply_theme
                        apply_theme(theme_collection, theme_name, root, model, additive=False)
            finally:
                # フラグを解除
                try:
                    self._suppress_theme_update = False
                except Exception:
                    pass
                try:
                    self._applying_theme = False
                except Exception:
                    pass
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"apply_selected_theme: cleared _suppress_theme_update/_applying_theme (instance={id(self)})", "GEO-search-plugin", 0)
                except Exception:
                    pass
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"テーマ適用エラー: {str(e)}", "GEO-search-plugin", 2)
            except Exception:
                pass

    def open_settings_dialog(self):
        """ツールバーの設定ボタンから開くシンプルな設定ダイアログを表示します。

        OK とキャンセルボタンを持ち、ユーザーの選択でダイアログを閉じます。
        実際の設定項目はここに追加できます。
        """
        try:
            # まずログに呼び出しを記録（QgsMessageLog または print）
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage("open_settings_dialog invoked", "GEO-search-plugin", 0)
            except Exception:
                try:
                    print("open_settings_dialog invoked")
                except Exception:
                    pass

            import importlib
            parent = None
            try:
                parent = self.iface.mainWindow()
            except Exception:
                parent = None

            # 専用の SettingsDialog があればそちらを使う
            try:
                from .settingsdialog import SettingsDialog
            except Exception:
                SettingsDialog = None

            if SettingsDialog is not None:
                dlg = SettingsDialog(parent=parent, iface=self.iface)
            else:
                # フォールバック: シンプルな QDialog を生成
                from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
                dlg = QDialog(parent)
                dlg.setWindowTitle("Settings")
                dlg.setMinimumSize(400, 120)
                layout = QVBoxLayout(dlg)
                layout.addWidget(QLabel("Settings dialog: add options here.", dlg))
                btn_layout = QHBoxLayout()
                btn_layout.addStretch()
                ok_btn = QPushButton("OK", dlg)
                cancel_btn = QPushButton("Cancel", dlg)
                ok_btn.clicked.connect(dlg.accept)
                cancel_btn.clicked.connect(dlg.reject)
                btn_layout.addWidget(ok_btn)
                btn_layout.addWidget(cancel_btn)
                layout.addLayout(btn_layout)

            try:
                qt_compat = importlib.import_module('geo_search.qt_compat')
            except Exception:
                qt_compat = None

            if qt_compat is not None:
                try:
                    qt_compat.exec_dialog(dlg)
                except Exception:
                    try:
                        dlg.exec_()
                    except Exception:
                        try:
                            dlg.exec()
                        except Exception:
                            pass
            else:
                try:
                    dlg.exec_()
                except Exception:
                    try:
                        dlg.exec()
                    except Exception:
                        pass
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"open_settings_dialog error: {e}", "GEO-search-plugin", 2)
            except Exception:
                try:
                    print(f"open_settings_dialog error: {e}")
                except Exception:
                    pass

    def _on_map_themes_changed(self, *args, **kwargs):
        """Wrapper for mapThemesChanged signal: log and delegate."""
        try:
            from qgis.core import QgsMessageLog
            QgsMessageLog.logMessage(f"mapThemesChanged signal received (instance={id(self)})", "GEO-search-plugin", 0)
        except Exception:
            pass
        try:
            self.update_theme_combobox()
        except Exception:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage("_on_map_themes_changed: update failed", "GEO-search-plugin", 2)
            except Exception:
                pass

    def _on_theme_collection_changed(self, *args, **kwargs):
        """Wrapper for legacy theme collection 'changed' signal."""
        try:
            from qgis.core import QgsMessageLog
            QgsMessageLog.logMessage(f"themeCollection.changed signal received (instance={id(self)})", "GEO-search-plugin", 0)
        except Exception:
            pass
        try:
            self.update_theme_combobox()
        except Exception:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage("_on_theme_collection_changed: update failed", "GEO-search-plugin", 2)
            except Exception:
                pass
    
    def unload(self):
        # プラグイン終了時に動作（例外処理を追加）
        # mark GUI not-ready to suppress warnings while widgets are being removed
        try:
            self._gui_ready = False
        except Exception:
            pass
        # disconnect theme collection signals if we connected them
        try:
            if getattr(self, '_theme_signals_connected', False):
                try:
                    project = QgsProject.instance()
                    theme_collection = project.mapThemeCollection()
                    try:
                        try:
                            theme_collection.mapThemesChanged.disconnect(self._on_map_themes_changed)
                        except Exception:
                            try:
                                theme_collection.mapThemesChanged.disconnect(self.update_theme_combobox)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        try:
                            theme_collection.changed.disconnect(self._on_theme_collection_changed)
                        except Exception:
                            try:
                                theme_collection.changed.disconnect(self.update_theme_combobox)
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass
                try:
                    self._theme_signals_connected = False
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu("地図検索", self.action)
        except:
            pass
            
        # コンボボックスの削除も例外処理
        try:
            if hasattr(self, 'theme_combobox'):
                self.theme_combobox.deleteLater()
                self.theme_combobox = None
            # remove theme widget and button if present
            if hasattr(self, 'setting_button') and self.setting_button is not None:
                try:
                    try:
                        self.iface.removeToolBarWidget(self.setting_button)
                    except Exception:
                        pass
                except Exception:
                    pass
                try:
                    self.setting_button.deleteLater()
                except Exception:
                    pass
                try:
                    self.setting_button = None
                except Exception:
                    pass
            if hasattr(self, 'theme_widget') and self.theme_widget is not None:
                try:
                    try:
                        self.iface.removeToolBarWidget(self.theme_widget)
                    except Exception:
                        pass
                except Exception:
                    pass
                try:
                    self.theme_widget.deleteLater()
                except Exception:
                    pass
                try:
                    self.theme_widget = None
                except Exception:
                    pass
            if hasattr(self, 'group_combobox'):
                try:
                    self.group_combobox.deleteLater()
                except Exception:
                    pass
                self.group_combobox = None
            # 追加表示アクションの削除
            if hasattr(self, 'additive_theme_action') and self.additive_theme_action is not None:
                try:
                    try:
                        self.iface.removeToolBarIcon(self.additive_theme_action)
                    except Exception:
                        try:
                            self.iface.removeToolBarWidget(self.additive_theme_action)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    self.additive_theme_action.deleteLater()
                except Exception:
                    pass
                try:
                    self.additive_theme_action = None
                except Exception:
                    pass
        except:
            pass

    def create_search_dialog(self):
        # メッセージ表示
        # QMessageBox.information(None, "create_search_dialog", "ダイヤログ構築", QMessageBox.Yes)

        self.current_feature = None
        flag = 0

        # 設定開始
        input_json = ' {"SearchTabs": [ '
        input_json_file = ""
        input_json_variable = ""
        
        # 以前のダイアログが存在する場合は閉じる
        if hasattr(self, 'dialog') and self.dialog:
            try:
                self.dialog.close()
                self.dialog.deleteLater()  # メモリリークを防止
            except Exception:
                pass

        # setting.jsonの読込
        if os.path.exists(os.path.join(os.path.dirname(__file__), "setting.json")):
            setting_path = os.path.join(os.path.dirname(__file__), "setting.json")
            # ファイルから読込
            with open(setting_path) as f:
                # テキストとして読込
                input_json_file = f.read()

        # プロジェクト変数から追加読込
        # 変数名 GEO-search-plugin
        ProjectInstance = QgsProject.instance()
        
        # リフレッシュを試みる
        try:
            ProjectInstance.reloadAllLayers()
        except Exception:
            pass
            
        # テキストとして読込 - 複数の方法を試す
        try:
            ctx_var = QgsExpressionContextUtils.projectScope(ProjectInstance).variable(
                "GEO-search-plugin"
            )
        except Exception:
            ctx_var = None

        if ctx_var is not None:
            input_json_variable = ctx_var
            # 設定読み込みの診断ログ (QGIS メッセージログに出力)
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"Found variable from projectScope: {ctx_var}", "GEO-search-plugin", 0)
            except Exception:
                try:
                    print(f"Found variable from projectScope: {ctx_var}")
                except Exception:
                    pass
        else:
            # fallback: try readEntry / custom property
            try:
                ok, val = ProjectInstance.readEntry('GEO-search-plugin', 'value')
                if ok:
                    input_json_variable = val
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"Found variable from readEntry: {val}", "GEO-search-plugin", 0)
                    except Exception:
                        try:
                            print(f"Found variable from readEntry: {val}")
                        except Exception:
                            pass
            except Exception:
                try:
                    pv = ProjectInstance.customProperty('GEO-search-plugin')
                    if pv is not None:
                        input_json_variable = pv
                        try:
                            from qgis.core import QgsMessageLog
                            QgsMessageLog.logMessage(f"Found variable from customProperty: {pv}", "GEO-search-plugin", 0)
                        except Exception:
                            try:
                                print(f"Found variable from customProperty: {pv}")
                            except Exception:
                                pass
                except Exception:
                    pass

        # ファイルと変数を結合
        if input_json_file != "":
            input_json += input_json_file
            flag = 1
            # メッセージ表示
            # QMessageBox.information(None, "設定ファイルの読込", input_json_file , QMessageBox.Yes)
            if input_json_variable != "":
                input_json += ","
        if input_json_variable is not None and input_json_variable != "":
            # If the stored project variable is a JSON array or object, expand it
            try:
                parsed_var = json.loads(input_json_variable)
                if isinstance(parsed_var, list):
                    # join elements without surrounding array brackets to avoid nested arrays
                    elems = ",".join(json.dumps(el, ensure_ascii=False) for el in parsed_var)
                    input_json += elems
                elif isinstance(parsed_var, dict):
                    input_json += json.dumps(parsed_var, ensure_ascii=False)
                else:
                    input_json += json.dumps(parsed_var, ensure_ascii=False)
            except Exception:
                # fallback: use raw string
                input_json += input_json_variable
            flag = 1
            # メッセージ表示
            # QMessageBox.information(None, "設定変数の読込", input_json_variable , QMessageBox.Yes)

        # 設定終了
        input_json += '],"PageLimit": 10000}'
        # メッセージ表示
        # QMessageBox.information(None, "JSON設定", input_json , QMessageBox.Yes)

        if flag == 1:
            # テキストをJSONとして読込
            settings = json.loads(input_json)

            # メッセージ表示
            # QMessageBox.information(None, "create_search_dialog", "JSON読込", QMessageBox.Yes)

            self.dialog = SearchDialog(settings, parent=self.iface.mainWindow(), iface=self.iface)
            # Defensive: nudge dialog layout and resize any tables so headers don't
            # collapse to zero width on some platforms (Qt6 style differences).
            try:
                try:
                    self.dialog.adjustSize()
                except Exception:
                    pass
                from qgis.PyQt.QtWidgets import QTableWidget
                for t in self.dialog.findChildren(QTableWidget):
                    try:
                        t.resizeColumnsToContents()
                        t.resizeRowsToContents()
                    except Exception:
                        pass
            except Exception:
                pass
            widgets = self.dialog.get_widgets()
            self._search_features = []
            # ここでおこられてる
            self._search_group_features = OrderedDict(
                {key: [] for key in self.dialog.tab_groups.keys()}
            )
            for setting, widget in zip(settings["SearchTabs"], widgets):
                if setting["Title"] == "地番検索":
                    # 地番検索
                    feature = SearchTibanFeature(self.iface, setting, widget)
                elif setting["Title"] == "所有者検索":
                    # 所有者検索
                    feature = SearchOwnerFeature(
                        self.iface,
                        setting,
                        widget,
                        andor=" Or ",
                        page_limit=settings.get("PageLimit", 1000),
                    )
                else:
                    # 通常検索 - 複数フィールド検索ではORを標準にする
                    feature = SearchTextFeature(
                        self.iface,
                        setting,
                        widget,
                        andor=" Or ",  # 複数フィールド選択時はOR検索を標準にする
                        page_limit=settings.get("PageLimit", 1000),
                    )
                # propagate current additive mode to the feature instance so
                # SearchFeature can respect it when applying themes during search
                try:
                    setattr(feature, 'theme_additive_mode', bool(getattr(self, '_theme_additive_mode', False)))
                except Exception:
                    pass
                # groupごとの配列にする必要がある
                if self.dialog.tab_groups:
                    self._search_group_features[
                        setting.get("group", OTHER_GROUP_NAME)
                    ].append(feature)
                else:
                    self._search_features.append(feature)

            if self.dialog.tab_groups:
                self.change_tab_group(0)
                self.dialog.tabWidget.currentChanged.connect(self.change_tab_group)
            else:
                self.change_search_feature(0)
                self._current_group_widget = self.dialog.tabWidget
                self.dialog.tabWidget.currentChanged.connect(self.change_search_feature)

            # Connect search button to wrapper that ensures current_feature.widget is set to current UI
            try:
                # disconnect any previous direct connections to features
                try:
                    self.dialog.searchButton.clicked.disconnect()
                except Exception:
                    pass
                self.dialog.searchButton.clicked.connect(self._invoke_current_feature)
            except Exception:
                pass

            # If panModeComboBox exists in the dialog UI, propagate its value to features
            try:
                cmb = getattr(self.dialog, 'panModeComboBox', None)
                if cmb is not None:
                    # Map UI combo indices to internal pan mode values. Mode 3 (bbox-fit) is removed,
                    # so we skip it in the mapping to keep internal mode IDs stable.
                    index_to_mode = [0, 1, 4, 5, 6]

                    def mapped_mode(i):
                        try:
                            i = int(i)
                        except Exception:
                            i = 0
                        if 0 <= i < len(index_to_mode):
                            return index_to_mode[i]
                        return 0

                    idx = mapped_mode(cmb.currentIndex())
                    # set initial pan_mode on all features (grouped or not)
                    try:
                        for f in self._search_features:
                            setattr(f, 'pan_mode', idx)
                    except Exception:
                        pass
                    try:
                        for group, flist in self._search_group_features.items():
                            for f in flist:
                                setattr(f, 'pan_mode', idx)
                    except Exception:
                        pass

                    # If the dialog provides a scaleComboBox, propagate its value to features as `fixed_scale`.
                    try:
                        scale_cmb = getattr(self.dialog, 'scaleComboBox', None)
                        def _parse_scale_text(t):
                            try:
                                if t is None:
                                    return None
                                # support formats like '1:5,000' or '5000'
                                s = str(t)
                                if ':' in s:
                                    s = s.split(':', 1)[1]
                                s = s.replace(',', '').strip()
                                v = int(s)
                                return v
                            except Exception:
                                return None

                        if scale_cmb is not None:
                            val = _parse_scale_text(self._safe_current_text(scale_cmb))
                            # if user selected "自動(無指定)" or parsing failed, leave as None
                            try:
                                for f in self._search_features:
                                    setattr(f, 'fixed_scale', val)
                            except Exception:
                                pass
                            try:
                                for group, flist in self._search_group_features.items():
                                    for f in flist:
                                        setattr(f, 'fixed_scale', val)
                            except Exception:
                                pass

                            def _on_scale_changed(i=None):
                                try:
                                    txt = self._safe_current_text(scale_cmb)
                                    v = _parse_scale_text(txt)
                                    # If parsing failed or user selected automatic, leave as None.
                                    # Do NOT fallback to the current canvas scale here — when
                                    # fixed_scale is None, SearchFeature.zoom_features will
                                    # behave like mode==1 (center-pan, keep zoom).
                                    for f in self._search_features:
                                        setattr(f, 'fixed_scale', v)
                                    try:
                                        for group, flist in self._search_group_features.items():
                                            for f in flist:
                                                setattr(f, 'fixed_scale', v)
                                    except Exception:
                                        pass
                                except Exception:
                                    pass

                            try:
                                scale_cmb.currentIndexChanged.connect(_on_scale_changed)
                            except Exception:
                                try:
                                    scale_cmb.activated.connect(_on_scale_changed)
                                except Exception:
                                    pass
                            # also react to direct text editing (editable combo)
                            try:
                                scale_cmb.editTextChanged.connect(_on_scale_changed)
                            except Exception:
                                pass
                            # propagate 'show layer' checkbox state if present in the dialog
                            try:
                                show_cbx = getattr(self.dialog, 'showLayerCheckBox', None)
                                if show_cbx is not None:
                                    initial = bool(show_cbx.isChecked())
                                    try:
                                        for f in self._search_features:
                                            setattr(f, 'show_layer_name', initial)
                                    except Exception:
                                        pass
                                    try:
                                        for group, flist in self._search_group_features.items():
                                            for f in flist:
                                                setattr(f, 'show_layer_name', initial)
                                    except Exception:
                                        pass

                                    def _on_show_toggled(checked=False):
                                        try:
                                            for f in self._search_features:
                                                setattr(f, 'show_layer_name', bool(checked))
                                            try:
                                                for group, flist in self._search_group_features.items():
                                                    for f in flist:
                                                        setattr(f, 'show_layer_name', bool(checked))
                                            except Exception:
                                                pass
                                        except Exception:
                                            pass

                                    try:
                                        show_cbx.toggled.connect(_on_show_toggled)
                                    except Exception:
                                        try:
                                            show_cbx.stateChanged.connect(lambda s: _on_show_toggled(bool(s)))
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                            try:
                                scale_cmb.editingFinished.connect(_on_scale_changed)
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # update function when combo changes
                    def _on_pan_mode_changed(i):
                        m = mapped_mode(i)
                        try:
                            for f in self._search_features:
                                setattr(f, 'pan_mode', m)
                        except Exception:
                            pass
                        try:
                            for group, flist in self._search_group_features.items():
                                for f in flist:
                                    setattr(f, 'pan_mode', m)
                        except Exception:
                            pass

                    try:
                        cmb.currentIndexChanged.connect(_on_pan_mode_changed)
                    except Exception:
                        try:
                            cmb.activated.connect(_on_pan_mode_changed)
                        except Exception:
                            pass
            except Exception:
                pass

    def run(self, state=None, layer=None, view_fields=None):
        """検索ダイアログを表示する"""
        # メッセージ表示
        # QMessageBox.information(None, "run", "検索ダイアログ表示", QMessageBox.Yes)
        
        # 現在のレイヤの状態を確認
        try:
            active_layer = self.iface.activeLayer()
            if active_layer:
                active_layer_name = active_layer.name()
                # ログ出力
                # QMessageBox.information(None, "アクティブレイヤ", active_layer_name, QMessageBox.Yes)
        except Exception:
            pass
            
        # 現在の表示状態をテーマとして保存する
        try:
            from qgis.core import QgsProject, QgsMessageLog
            project = QgsProject.instance()
            theme_collection = project.mapThemeCollection()
            
            # シンプルなテーマ名
            theme_name = "検索前"
            
            # レイヤーツリーを取得
            root = project.layerTreeRoot()
            
            # 最初に既存の同名テーマを削除（あれば）。mapThemes() の返り値は
            # 文字列リストかテーマオブジェクトのリストか環境により異なるため
            # 安全に名前を比較する。
            try:
                raw_tm = theme_collection.mapThemes()
            except Exception:
                raw_tm = []
            exists = False
            for t in (raw_tm or []):
                try:
                    if isinstance(t, str):
                        tname = t
                    else:
                        if hasattr(t, 'name') and callable(getattr(t, 'name')):
                            tname = t.name()
                        elif hasattr(t, 'name'):
                            tname = getattr(t, 'name')
                        elif hasattr(t, 'displayName') and callable(getattr(t, 'displayName')):
                            tname = t.displayName()
                        elif hasattr(t, 'displayName'):
                            tname = getattr(t, 'displayName')
                        else:
                            tname = str(t)
                    if tname == theme_name:
                        exists = True
                        break
                except Exception:
                    continue
            if exists:
                theme_collection.removeMapTheme(theme_name)
            
            # レイヤーツリーモデルを取得してテーマを作成
            model = self.iface.layerTreeView().layerTreeModel()
            theme_state = theme_collection.createThemeFromCurrentState(root, model)
            theme_collection.insert(theme_name, theme_state)
            QgsMessageLog.logMessage(f"テーマ「{theme_name}」を保存しました", "GEO-search-plugin", 0)
            
        except Exception as e:
            from qgis.core import QgsMessageLog
            QgsMessageLog.logMessage(f"テーマ保存エラー: {str(e)}", "GEO-search-plugin", 2)
            
        self.dialog.show()

    def change_tab_group(self, index):
        if self._current_group_widget:
            self._current_group_widget.currentChanged.disconnect(
                self.change_search_feature
            )
        tab_text = self.dialog.tabWidget.tabText(index)
        self._current_group_widget = self.dialog.tab_groups[tab_text]
        self._search_features = self._search_group_features[tab_text]
        self._current_group_widget.currentChanged.connect(self.change_search_feature)
        self._current_group_widget.setCurrentIndex(0)
        self.change_search_feature(0)

    def change_search_feature(self, index):
        if self.current_feature:
            try:
                self.current_feature.unload()
            except Exception:
                pass
        if len(self._search_features) <= index:
            return
        self.current_feature = self._search_features[index]
        try:
            self.current_feature.load()
        except Exception:
            pass
        # Ensure search button enabled state follows the widget availability
        try:
            self.dialog.searchButton.setEnabled(self.current_feature.widget.isEnabled())
        except Exception:
            try:
                # fallback: enable button
                self.dialog.searchButton.setEnabled(True)
            except Exception:
                pass


    def _invoke_current_feature(self):
        """Wrapper called when search button is pressed.

        It ensures current_feature.widget points to the dialog's current page widget
        so the search reads the current UI values.
        """
        # Improved diagnostics: log invocation and internal state to help debug when
        # the search button appears to do nothing in QGIS.
        try:
            from qgis.core import QgsMessageLog
            QgsMessageLog.logMessage("_invoke_current_feature: invoked", "GEO-search-plugin", 0)
        except Exception:
            try:
                print("_invoke_current_feature: invoked")
            except Exception:
                pass

        try:
            if not hasattr(self, 'dialog') or not self.dialog:
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage("_invoke_current_feature: no dialog present", "GEO-search-plugin", 1)
                except Exception:
                    print("_invoke_current_feature: no dialog present")
                return
            # pick current visible widget from dialog
            try:
                cur = self.dialog.get_current_search_widget()
            except Exception as e:
                cur = None
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"_invoke_current_feature: get_current_search_widget error: {e}", "GEO-search-plugin", 1)
                except Exception:
                    print(f"_invoke_current_feature: get_current_search_widget error: {e}")

            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"_invoke_current_feature: current_feature={bool(self.current_feature)} cur={bool(cur)}", "GEO-search-plugin", 0)
            except Exception:
                pass

            if self.current_feature is not None and cur is not None:
                try:
                    # Set feature's widget to the current visible widget so its .search_widgets reflect current UI
                    setattr(self.current_feature, 'widget', cur)
                except Exception as e:
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"_invoke_current_feature: failed to set widget: {e}", "GEO-search-plugin", 1)
                    except Exception:
                        print(f"_invoke_current_feature: failed to set widget: {e}")

            # finally invoke feature's show_features
            if self.current_feature is not None:
                try:
                    self.current_feature.show_features()
                except Exception as e:
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"_invoke_current_feature: show_features error: {e}", "GEO-search-plugin", 2)
                    except Exception:
                        print(f"_invoke_current_feature: show_features error: {e}")
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"_invoke_current_feature: unexpected error: {e}", "GEO-search-plugin", 2)
            except Exception:
                print(f"_invoke_current_feature: unexpected error: {e}")
        
    # 以前のイベントフィルタ関連メソッドは不要になったため削除
    # activatedシグナルが同じ項目選択も検出するため、これらのメソッドは不要
    # eventFilter, force_apply_current_theme, _force_apply_themeは削除
    
    def on_project_saved(self):
        """プロジェクトが保存された時の処理"""
        try:
            # プロジェクト変数の変更を確認し、UIを更新
            self.create_search_dialog()
            
            # ダイアログが表示されていれば、再表示する
            if hasattr(self, 'dialog') and self.dialog and self.dialog.isVisible():
                self.run()
        except Exception:
            pass
