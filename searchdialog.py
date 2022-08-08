# -*- coding: utf-8 -*-
import os

from qgis.PyQt.QtWidgets import QDialog

from qgis.PyQt import uic

from .widget.searchwidget import (
    SearchTextWidget,
    SearchTibanWidget,
    SearchOwnerWidget,
)


UI_FILE = "dialog.ui"


class SearchDialog(QDialog):
    def __init__(self, setting, parent=None):
        super(SearchDialog, self).__init__(parent=parent)
        directory = os.path.join(os.path.dirname(__file__), "ui")
        ui_file = os.path.join(directory, UI_FILE)
        uic.loadUi(ui_file, self)
        self.init_gui(setting)

    def init_gui(self, setting):
        # create Page
        for tab_setting in setting["SearchTabs"]:
            page = self.create_page(tab_setting)
            self.tabWidget.addTab(page, tab_setting["Title"])

        self.set_window_title(0)
        self.tabWidget.currentChanged.connect(self.set_window_title)

    def set_window_title(self, index):
        text = self.tabWidget.tabText(index)
        self.setWindowTitle("地図検索: " + text)

    def create_page(self, setting):
        if setting["Title"] == "地番検索":
            return SearchTibanWidget(setting)
        elif setting["Title"] == "所有者検索":
            return SearchOwnerWidget(setting)
        return SearchTextWidget(setting)

    def get_widgets(self):
        return [self.tabWidget.widget(i) for i in range(self.tabWidget.count())]
