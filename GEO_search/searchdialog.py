# -*- coding: utf-8 -*-
import os
import json
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
    def __init__(self, setting, parent=None, iface=None):
        super(SearchDialog, self).__init__(parent=parent)
        self.iface = iface
        directory = os.path.join(os.path.dirname(__file__), "ui")
        ui_file = os.path.join(directory, UI_FILE)
        uic.loadUi(ui_file, self)
        self.init_gui(setting)
        # Connect add layer button if present
        try:
            self.addLayerButton.clicked.connect(self.add_current_layer_to_project_variable)
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage("addLayerButton connected", "GEO-search-plugin", 0)
            except Exception:
                print("addLayerButton connected")
        except Exception:
            pass

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

    def add_current_layer_to_project_variable(self):
        try:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage("add_current_layer_to_project_variable invoked", "GEO-search-plugin", 0)
            except Exception:
                print("add_current_layer_to_project_variable invoked")
            from qgis.core import QgsProject, QgsExpressionContextUtils
            project = QgsProject.instance()
            # Resolve iface: prefer dialog's iface, fallback to parent().iface
            iface = getattr(self, 'iface', None)
            if iface is None and hasattr(self.parent(), 'iface'):
                iface = self.parent().iface

            current_layer = None
            try:
                if iface is not None:
                    current_layer = iface.activeLayer()
            except Exception:
                current_layer = None

            if current_layer is None:
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage("add_current_layer: no active layer found", "GEO-search-plugin", 1)
                except Exception:
                    print("add_current_layer: no active layer found")
                return

            layer_name = current_layer.name() if hasattr(current_layer, 'name') else str(current_layer)

            # Build a standard JSON structure for searching this layer
            standard_json = {
                "Title": layer_name,
                "Layer": {
                    "LayerType": "Name",
                    "Name": layer_name
                },
                # default search options
                "Search": {
                    "Fields": [],
                    "FullText": False,
                    "CaseSensitive": False,
                    "MatchType": "contains"
                }
            }

            # Log the JSON to QGIS message log for inspection
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"Add current layer JSON: {json.dumps(standard_json, ensure_ascii=False)}", "GEO-search-plugin", 0)
            except Exception:
                # best-effort: if QgsMessageLog not available, print
                try:
                    print(json.dumps(standard_json, ensure_ascii=False))
                except Exception:
                    pass

            # read existing variable
            proj_scope = QgsExpressionContextUtils.projectScope(project)
            existing = proj_scope.variable("GEO-search-plugin")
            # existing is expected to be a JSON fragment (e.g., array element), try to merge
            try:
                if existing is None or existing == "":
                    new_value = json.dumps([standard_json], ensure_ascii=False)
                else:
                    # try to parse existing as JSON array; if not array, wrap
                    parsed = json.loads(existing)
                    if isinstance(parsed, list):
                        parsed.append(standard_json)
                        new_value = json.dumps(parsed, ensure_ascii=False)
                    else:
                        new_value = json.dumps([parsed, standard_json], ensure_ascii=False)
            except Exception:
                # fallback: set as single-item array string
                new_value = json.dumps([standard_json], ensure_ascii=False)

            # write back into project variables: try writeEntry, then setCustomProperty
            try:
                project.writeEntry('GEO-search-plugin', 'value', new_value)
            except Exception:
                try:
                    project.setCustomProperty("GEO-search-plugin", new_value)
                except Exception:
                    pass
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"add_current_layer_to_project_variable error: {e}", "GEO-search-plugin", 1)
            except Exception:
                print(f"add_current_layer_to_project_variable error: {e}")
