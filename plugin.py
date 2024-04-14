# -*- coding: utf-8 -*-
from ast import IsNot
from asyncio.windows_events import NULL
from collections import OrderedDict
from contextlib import nullcontext
import json
import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import (
    QgsProject,
    QgsExpressionContextUtils,
)
from PyQt5.QtWidgets import QMessageBox

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
        self.current_feature = None
        self._current_group_widget = None
        self._search_features = []
        self._search_group_features = OrderedDict()

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
        # テキストとして読込
        if (
            QgsExpressionContextUtils.projectScope(ProjectInstance).variable(
                "GEO-search-plugin"
            )
            is not None
        ):
            input_json_variable = QgsExpressionContextUtils.projectScope(
                ProjectInstance
            ).variable("GEO-search-plugin")

        # ファイルと変数を結合
        if input_json_file != "":
            input_json += input_json_file
            flag = 1
            # メッセージ表示
            # QMessageBox.information(None, "設定ファイルの読込", input_json_file , QMessageBox.Yes)
            if input_json_variable != "":
                input_json += ","
        if input_json_variable is not None:
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

            self.dialog = SearchDialog(settings, parent=self.iface.mainWindow())
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
                    # 通常検索
                    feature = SearchTextFeature(
                        self.iface,
                        setting,
                        widget,
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
