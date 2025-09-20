# -*- coding: utf-8 -*-
from ast import IsNot
from asyncio.windows_events import NULL
from collections import OrderedDict
from contextlib import nullcontext
import json
import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
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

# TODO: Fieldの確認
# TODO: 表示テーブルの順番変更


class plugin(object):
    def __init__(self, iface):
        self.iface = iface
        self._init_language()
        self.current_feature = None
        self._current_group_widget = None
        self._search_features = []
        self._search_group_features = OrderedDict()
        self.current_layers = []  # 追加されたレイヤを管理するリスト

    def _init_language(self):
        """QGISとプラグインの言語設定を自動化"""
        try:
            from qgis.PyQt.QtCore import QSettings, QLocale, QTranslator
            from qgis.PyQt.QtWidgets import QApplication
            import os
            # QGISの設定から言語取得（なければOSのロケール）
            settings = QSettings()
            lang = settings.value('locale/userLocale', QLocale.system().name())
            if lang:
                settings.setValue('locale/userLocale', lang)
            # プラグインの翻訳ファイルをロード
            translator = QTranslator()
            qm_path = os.path.join(os.path.dirname(__file__), 'i18n', f'{lang}.qm')
            if os.path.exists(qm_path):
                translator.load(qm_path)
                QApplication.instance().installTranslator(translator)
        except Exception as e:
            pass  # エラーは無視（QGIS外実行時など）

    def initGui(self):
        # プラグイン開始時に動作
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

        # トリガー構築
        self.action.triggered.connect(self.run)
        self.iface.projectRead.connect(self.create_search_dialog)
        
        # プロジェクト変数の変更を検知するために追加のイベント接続
        try:
            QgsProject.instance().projectSaved.connect(self.on_project_saved)
        except Exception:
            pass

    def unload(self):
        # プラグイン終了時に動作
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu("地図検索", self.action)

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
            # デバッグ出力
            print(f"Found variable from projectScope: {ctx_var}")
        else:
            # fallback: try readEntry / custom property
            try:
                ok, val = ProjectInstance.readEntry('GEO-search-plugin', 'value')
                if ok:
                    input_json_variable = val
                    print(f"Found variable from readEntry: {val}")
            except Exception:
                try:
                    pv = ProjectInstance.customProperty('GEO-search-plugin')
                    if pv is not None:
                        input_json_variable = pv
                        print(f"Found variable from customProperty: {pv}")
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
            
            # 最初に既存の同名テーマを削除（あれば）
            if theme_name in theme_collection.mapThemes():
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
            self.current_feature.unload()
            self.dialog.searchButton.clicked.disconnect(
                self.current_feature.show_features
            )
        if len(self._search_features) <= index:
            return
        self.current_feature = self._search_features[index]
        self.current_feature.load()
        self.dialog.searchButton.clicked.connect(self.current_feature.show_features)
        self.dialog.searchButton.setEnabled(self.current_feature.widget.isEnabled())
        
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
