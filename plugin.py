# -*- coding: utf-8 -*-
from ast import IsNot
from asyncio.windows_events import NULL
from contextlib import nullcontext
import json
import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsVectorLayer, Qgis, QgsProject, QgsWkbTypes, QgsMapLayer, QgsFields, QgsExpressionContextUtils
from PyQt5.QtWidgets import QMessageBox

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

    def initGui(self):
        #起動時に動作
        #メッセージ表示
        #QMessageBox.information(None, "iniGui", "Gui構築", QMessageBox.Yes)
        icon_path = os.path.join(os.path.dirname(__file__), u"icon/qgis-icon.png")
        self.action = QAction(QIcon(icon_path), "地図検索", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.projectRead.connect(self.create_search_dialog)

        self.create_search_dialog()

    def unload(self):
        self.iface.removeToolBarIcon(self.action)

    def create_search_dialog(self):
        self.current_feature = None
        #ファイルからjsonを読み込む
        setting_path = os.path.join(os.path.dirname(__file__), "setting.json")
        with open(setting_path) as f:
        #ファイルオブジェクトをJSONとして読込
            settings = json.load(f)

        # jsonファイルの追加設定
        # プロジェクト変数から追加読み込み
        # 変数名 GEO-search-plugin
        # 変数
        ProjectInstance = QgsProject.instance()
        #文字列をJSONとして読込
        #変数の有無を確認
        GEO_search_plugin_variable = QgsExpressionContextUtils.projectScope(ProjectInstance).variable('GEO-search-plugin')
        if GEO_search_plugin_variable is not None :
            #メッセージ表示
            #QMessageBox.information(None, "create_search_dialog", GEO_search_plugin_variable , QMessageBox.Yes) 
            settings = json.loads(QgsExpressionContextUtils.projectScope(ProjectInstance).variable('GEO-search-plugin')) 
             
            
        #メッセージ表示
        #QMessageBox.information(None, "create_search_dialog", "JSON読込", QMessageBox.Yes)
            
        self.dialog = SearchDialog(settings, parent=self.iface.mainWindow())
        widgets = self.dialog.get_widgets()
        self.search_features = []
        for setting, widget in zip(settings["SearchTabs"], widgets):
            if setting["Title"] == "地番検索":
                feature = SearchTibanFeature(self.iface, setting, widget)
            elif setting["Title"] == "所有者検索":
                feature = SearchOwnerFeature(
                    self.iface,
                    setting,
                    widget,
                    andor=" Or ",
                    page_limit=settings.get("PageLimit", 1000),
                )
            else:
                feature = SearchTextFeature(
                    self.iface,
                    setting,
                    widget,
                    page_limit=settings.get("PageLimit", 1000),
                )
            self.search_features.append(feature)
        self.change_sesarch_feature(0)
        self.dialog.tabWidget.currentChanged.connect(self.change_sesarch_feature)

    def run(self, state=None, layer=None, view_fields=None):
        """ 検索ダイアログを表示する """
        self.dialog.show()

    def change_sesarch_feature(self, index):
        if self.current_feature:
            self.current_feature.unload()
            self.dialog.searchButton.clicked.disconnect(
                self.current_feature.show_features
            )

        self.current_feature = self.search_features[index]
        self.current_feature.load()
        self.dialog.searchButton.clicked.connect(self.current_feature.show_features)
        self.dialog.searchButton.setEnabled(self.current_feature.widget.isEnabled())
