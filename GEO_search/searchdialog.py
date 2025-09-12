# -*- coding: utf-8 -*-
import os
import json
from collections import OrderedDict

from qgis.PyQt.QtWidgets import QDialog, QTabWidget, QTextEdit, QVBoxLayout, QPushButton, QHBoxLayout, QMessageBox
from qgis.PyQt.QtWidgets import QLabel, QGridLayout, QFrame, QCheckBox, QScrollArea, QWidget
from qgis.PyQt.QtCore import Qt

from qgis.PyQt import uic
from qgis.core import QgsProject

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
        self.setting = setting  # 設定を保持
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
            
        # Connect remove tab button if present
        try:
            self.removeTabButton.clicked.connect(self.remove_current_tab_from_project_variable)
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage("removeTabButton connected", "GEO-search-plugin", 0)
            except Exception:
                print("removeTabButton connected")
        except Exception:
            pass
            
        # Connect config button if present
        try:
            self.configButton.clicked.connect(self.edit_project_variable)
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage("configButton connected", "GEO-search-plugin", 0)
            except Exception:
                print("configButton connected")
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
        
        # 共通のUIリロードメソッドを呼び出し
        self.reload_ui("with new layer")
    
    def reload_ui(self, message=""):
        """UIを再読み込みするための共通メソッド"""
        try:
            # プロジェクトは自動保存せず、変数の更新のみを行う
            print(f"Updating UI without auto-saving the project: {message}")
                
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
                            print(f"UI refreshed: {message}")
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
                
    def remove_current_tab_from_project_variable(self):
        """選択されているタブを削除し、プロジェクト変数から対応する設定を削除します"""
        try:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage("remove_current_tab_from_project_variable invoked", "GEO-search-plugin", 0)
            except Exception:
                print("remove_current_tab_from_project_variable invoked")
                
            # 選択されているタブの情報を取得
            current_tab = None
            current_tab_title = None
            
            # 親タブがグループタブかどうかをチェック
            if self.tab_groups:
                # グループタブの場合、選択されているグループ内の選択されているタブを取得
                current_group_index = self.tabWidget.currentIndex()
                current_group_widget = self.tabWidget.widget(current_group_index)
                
                if isinstance(current_group_widget, QTabWidget):
                    # このグループ内の現在のタブを取得
                    tab_index = current_group_widget.currentIndex()
                    if tab_index >= 0:
                        current_tab = current_group_widget.widget(tab_index)
                        current_tab_title = current_group_widget.tabText(tab_index)
            else:
                # 通常のタブの場合、選択されているタブを取得
                tab_index = self.tabWidget.currentIndex()
                if tab_index >= 0:
                    current_tab = self.tabWidget.widget(tab_index)
                    current_tab_title = self.tabWidget.tabText(tab_index)
                    
            # タブが選択されていなければ終了
            if current_tab is None or current_tab_title is None:
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage("No tab selected or tab information could not be determined", "GEO-search-plugin", 1)
                except Exception:
                    print("No tab selected or tab information could not be determined")
                return
                
            # プロジェクト変数を取得して更新
            from qgis.core import QgsProject, QgsExpressionContextUtils
            project = QgsProject.instance()
            proj_scope = QgsExpressionContextUtils.projectScope(project)
            existing = proj_scope.variable("GEO-search-plugin")
            
            if existing is None or existing == "":
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage("No project variable exists to remove from", "GEO-search-plugin", 1)
                except Exception:
                    print("No project variable exists to remove from")
                return
                
            try:
                # JSONとして解析
                parsed = json.loads(existing)
                
                # 配列でなければ配列に変換
                if not isinstance(parsed, list):
                    parsed = [parsed]
                    
                # タブのタイトルが一致する項目を探して削除
                updated_settings = [item for item in parsed if item.get("Title") != current_tab_title]
                
                # 変更があったかチェック
                if len(updated_settings) == len(parsed):
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"Tab '{current_tab_title}' not found in project variables", "GEO-search-plugin", 1)
                    except Exception:
                        print(f"Tab '{current_tab_title}' not found in project variables")
                    return
                    
                # 更新された設定をJSONに変換（空リストの場合は空文字列に）
                if len(updated_settings) == 0:
                    new_value = ""
                else:
                    new_value = json.dumps(updated_settings, ensure_ascii=False)
                
                # プロジェクト変数を更新
                # Method 1: setProjectVariable
                try:
                    QgsExpressionContextUtils.setProjectVariable(project, 'GEO-search-plugin', new_value)
                    read_back = QgsExpressionContextUtils.projectScope(project).variable('GEO-search-plugin')
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"Updated project variable after removing tab: {str(read_back)}", "GEO-search-plugin", 0)
                    except Exception:
                        print(f"Updated project variable after removing tab: {str(read_back)}")
                except Exception as err:
                    print(f"setProjectVariable failed: {err}")
                
                # Method 2: writeEntry
                try:
                    project.writeEntry('GEO-search-plugin', 'value', new_value)
                    ok, val = project.readEntry('GEO-search-plugin', 'value')
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"Wrote via writeEntry after removing tab ok={ok} val={val}", "GEO-search-plugin", 0)
                    except Exception:
                        print(f"Wrote via writeEntry after removing tab ok={ok} val={val}")
                except Exception as err:
                    print(f"writeEntry failed: {err}")
                
                # Method 3: setCustomProperty
                try:
                    project.setCustomProperty('GEO-search-plugin', new_value)
                    pv = project.customProperty('GEO-search-plugin')
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"Set customProperty after removing tab: {str(pv)}", "GEO-search-plugin", 0)
                    except Exception:
                        print(f"Set customProperty after removing tab: {str(pv)}")
                except Exception as err:
                    print(f"setCustomProperty failed: {err}")
                    
                # 共通のUIリロードメソッドを呼び出し
                self.reload_ui("after removing tab")
                
            except Exception as e:
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"Error updating project variable: {e}", "GEO-search-plugin", 1)
                except Exception:
                    print(f"Error updating project variable: {e}")
                
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"remove_current_tab_from_project_variable error: {e}", "GEO-search-plugin", 1)
            except Exception:
                print(f"remove_current_tab_from_project_variable error: {e}")
                
    def edit_project_variable(self):
        """現在選択されているタブのレイヤー設定を編集するためのダイアログを表示します"""
        try:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage("edit_project_variable invoked", "GEO-search-plugin", 0)
            except Exception:
                print("edit_project_variable invoked")
            
            # 現在選択されているタブの情報を取得
            current_tab = None
            current_tab_title = None
            current_tab_index = -1
            
            # 親タブがグループタブかどうかをチェック
            if self.tab_groups:
                # グループタブの場合、選択されているグループ内の選択されているタブを取得
                current_group_index = self.tabWidget.currentIndex()
                current_group_widget = self.tabWidget.widget(current_group_index)
                
                if isinstance(current_group_widget, QTabWidget):
                    # このグループ内の現在のタブを取得
                    tab_index = current_group_widget.currentIndex()
                    if tab_index >= 0:
                        current_tab = current_group_widget.widget(tab_index)
                        current_tab_title = current_group_widget.tabText(tab_index)
            else:
                # 通常のタブの場合、選択されているタブを取得
                tab_index = self.tabWidget.currentIndex()
                if tab_index >= 0:
                    current_tab = self.tabWidget.widget(tab_index)
                    current_tab_title = self.tabWidget.tabText(tab_index)
                    current_tab_index = tab_index
            
            # タブが選択されていなければ終了
            if current_tab is None or current_tab_title is None:
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage("No tab selected or tab information could not be determined", "GEO-search-plugin", 1)
                except Exception:
                    print("No tab selected or tab information could not be determined")
                return
                
            # プロジェクト変数を取得
            from qgis.core import QgsProject, QgsExpressionContextUtils
            project = QgsProject.instance()
            proj_scope = QgsExpressionContextUtils.projectScope(project)
            existing = proj_scope.variable("GEO-search-plugin")
            
            if existing is None or existing == "":
                existing = "[]"  # 空の配列
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage("No existing project variable, creating empty array", "GEO-search-plugin", 0)
                except Exception:
                    print("No existing project variable, creating empty array")
            
            # 現在のタブに対応する設定を見つける
            tab_config = None
            all_configs = []
            tab_index_in_config = -1
            
            try:
                parsed = json.loads(existing)
                # 配列でなければ配列に変換
                if not isinstance(parsed, list):
                    parsed = [parsed]
                    
                all_configs = parsed
                
                # タイトルが一致する設定を探す
                for i, config in enumerate(parsed):
                    if config.get("Title") == current_tab_title:
                        tab_config = config
                        tab_index_in_config = i
                        break
                
                # 設定が見つからなければ、現在のタブに基づいて新しい設定を作成
                if tab_config is None:
                    tab_config = {
                        "Title": current_tab_title,
                        "Layer": {},
                        "SearchField": {},
                        "ViewFields": []
                    }
                    # タブに設定がある場合は取得を試みる
                    if hasattr(current_tab, "setting") and current_tab.setting:
                        try:
                            # 設定全体を取得
                            if isinstance(current_tab.setting, dict):
                                tab_config = current_tab.setting.copy()
                            else:
                                tab_config = current_tab.setting
                        except Exception as err:
                            try:
                                from qgis.core import QgsMessageLog
                                QgsMessageLog.logMessage(f"Error getting tab setting: {err}", "GEO-search-plugin", 1)
                            except Exception:
                                print(f"Error getting tab setting: {err}")
            except Exception as e:
                tab_config = {
                    "Title": current_tab_title,
                    "Layer": {},
                    "SearchField": {},
                    "ViewFields": []
                }
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"Error parsing project variable: {e}", "GEO-search-plugin", 1)
                except Exception:
                    print(f"Error parsing project variable: {e}")
            
            # 編集ダイアログを作成
            edit_dialog = QDialog(self)
            edit_dialog.setWindowTitle(f"タブ設定の編集: {current_tab_title}")
            edit_dialog.setMinimumSize(700, 600)
            
            layout = QVBoxLayout(edit_dialog)
            
            # インポート
            from qgis.PyQt.QtWidgets import QLabel, QGridLayout, QFrame
            
            # フォームレイアウトで編集可能フィールドと読み取り専用フィールドを分ける
            grid_layout = QGridLayout()
            
            # 編集可能フィールドを抽出
            editable_fields = {}
            readonly_fields = {}
            
            # グループ (group)
            if "group" in tab_config:
                editable_fields["group"] = tab_config["group"]
            else:
                editable_fields["group"] = "未設定"
                
            # タイトル (Title)
            if "Title" in tab_config:
                editable_fields["Title"] = tab_config["Title"]
            else:
                editable_fields["Title"] = current_tab_title
                
            # 検索フィールド (SearchField)
            if "SearchField" in tab_config:
                editable_fields["SearchField"] = tab_config["SearchField"]
            else:
                editable_fields["SearchField"] = {}
                
                # 表示フィールド (ViewFields) - 直接編集しない
                # ViewFields は別のダイアログで編集するため、一旦保存しておく
                if "ViewFields" in tab_config:
                    tab_config["_ViewFields"] = tab_config["ViewFields"]  # 一時的なキーに保存
                else:
                    tab_config["_ViewFields"] = []            # その他の読み取り専用フィールド
            for key, value in tab_config.items():
                if key not in ["group", "Title", "SearchField", "ViewFields"]:
                    readonly_fields[key] = value
                    
            # テキストエディタを作成
            editors = {}
            
            # 編集可能フィールドの設定
            row = 0
            for field_name, field_value in editable_fields.items():
                # ViewFields は特別処理なのでスキップ（別のボタンで編集）
                if field_name == "ViewFields":
                    continue
                    
                # ラベル
                label = QLabel(f"{field_name}:", edit_dialog)
                label.setStyleSheet("font-weight: bold;")
                grid_layout.addWidget(label, row, 0)
                
                # エディタ
                editor = QTextEdit(edit_dialog)
                editor.setFont(self.get_monospace_font())
                editor.setMinimumHeight(80)
                
                # フィールドの内容をJSONとして表示
                json_str = json.dumps(field_value, indent=2, ensure_ascii=False)
                editor.setText(json_str)
                
                grid_layout.addWidget(editor, row, 1)
                editors[field_name] = editor
                
                row += 1
                
            # ViewFields 用のボタンを追加
            view_fields_label = QLabel("ViewFields:", edit_dialog)
            view_fields_label.setStyleSheet("font-weight: bold;")
            grid_layout.addWidget(view_fields_label, row, 0)
            
            view_fields_layout = QHBoxLayout()
            
            # 現在の表示フィールドを表示
            view_fields_text = QTextEdit(edit_dialog)
            view_fields_text.setFont(self.get_monospace_font())
            view_fields_text.setReadOnly(True)
            view_fields_text.setMinimumHeight(80)
            
            # フィールド情報を取得
            view_fields_value = []
            if "_ViewFields" in tab_config and isinstance(tab_config["_ViewFields"], list):
                view_fields_value = tab_config["_ViewFields"]
            
            # テキスト表示
            json_str = json.dumps(view_fields_value, indent=2, ensure_ascii=False)
            view_fields_text.setText(json_str)
            
            view_fields_layout.addWidget(view_fields_text)
            
            # 編集ボタン
            view_fields_button = QPushButton("フィールド選択", edit_dialog)
            
            # レイヤー名を取得
            layer_name = ""
            if "Layer" in tab_config and "Name" in tab_config["Layer"]:
                layer_name = tab_config["Layer"]["Name"]
            
            # ボタンクリック時の処理
            def on_view_fields_edited(new_fields):
                view_fields_text.setText(json.dumps(new_fields, indent=2, ensure_ascii=False))
                tab_config["_ViewFields"] = new_fields  # 一時的な保存
            
            view_fields_button.clicked.connect(
                lambda: self.edit_view_fields(
                    view_fields_value, 
                    layer_name, 
                    edit_dialog, 
                    on_view_fields_edited
                )
            )
            
            view_fields_button.setMinimumWidth(100)
            view_fields_layout.addWidget(view_fields_button)
            
            grid_layout.addLayout(view_fields_layout, row, 1)
            row += 1
            
            # 読み取り専用フィールドがあれば、セクション区切りを追加
            if readonly_fields:
                separator = QFrame()
                separator.setFrameShape(QFrame.HLine)
                separator.setFrameShadow(QFrame.Sunken)
                grid_layout.addWidget(separator, row, 0, 1, 2)
                row += 1
                
                # 読み取り専用ヘッダー
                readonly_label = QLabel("以下のフィールドは読み取り専用です:", edit_dialog)
                readonly_label.setStyleSheet("font-weight: bold; color: #777777;")
                grid_layout.addWidget(readonly_label, row, 0, 1, 2)
                row += 1
                
                # 読み取り専用フィールドの表示
                for field_name, field_value in readonly_fields.items():
                    # ラベル
                    label = QLabel(f"{field_name}:", edit_dialog)
                    label.setStyleSheet("color: #777777;")
                    grid_layout.addWidget(label, row, 0)
                    
                    # 表示のみのエディタ
                    editor = QTextEdit(edit_dialog)
                    editor.setFont(self.get_monospace_font())
                    editor.setReadOnly(True)
                    editor.setStyleSheet("background-color: #f0f0f0;")
                    editor.setMinimumHeight(60)
                    editor.setMaximumHeight(80)
                    
                    # フィールドの内容をJSONとして表示
                    json_str = json.dumps(field_value, indent=2, ensure_ascii=False)
                    editor.setText(json_str)
                    
                    grid_layout.addWidget(editor, row, 1)
                    
                    row += 1
            
            layout.addLayout(grid_layout)
            
            # ボタン配置
            button_layout = QHBoxLayout()
            
            # 保存ボタン
            save_button = QPushButton("保存", edit_dialog)
            save_button.clicked.connect(lambda: self.save_tab_config_by_fields(
                editors,
                readonly_fields,
                edit_dialog, 
                all_configs, 
                tab_index_in_config, 
                current_tab_title
            ))
            button_layout.addWidget(save_button)
            
            # キャンセルボタン
            cancel_button = QPushButton("キャンセル", edit_dialog)
            cancel_button.clicked.connect(edit_dialog.reject)
            button_layout.addWidget(cancel_button)
            
            layout.addLayout(button_layout)
            
            # ダイアログを表示
            edit_dialog.exec_()
            
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"edit_project_variable error: {e}", "GEO-search-plugin", 1)
            except Exception:
                print(f"edit_project_variable error: {e}")
    
    def get_monospace_font(self):
        """等幅フォントを取得"""
        try:
            from qgis.PyQt.QtGui import QFont
            font = QFont("Courier New")
            font.setStyleHint(QFont.Monospace)
            font.setPointSize(10)
            return font
        except Exception:
            return None
    
    def edit_view_fields(self, current_fields, layer_name, dialog, callback):
        """ViewFieldsを編集するためのダイアログを表示する"""
        try:
            # レイヤーを取得
            layer = None
            project = QgsProject.instance()
            
            # レイヤー名でレイヤーを検索
            for lyr in project.mapLayers().values():
                if lyr.name() == layer_name:
                    layer = lyr
                    break
            
            # レイヤーの属性を取得
            available_fields = []
            if layer:
                for field in layer.fields():
                    available_fields.append(field.name())
            else:
                # レイヤーが見つからない場合、現在のフィールドを使用
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"レイヤー '{layer_name}' が見つかりません。現在のフィールドを使用します。", "GEO-search-plugin", 1)
                except Exception:
                    print(f"レイヤー '{layer_name}' が見つかりません。現在のフィールドを使用します。")
                
                # 現在のフィールドが空でない場合は使用
                if isinstance(current_fields, list) and current_fields:
                    available_fields = [field for field in current_fields]
            
            # ダイアログを作成
            fields_dialog = QDialog(dialog)
            fields_dialog.setWindowTitle(f"表示フィールドの選択: {layer_name}")
            fields_dialog.setMinimumSize(400, 300)
            
            layout = QVBoxLayout(fields_dialog)
            
            # 説明ラベル
            info_label = QLabel("表示するフィールドを選択してください:", fields_dialog)
            layout.addWidget(info_label)
            
            # スクロールエリア
            scroll_area = QScrollArea(fields_dialog)
            scroll_area.setWidgetResizable(True)
            scroll_content = QWidget(scroll_area)
            scroll_layout = QVBoxLayout(scroll_content)
            
            # チェックボックス
            checkboxes = {}
            for field_name in available_fields:
                checkbox = QCheckBox(field_name, scroll_content)
                # 現在選択されているフィールドはチェックを入れる
                if isinstance(current_fields, list) and field_name in current_fields:
                    checkbox.setChecked(True)
                scroll_layout.addWidget(checkbox)
                checkboxes[field_name] = checkbox
            
            # 空きスペースを追加
            scroll_layout.addStretch(1)
            
            scroll_content.setLayout(scroll_layout)
            scroll_area.setWidget(scroll_content)
            layout.addWidget(scroll_area)
            
            # ボタン配置
            button_layout = QHBoxLayout()
            
            # 保存ボタン
            save_button = QPushButton("保存", fields_dialog)
            save_button.clicked.connect(lambda: self._save_view_fields(checkboxes, fields_dialog, callback))
            button_layout.addWidget(save_button)
            
            # キャンセルボタン
            cancel_button = QPushButton("キャンセル", fields_dialog)
            cancel_button.clicked.connect(fields_dialog.reject)
            button_layout.addWidget(cancel_button)
            
            layout.addLayout(button_layout)
            
            # ダイアログを表示
            fields_dialog.exec_()
            
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"edit_view_fields error: {e}", "GEO-search-plugin", 1)
            except Exception:
                print(f"edit_view_fields error: {e}")
            QMessageBox.warning(dialog, "エラー", f"表示フィールドの編集中にエラーが発生しました:\n{str(e)}")
    
    def _save_view_fields(self, checkboxes, dialog, callback):
        """チェックされたフィールドを保存する"""
        try:
            # チェックされているフィールドのリストを作成
            selected_fields = []
            for field_name, checkbox in checkboxes.items():
                if checkbox.isChecked():
                    selected_fields.append(field_name)
            
            # コールバック関数を呼び出して結果を返す
            callback(selected_fields)
            
            # ダイアログを閉じる
            dialog.accept()
            
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"_save_view_fields error: {e}", "GEO-search-plugin", 1)
            except Exception:
                print(f"_save_view_fields error: {e}")
            QMessageBox.warning(dialog, "エラー", f"表示フィールドの保存中にエラーが発生しました:\n{str(e)}")
                
    def save_tab_config_by_fields(self, editors, readonly_fields, dialog, all_configs, tab_index, tab_title):
        """各フィールドエディタから値を取得してタブ設定を保存"""
        try:
            # 新しい設定を構築
            tab_config = {}
            
            # 読み取り専用フィールドをコピー
            for field_name, field_value in readonly_fields.items():
                tab_config[field_name] = field_value
            
            # 編集可能フィールドを処理
            error_messages = []
            for field_name, editor in editors.items():
                text = editor.toPlainText()
                try:
                    # JSONとして解析
                    field_value = json.loads(text)
                    tab_config[field_name] = field_value
                except Exception as e:
                    error_messages.append(f"フィールド '{field_name}' のJSONエラー: {str(e)}")
            
            # エラーがあれば表示して終了
            if error_messages:
                QMessageBox.warning(self, "JSONエラー", "\n".join(error_messages))
                return
                
            # タイトルを確認
            if "Title" in tab_config and tab_config["Title"] != tab_title:
                # 警告を表示してタイトルを修正
                QMessageBox.information(self, "タイトルの調整", 
                    f"タイトルは自動的に '{tab_title}' に設定されます。タブ名を変更するには、新しいタブを作成してください。")
                tab_config["Title"] = tab_title
                
            # _ViewFieldsからViewFieldsに値を移し替え
            if "_ViewFields" in readonly_fields:
                tab_config["ViewFields"] = readonly_fields["_ViewFields"]
            
            # 設定を保存
            self._update_config_and_save(tab_config, dialog, all_configs, tab_index)
            
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"save_tab_config_by_fields error: {e}", "GEO-search-plugin", 1)
            except Exception:
                print(f"save_tab_config_by_fields error: {e}")
            QMessageBox.warning(self, "エラー", f"タブ設定の保存中にエラーが発生しました:\n{str(e)}")
    
    def save_tab_config(self, text, dialog, all_configs, tab_index, tab_title):
        """タブの設定を保存（単一テキストエディタから）"""
        try:
            # JSONとして解析できるかチェック
            try:
                tab_config = json.loads(text)
                
                # タブ名を一貫させるために、タイトルを現在のタブ名に設定
                if "Title" in tab_config and tab_config["Title"] != tab_title:
                    tab_config["Title"] = tab_title
                    
            except Exception as e:
                QMessageBox.warning(self, "JSONエラー", f"入力されたテキストはJSONとして有効ではありません:\n{str(e)}")
                return
                
            # 設定の更新と保存の共通処理を呼び出し
            self._update_config_and_save(tab_config, dialog, all_configs, tab_index)
                
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"タブ設定の保存中にエラーが発生しました:\n{str(e)}")
            
    def _update_config_and_save(self, tab_config, dialog, all_configs, tab_index):
        """設定を更新し、プロジェクト変数に保存する共通処理"""
        try:
            # 設定の処理を開始
            # プロジェクト変数を更新
            from qgis.core import QgsProject, QgsExpressionContextUtils
            project = QgsProject.instance()
            
            # 設定を更新または追加
            if tab_index >= 0 and tab_index < len(all_configs):
                # 既存の設定を更新
                all_configs[tab_index] = tab_config
            else:
                # 新しい設定を追加
                all_configs.append(tab_config)
                
            # JSONを文字列に変換
            new_value = json.dumps(all_configs, ensure_ascii=False)
            
            # 変数を更新 (複数の方法で試行)
            # Method 1: setProjectVariable
            try:
                QgsExpressionContextUtils.setProjectVariable(project, 'GEO-search-plugin', new_value)
                read_back = QgsExpressionContextUtils.projectScope(project).variable('GEO-search-plugin')
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"Updated project variable: {str(read_back)}", "GEO-search-plugin", 0)
                except Exception:
                    print(f"Updated project variable: {str(read_back)}")
            except Exception as err:
                print(f"setProjectVariable failed: {err}")
            
            # Method 2: writeEntry
            try:
                project.writeEntry('GEO-search-plugin', 'value', new_value)
                ok, val = project.readEntry('GEO-search-plugin', 'value')
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"Wrote via writeEntry ok={ok} val={val}", "GEO-search-plugin", 0)
                except Exception:
                    print(f"Wrote via writeEntry ok={ok} val={val}")
            except Exception as err:
                print(f"writeEntry failed: {err}")
            
            # Method 3: setCustomProperty
            try:
                project.setCustomProperty('GEO-search-plugin', new_value)
                pv = project.customProperty('GEO-search-plugin')
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"Set customProperty: {str(pv)}", "GEO-search-plugin", 0)
                except Exception:
                    print(f"Set customProperty: {str(pv)}")
            except Exception as err:
                print(f"setCustomProperty failed: {err}")
                
            # ダイアログを閉じる
            dialog.accept()
            
            # UI再読み込み
            self.reload_ui("after editing tab configuration")
            
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"_update_config_and_save error: {e}", "GEO-search-plugin", 1)
            except Exception:
                print(f"_update_config_and_save error: {e}")
            QMessageBox.warning(dialog, "エラー", f"設定の保存中にエラーが発生しました:\n{str(e)}")
            
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"save_tab_config error: {e}", "GEO-search-plugin", 1)
            except Exception:
                print(f"save_tab_config error: {e}")
            QMessageBox.warning(self, "エラー", f"タブ設定の保存中にエラーが発生しました:\n{str(e)}")
    
    def save_project_variable(self, text, dialog):
        """プロジェクト変数を保存（古いメソッド - 互換性のために残しています）"""
        try:
            # JSONとして解析できるかチェック
            try:
                json_data = json.loads(text)
                # 配列でなければ配列に変換
                if not isinstance(json_data, list):
                    json_data = [json_data]
            except Exception as e:
                QMessageBox.warning(self, "JSONエラー", f"入力されたテキストはJSONとして有効ではありません:\n{str(e)}")
                return
                
            # プロジェクト変数を更新
            from qgis.core import QgsProject, QgsExpressionContextUtils
            project = QgsProject.instance()
            
            # JSONを文字列に変換
            new_value = json.dumps(json_data, ensure_ascii=False)
            
            # 変数を更新 (複数の方法で試行)
            # Method 1: setProjectVariable
            try:
                QgsExpressionContextUtils.setProjectVariable(project, 'GEO-search-plugin', new_value)
                read_back = QgsExpressionContextUtils.projectScope(project).variable('GEO-search-plugin')
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"Updated project variable: {str(read_back)}", "GEO-search-plugin", 0)
                except Exception:
                    print(f"Updated project variable: {str(read_back)}")
            except Exception as err:
                print(f"setProjectVariable failed: {err}")
            
            # Method 2: writeEntry
            try:
                project.writeEntry('GEO-search-plugin', 'value', new_value)
                ok, val = project.readEntry('GEO-search-plugin', 'value')
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"Wrote via writeEntry ok={ok} val={val}", "GEO-search-plugin", 0)
                except Exception:
                    print(f"Wrote via writeEntry ok={ok} val={val}")
            except Exception as err:
                print(f"writeEntry failed: {err}")
            
            # Method 3: setCustomProperty
            try:
                project.setCustomProperty('GEO-search-plugin', new_value)
                pv = project.customProperty('GEO-search-plugin')
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"Set customProperty: {str(pv)}", "GEO-search-plugin", 0)
                except Exception:
                    print(f"Set customProperty: {str(pv)}")
            except Exception as err:
                print(f"setCustomProperty failed: {err}")
                
            # ダイアログを閉じる
            dialog.accept()
            
            # UI再読み込み
            self.reload_ui("after editing project variable")
            
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"save_project_variable error: {e}", "GEO-search-plugin", 1)
            except Exception:
                print(f"save_project_variable error: {e}")
            QMessageBox.warning(self, "エラー", f"プロジェクト変数の保存中にエラーが発生しました:\n{str(e)}")
