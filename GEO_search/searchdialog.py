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
            
            # 親のプラグインインスタンスがある場合、current_layersリストを更新
            try:
                parent = self.parent()
                if hasattr(parent, "current_layers"):
                    # レイヤ情報がある場合、追跡リストに追加
                    if "Layer" in tab_setting and "Name" in tab_setting["Layer"]:
                        layer_name = tab_setting["Layer"]["Name"]
                        if layer_name not in parent.current_layers:
                            parent.current_layers.append(layer_name)
            except Exception:
                pass

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

            # Build a standard JSON structure matching plugin setting schema
            # Provide an "All" SearchField so the UI has a valid input widget,
            # and include ViewFields from the layer field names so result table can render.
            # Build a simple JSON matching README sample
            # Create simple JSON that triggers an all-field search.
            # Setting "SearchField" to an empty dict {} will be interpreted
            # by the widget as the All-field and cause full-text search logic to run.
            standard_json = {
                "group": "ﾌﾟﾛｼﾞｪｸﾄ検索",
                "Title": layer_name,
                "Layer": {"LayerType": "Name", "Name": layer_name},
                # empty dict -> SearchWidget will create the All field
                "SearchField": {},
                "ViewFields": []
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
                    merged = [standard_json]
                    # log merged
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"Merging: existing empty -> merged={json.dumps(merged, ensure_ascii=False)}", "GEO-search-plugin", 0)
                    except Exception:
                        print("Merging: existing empty -> merged=", json.dumps(merged, ensure_ascii=False))
                    new_value = json.dumps(merged, ensure_ascii=False)
                else:
                    # try to parse existing as JSON; coerce non-list to list then append
                    parsed = json.loads(existing)
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"Parsed existing value: {json.dumps(parsed, ensure_ascii=False)}", "GEO-search-plugin", 0)
                    except Exception:
                        print("Parsed existing value:", parsed)

                    if isinstance(parsed, list):
                        parsed.append(standard_json)
                        merged = parsed
                    else:
                        merged = [parsed, standard_json]

                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"Merged JSON to write: {json.dumps(merged, ensure_ascii=False)}", "GEO-search-plugin", 0)
                    except Exception:
                        print("Merged JSON to write:", json.dumps(merged, ensure_ascii=False))

                    new_value = json.dumps(merged, ensure_ascii=False)
            except Exception as e:
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"Error while merging existing project variable: {e}", "GEO-search-plugin", 1)
                except Exception:
                    print(f"Error while merging existing project variable: {e}")
                # fallback: set as single-item array string
                new_value = json.dumps([standard_json], ensure_ascii=False)

            # write back into project variables: try all available methods for maximum compatibility
            wrote = False
            try:
                # Prefer API to set project variable so it appears in Project→Properties→Variables
                from qgis.core import QgsExpressionContextUtils, QgsMessageLog
                
                # Method 1: setProjectVariable
                try:
                    QgsExpressionContextUtils.setProjectVariable(project, 'GEO-search-plugin', new_value)
                    wrote = True
                    read_back = QgsExpressionContextUtils.projectScope(project).variable('GEO-search-plugin')
                    QgsMessageLog.logMessage(f"Set project variable (project scope): {str(read_back)}", "GEO-search-plugin", 0)
                    print(f"Set project variable via setProjectVariable: {str(read_back)}")
                except Exception as err:
                    print(f"setProjectVariable failed: {err}")
                
                # Method 2: writeEntry - always try this too
                try:
                    project.writeEntry('GEO-search-plugin', 'value', new_value)
                    wrote = True
                    ok, val = project.readEntry('GEO-search-plugin', 'value')
                    QgsMessageLog.logMessage(f"Wrote via writeEntry ok={ok} val={val}", "GEO-search-plugin", 0)
                    print(f"Wrote via writeEntry ok={ok} val={val}")
                except Exception as err:
                    print(f"writeEntry failed: {err}")
                
                # Method 3: setCustomProperty - always try this too
                try:
                    project.setCustomProperty('GEO-search-plugin', new_value)
                    pv = project.customProperty('GEO-search-plugin')
                    QgsMessageLog.logMessage(f"Set customProperty: {str(pv)}", "GEO-search-plugin", 0)
                    print(f"Set customProperty: {str(pv)}")
                except Exception as err:
                    print(f"setCustomProperty failed: {err}")
                    
                # プロジェクトの自動保存は行わない（ユーザーが必要なときに保存する）
                print("Project variable updated, but project not auto-saved")
            except Exception:
                try:
                    # best-effort: try the old writeEntry then customProperty
                    project.writeEntry('GEO-search-plugin', 'value', new_value)
                    try:
                        from qgis.core import QgsMessageLog
                        ok, val = project.readEntry('GEO-search-plugin', 'value')
                        QgsMessageLog.logMessage(f"Wrote via writeEntry ok={ok} val={val}", "GEO-search-plugin", 0)
                    except Exception:
                        print("Wrote via writeEntry (fallback)")
                except Exception:
                    try:
                        project.setCustomProperty('GEO-search-plugin', new_value)
                        try:
                            from qgis.core import QgsMessageLog
                            pv = project.customProperty('GEO-search-plugin')
                            QgsMessageLog.logMessage(f"Set customProperty (fallback): {str(pv)}", "GEO-search-plugin", 0)
                        except Exception:
                            print('Set customProperty (fallback)')
                    except Exception:
                        pass
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"add_current_layer_to_project_variable error: {e}", "GEO-search-plugin", 1)
            except Exception:
                print(f"add_current_layer_to_project_variable error: {e}")
        
        # プラグインの再初期化を呼び出して、UIを更新する
        try:
            # プロジェクトは自動保存せず、変数の更新のみを行う
            print("Updating UI without auto-saving the project")
                
            # QGISに変更を反映させるための遅延処理を設定
            try:
                from qgis.PyQt.QtCore import QTimer
                from functools import partial
                
                def find_plugin_instance():
                    """プラグインインスタンスを複数の方法で探す"""
                    parent_plugin = None
                    
                    # 方法1: 直接の親を調べる
                    try:
                        parent_plugin = self.parent()
                        if parent_plugin and hasattr(parent_plugin, 'create_search_dialog'):
                            print("Found plugin via direct parent")
                            return parent_plugin
                    except Exception:
                        pass
                        
                    # 方法2: iface経由で探す（可能な場合）
                    try:
                        if hasattr(self, 'iface') and self.iface:
                            from qgis.utils import plugins
                            for plugin_name, plugin_obj in plugins.items():
                                if hasattr(plugin_obj, 'create_search_dialog'):
                                    print(f"Found plugin via plugins dict: {plugin_name}")
                                    return plugin_obj
                    except Exception:
                        pass
                        
                    return None
                
                def reload_plugin_ui():
                    try:
                        # プラグインインスタンスを取得
                        plugin_instance = find_plugin_instance()
                        
                        if plugin_instance:
                            # 現在のダイアログを閉じる
                            self.close()
                            # プラグインの検索ダイアログを再構築
                            plugin_instance.create_search_dialog()
                            # 再表示
                            plugin_instance.run()
                            print("UI refreshed with new layer")
                        else:
                            # プラグインインスタンスが見つからない場合
                            print("Could not find plugin instance, closing dialog only")
                            self.close()
                    except Exception as err:
                        print(f"Failed in reload_plugin_ui: {err}")
                
                # より長い遅延を設定（QGISが変数を更新する時間を確保）
                QTimer.singleShot(500, reload_plugin_ui)
                
            except Exception as e:
                print(f"Failed to set up timer: {e}")
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"Failed to refresh UI: {e}", "GEO-search-plugin", 2)
            except Exception:
                print(f"Failed to refresh UI: {e}")
