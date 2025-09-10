# -*- coding: utf-8 -*-
import os
from collections import OrderedDict

from qgis.PyQt.QtWidgets import QDialog, QTabWidget

from qgis.PyQt import uic

from .widget.searchwidget import (
    SearchTextWidget,
    SearchTibanWidget,
    SearchOwnerWidget,
)
from .constants import OTHER_GROUP_NAME


UI_FILE = "dialog.ui"


class SearchDialog(QDialog):
    def __init__(self, setting, parent=None):
        super(SearchDialog, self).__init__(parent=parent)
        directory = os.path.join(os.path.dirname(__file__), "ui")
        ui_file = os.path.join(directory, UI_FILE)
        uic.loadUi(ui_file, self)
        self.init_gui(setting)

    def init_gui(self, setting):
        self.tab_groups = self.create_tab_groups(setting["SearchTabs"])
        # create Page
        for tab_setting in setting["SearchTabs"]:
            page = self.create_page(tab_setting)
            if self.tab_groups:
                tab_group_widget = self.tab_groups[
                    tab_setting.get("group", OTHER_GROUP_NAME)
                ]
                tab_group_widget.addTab(page, tab_setting["Title"])
            else:
                self.tabWidget.addTab(page, tab_setting["Title"])

        self.set_window_title(0)
        self.tabWidget.currentChanged.connect(self.set_window_title)

    def set_window_title(self, index):
        text = self.tabWidget.tabText(index)
        self.setWindowTitle("地図検索: " + text)

    def create_page(self, setting):
        if setting["Title"] == "地番検索":
            return SearchTibanWidget(setting)
        if setting["Title"] == "所有者検索":
            return SearchOwnerWidget(setting)
        return SearchTextWidget(setting)

    def create_tab_groups(self, search_tabs):
        tab_groups = OrderedDict()
        for search_tab in search_tabs:
            group_name = search_tab.get("group", OTHER_GROUP_NAME)
            if group_name not in tab_groups:
                group_widget = QTabWidget()
                tab_groups[group_name] = group_widget
        if len(tab_groups) <= 1 and OTHER_GROUP_NAME in tab_groups:
            return {}
        for group_name, group_widget in tab_groups.items():
            self.tabWidget.addTab(group_widget, group_name)
        return tab_groups

    def get_widgets(self):
        if self.tab_groups:
            return [
                group_widget.widget(i)
                for group_widget in self.tab_groups.values()
                for i in range(group_widget.count())
            ]
        return [self.tabWidget.widget(i) for i in range(self.tabWidget.count())]
