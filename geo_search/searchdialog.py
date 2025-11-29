# -*- coding: utf-8 -*-
import os
import json
import shutil
import tempfile
import datetime
from collections import OrderedDict

from qgis.PyQt.QtWidgets import QDialog, QTabWidget, QTextEdit, QVBoxLayout, QPushButton, QHBoxLayout, QMessageBox
from qgis.PyQt.QtWidgets import QLabel, QGridLayout, QFrame, QCheckBox, QScrollArea, QWidget, QButtonGroup, QRadioButton
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

from .utils import set_project_variable, remove_entry_from_json_file


class SearchDialog(QDialog):
    def __init__(self, setting, parent=None, iface=None):
        super(SearchDialog, self).__init__(parent=parent)
        self.iface = iface
        self.setting = setting  # 設定を保持
        directory = os.path.join(os.path.dirname(__file__), "ui")
        ui_file = os.path.join(directory, UI_FILE)
        uic.loadUi(ui_file, self)
    # Note: ID-based mapping removed. Matching will use Title+group heuristics.
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

        # Post-initialization: attempt to stabilize layout and table sizing.
        # Some Qt6 style/backends may delay layout calculations; calling
        # adjustSize()/updateGeometry() and resizing table columns helps avoid
        # zero-width header / invisible children that were observed on some
        # systems. This is defensive and wrapped in try/except to be safe.
        try:
            # ensure top-level layout is recalculated
            try:
                self.adjustSize()
            except Exception:
                pass

            from qgis.PyQt.QtWidgets import QWidget, QTableWidget
            # update geometry for all child widgets
            for w in self.findChildren(QWidget):
                try:
                    # keep widgets hidden state as-is; just nudge geometry
                    w.updateGeometry()
                    w.repaint()
                except Exception:
                    pass

            # resize any tables to contents so headers don't collapse to zero
            for t in self.findChildren(QTableWidget):
                try:
                    t.resizeColumnsToContents()
                    t.resizeRowsToContents()
                    t.repaint()
                except Exception:
                    pass
        except Exception:
            # swallow any errors - this is purely best-effort
            pass

    def init_gui(self, setting):
        self.tab_groups = self.create_tab_groups(setting["SearchTabs"])
        # create Page
        for i, tab_setting in enumerate(setting["SearchTabs"]):
            page = self.create_page(tab_setting)
            # Tab title: use configured Title only (source marker shown under angle display)
            display_title = tab_setting.get("Title") if isinstance(tab_setting, dict) else str(tab_setting)

            # Do not use per-tab "id" mapping. Rely on Title and group for matching.
            if self.tab_groups:
                group_name = tab_setting.get("group", OTHER_GROUP_NAME) if isinstance(tab_setting, dict) else OTHER_GROUP_NAME
                tab_group_widget = self.tab_groups[group_name]
                tab_index = tab_group_widget.addTab(page, self.tr(display_title))
            else:
                tab_index = self.tabWidget.addTab(page, self.tr(display_title))
            
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
        self.setWindowTitle(self.tr("Geo Search: ") + text)

    # ID-based project id helpers removed. Matching is done by Title and group when
    # updating/removing entries from project variables.
        
    def create_page(self, setting):
        if setting["Title"] == "地番検索":
            return SearchTibanWidget(setting)
        if setting["Title"] == "所有者検索":
            return SearchOwnerWidget(setting)
        return SearchTextWidget(setting)

    def create_tab_groups(self, searchtabs):
        """Create grouped tab containers when multiple groups are present.

        Returns an OrderedDict mapping group name -> child QTabWidget.
        If there is one or zero groups, returns an empty dict to keep
        the simpler (ungrouped) tab layout.
        """
        try:
            groups = OrderedDict()
            # collect group order as they appear
            for t in (searchtabs or []):
                try:
                    g = t.get('group') if isinstance(t, dict) else None
                except Exception:
                    g = None
                if not g:
                    g = OTHER_GROUP_NAME
                if g not in groups:
                    groups[g] = None

            # If only one group (or none), don't create grouped UI
            if len(groups) <= 1:
                return {}

            created = OrderedDict()
            for g in groups.keys():
                try:
                    page = QWidget()
                    layout = QVBoxLayout(page)
                    child_tabs = QTabWidget()
                    layout.addWidget(child_tabs)
                    # add group page to the main tabWidget
                    try:
                        self.tabWidget.addTab(page, self.tr(str(g)))
                    except Exception:
                        # fallback to raw text
                        self.tabWidget.addTab(page, str(g))
                    created[g] = child_tabs
                except Exception:
                    continue
            return created
        except Exception:
            return {}
    def get_widgets(self):
        """Return a list of page widgets in the same order as self.setting['SearchTabs'].

        Matching is performed by comparing an optional '_load_sequence' marker kept on
        each tab's setting dict (preferred), falling back to Title+group matching.
        Returns None entries for tabs that could not be located.
        """
        result = []
        used = set()

        # Helper: yield all candidate page widgets in the UI
        def all_pages():
            # If grouped, pages live inside child QTabWidget instances placed on group pages
            try:
                if self.tab_groups:
                    for grp, child_tab in self.tab_groups.items():
                        try:
                            for i in range(child_tab.count()):
                                yield child_tab.widget(i)
                        except Exception:
                            continue
                # also include any top-level tabs that are not group containers
                for i in range(self.tabWidget.count()):
                    page = self.tabWidget.widget(i)
                    # if this page itself is a group container (we created it), skip
                    try:
                        # detect child QTabWidget
                        from qgis.PyQt.QtWidgets import QTabWidget
                        child = page.findChild(QTabWidget)
                        if child is not None:
                            # child tabs already yielded above
                            continue
                    except Exception:
                        pass
                    yield page
            except Exception:
                return

        # Build a mapping from '_load_sequence' -> widget for fast lookup
        seq_map = {}
        title_map = {}
        for p in all_pages():
            try:
                if p is None:
                    continue
                if hasattr(p, 'setting') and isinstance(p.setting, dict):
                    seq = p.setting.get('_load_sequence')
                    if seq is not None:
                        seq_map[int(seq)] = p
                    title = p.setting.get('Title')
                    grp = p.setting.get('group', OTHER_GROUP_NAME)
                    title_map.setdefault((title, grp), []).append(p)
                else:
                    # fallback: try to use widget.objectName as title hint
                    name = getattr(p, 'objectName', None)
                    if name:
                        title_map.setdefault((name, None), []).append(p)
            except Exception:
                continue

        for tab in (self.setting.get('SearchTabs') or []):
            try:
                if isinstance(tab, dict):
                    # Prefer matching by load sequence
                    seq = tab.get('_load_sequence')
                    if seq is not None and int(seq) in seq_map and seq_map[int(seq)] not in used:
                        w = seq_map[int(seq)]
                        result.append(w)
                        used.add(w)
                        continue

                    # Fallback: match by Title+group and pick first unused
                    title = tab.get('Title')
                    grp = tab.get('group', OTHER_GROUP_NAME)
                    candidates = title_map.get((title, grp)) or title_map.get((title, None)) or []
                    picked = None
                    for c in candidates:
                        if c not in used:
                            picked = c
                            break
                    if picked is not None:
                        result.append(picked)
                        used.add(picked)
                        continue

                # Last resort: try to pop next available page preserving order
                for p in all_pages():
                    if p not in used:
                        result.append(p)
                        used.add(p)
                        break
                else:
                    result.append(None)
            except Exception:
                result.append(None)

        return result

    def _normalize_source(self, src):
        """Normalize various '_source' token variants into canonical tokens.

        Returns one of: 'geo_search_json', 'project', 'setting.json', or
        a lowered, underscored fallback string.
        """
        try:
            if src is None:
                return ''
            s = str(src).strip().lower()
            # unify underscores and spaces
            s = s.replace('_', ' ')
            # common canonical forms
            if 'geo' in s and 'search' in s:
                return 'geo_search_json'
            if 'setting' in s and 'json' in s:
                return 'setting.json'
            if 'project' in s:
                # collapse any project-related variant to 'project'
                return 'project'
            # fallback: return underscored simple token
            return s.replace(' ', '_')
        except Exception:
            try:
                return str(src)
            except Exception:
                return ''

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
            
            # Create standard JSON for the current layer. Do NOT add an 'id' field;
            # matching will be performed by Title+group only.
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

            # Ask user where to save
            try:
                save_target = self.choose_save_target_dialog()
            except Exception:
                # If dialog fails unexpectedly, do not assume project - abort
                save_target = None

            # If user cancelled selection (None), gather diagnostic information
            # to help determine why the save did not proceed, then log and
            # present the details to the user. Do NOT retry automatically.
            if save_target is None:
                diag = []
                diag.append("save_target: None (user cancelled or dialog failed)")

                # Environment variable check
                try:
                    env_val = os.environ.get('geo_search_json')
                    diag.append(f"env geo_search_json={env_val}")
                except Exception as e:
                    diag.append(f"env geo_search_json: error: {e}")

                # Project variable check
                try:
                    from qgis.core import QgsProject, QgsExpressionContextUtils
                    proj = QgsProject.instance()
                    pv = QgsExpressionContextUtils.projectScope(proj).variable('geo_search_json')
                    proj_file = proj.fileName() or ''
                    diag.append(f"project.geo_search_json={pv}")
                    diag.append(f"project.filename={proj_file}")
                except Exception as e:
                    diag.append(f"project geo_search_json check error: {e}")

                # plugin setting.json check
                try:
                    plugin_dir = os.path.dirname(__file__)
                    setting_path = os.path.join(plugin_dir, 'setting.json')
                    exists = os.path.exists(setting_path)
                    try:
                        writable = os.access(setting_path, os.W_OK) if exists else os.access(plugin_dir, os.W_OK)
                    except Exception:
                        writable = False
                    diag.append(f"plugin setting.json path={setting_path} exists={exists} writable={writable}")
                except Exception as e:
                    diag.append(f"plugin setting.json check error: {e}")

                # Active layer / layer info
                try:
                    layer_info = "<no iface available>"
                    iface = getattr(self, 'iface', None)
                    if iface is None and hasattr(self.parent(), 'iface'):
                        iface = getattr(self.parent(), 'iface')
                    if iface is not None:
                        layer = iface.activeLayer()
                        if layer is None:
                            layer_info = "activeLayer: None"
                        else:
                            try:
                                layer_name = layer.name() if hasattr(layer, 'name') else str(layer)
                                fields_count = len(list(layer.fields())) if hasattr(layer, 'fields') else 'unknown'
                                layer_info = f"activeLayer.name={layer_name} fields={fields_count}"
                            except Exception as e:
                                layer_info = f"activeLayer introspect error: {e}"
                    diag.append(layer_info)
                except Exception as e:
                    diag.append(f"active layer check error: {e}")

                # Log diagnostics
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage("Add current layer aborted; diagnostics:\n" + "\n".join(diag), "GEO-search-plugin", 1)
                except Exception:
                    print("Add current layer aborted; diagnostics:")
                    for d in diag:
                        print(d)

                # Show dialog with summary and detailed text for troubleshooting
                try:
                    msg = QMessageBox(self)
                    msg.setIcon(QMessageBox.Warning)
                    msg.setWindowTitle(self.tr("Add current layer aborted"))
                    msg.setText(self.tr("The save operation was cancelled. Diagnostic information has been logged."))
                    # setDetailedText is available on QMessageBox to show long diagnostics
                    try:
                        msg.setDetailedText("\n".join(diag))
                    except Exception:
                        # Fallback: append diagnostics to text if detailed not available
                        msg.setText(msg.text() + "\n\n" + "\n".join(diag))
                    try:
                        msg.exec_()
                    except Exception:
                        try:
                            msg.exec()
                        except Exception:
                            pass
                except Exception:
                    # As a last resort, show a simple information box
                    try:
                        QMessageBox.information(self, self.tr("Cancelled"), self.tr("Add current layer aborted. See log for details."))
                    except Exception:
                        pass

                return

            # read existing variable (used when saving to project variable)
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

            # route write according to user's selection (use small save wrappers and show diagnostics)
            wrote_ok = False
            try:
                if save_target == 'project' or save_target is None:
                    try:
                        ok = self._save_to_project_variable(project, new_value)
                        if ok:
                            wrote_ok = True
                            try:
                                from qgis.core import QgsExpressionContextUtils, QgsMessageLog
                                read_back = QgsExpressionContextUtils.projectScope(project).variable('GEO-search-plugin')
                                QgsMessageLog.logMessage(f"Wrote project variable via helper: {str(read_back)}", "GEO-search-plugin", 0)
                            except Exception:
                                pass
                        else:
                            try:
                                from qgis.core import QgsMessageLog
                                QgsMessageLog.logMessage("set_project_variable returned False when writing GEO-search-plugin", "GEO-search-plugin", 1)
                            except Exception:
                                print("set_project_variable returned False when writing GEO-search-plugin")
                    except Exception as err:
                        try:
                            from qgis.core import QgsMessageLog
                            QgsMessageLog.logMessage(f"Error while persisting via set_project_variable: {err}", "GEO-search-plugin", 1)
                        except Exception:
                            print(f"Error while persisting via set_project_variable: {err}")
                elif save_target == 'setting_json':
                    wrote_ok = self._save_to_setting_json(standard_json)
                elif save_target == 'geo_search_json':
                    wrote_ok = self._save_to_geo_search_json(standard_json)
                else:
                    try:
                        ok = self._save_to_project_variable(project, new_value)
                        if ok:
                            wrote_ok = True
                        else:
                            try:
                                from qgis.core import QgsMessageLog
                                QgsMessageLog.logMessage("set_project_variable returned False when writing GEO-search-plugin (default route)", "GEO-search-plugin", 1)
                            except Exception:
                                print("set_project_variable returned False when writing GEO-search-plugin (default route)")
                    except Exception as err:
                        try:
                            from qgis.core import QgsMessageLog
                            QgsMessageLog.logMessage(f"Error while persisting via set_project_variable (default route): {err}", "GEO-search-plugin", 1)
                        except Exception:
                            print(f"Error while persisting via set_project_variable (default route): {err}")
            except Exception as e:
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"Error writing settings: {e}", "GEO-search-plugin", 1)
                except Exception:
                    print(f"Error writing settings: {e}")

            # If write succeeded, reload UI; otherwise show diagnostic to user (already logged by wrappers)
            if wrote_ok:
                try:
                    self.reload_ui("with new layer")
                except Exception:
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage("reload_ui after save failed", "GEO-search-plugin", 2)
                    except Exception:
                        print("reload_ui after save failed")
                # exit early since we already reloaded
                return
            else:
                # inform user that save failed (wrappers/logs provide details)
                try:
                    QMessageBox.warning(self, self.tr("Save Failed"), self.tr("Failed to persist the new layer setting. See log for details."))
                except Exception:
                    pass
                return
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"add_current_layer_to_project_variable error: {e}", "GEO-search-plugin", 1)
            except Exception:
                print(f"add_current_layer_to_project_variable error: {e}")
        
        # UI reload is handled after successful save; do not reload unconditionally here.
    
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

            # Determine safe QMessageBox constants to avoid binding differences
            YES_CONST = None
            NO_CONST = None
            YES_NO_FLAGS = 0
            try:
                # Avoid referencing QMessageBox.Yes/No directly in comparisons
                YES_CONST = getattr(QMessageBox, 'Yes', None)
                NO_CONST = getattr(QMessageBox, 'No', None)
                if YES_CONST is None or NO_CONST is None:
                    sb = getattr(QMessageBox, 'StandardButton', None)
                    if sb is not None:
                        YES_CONST = getattr(sb, 'Yes', YES_CONST)
                        NO_CONST = getattr(sb, 'No', NO_CONST)
                if YES_CONST is None:
                    YES_CONST = 0
                if NO_CONST is None:
                    NO_CONST = 0
                try:
                    YES_NO_FLAGS = YES_CONST | NO_CONST
                except Exception:
                    YES_NO_FLAGS = 0
            except Exception:
                YES_CONST = 0
                NO_CONST = 0
                YES_NO_FLAGS = 0
                
            # 選択されているタブの情報を取得（共通ヘルパーを使用）
            try:
                current_tab, current_tab_title, current_tab_index, current_group_name, active_tabwidget, src_val, src_idx = self._get_current_tab_info()
            except Exception:
                current_tab = None
                current_tab_title = None
                current_group_name = None
                src_val = None
                src_idx = None

            # Log provenance when available to help debugging
            try:
                if src_val is not None or src_idx is not None:
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"_get_current_tab_info provenance: src_val={repr(src_val)} src_idx={repr(src_idx)} title={repr(current_tab_title)} group={repr(current_group_name)}", "GEO-search-plugin", 0)
                    except Exception:
                        print(f"_get_current_tab_info provenance: src_val={repr(src_val)} src_idx={repr(src_idx)} title={repr(current_tab_title)} group={repr(current_group_name)}")
            except Exception:
                pass

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
                # No project variable set. Try to remove from external
                # geo_search_json if possible. Resolution strategy:
                # 1) If widget.setting._source == 'geo_search_json', prefer that.
                # 2) Otherwise try to resolve geo_search_json path (env/project var),
                #    allowing the user to locate it if not present.
                def _resolve_geo_search_path(allow_user_pick=True):
                    p = None
                    try:
                        p = os.environ.get('geo_search_json')
                    except Exception:
                        p = None
                    try:
                        from qgis.core import QgsProject, QgsExpressionContextUtils
                        proj = QgsProject.instance()
                        pv = QgsExpressionContextUtils.projectScope(proj).variable('geo_search_json')
                        if pv:
                            p = pv
                        try:
                            proj_file = proj.fileName() or ''
                            proj_dir = os.path.dirname(proj_file) if proj_file else ''
                        except Exception:
                            proj_dir = ''
                        if p and proj_dir and not os.path.isabs(p):
                            p = os.path.join(proj_dir, p)
                    except Exception:
                        pass

                    if (not p or not os.path.exists(p)) and allow_user_pick:
                        try:
                            from qgis.PyQt.QtWidgets import QFileDialog
                            start_dir = os.path.dirname(p) if p else os.getcwd()
                            sel, _ = QFileDialog.getOpenFileName(self, self.tr("Locate geo_search_json file"), start_dir, self.tr("JSON Files (*.json);;All Files (*)"))
                        except Exception:
                            sel = None
                        if sel:
                            p = sel

                    if p and os.path.exists(p):
                        return p
                    return None

                # removal logic moved to utils.remove_entry_from_json_file

                # Prefer explicit provenance if available. If the widget does
                # not expose provenance in `setting`, try to infer it from the
                # visible UI label (e.g. a QLabel showing "[geo_search_json]").
                src_val = None
                src_idx = None
                try:
                    if hasattr(current_tab, 'setting') and isinstance(current_tab.setting, dict):
                        src_val = current_tab.setting.get('_source')
                        src_idx = current_tab.setting.get('_source_index')
                except Exception:
                    src_val = None
                    src_idx = None

                # If no explicit provenance, inspect child QLabel texts for
                # a marker like "[geo_search_json]" or any text containing
                # 'geo' and 'search' so we can branch correctly.
                if not src_val:
                    try:
                        from qgis.PyQt.QtWidgets import QLabel
                        import re
                        # find any QLabel child containing bracketed token
                        if hasattr(current_tab, 'findChildren'):
                            for lbl in current_tab.findChildren(QLabel):
                                try:
                                    txt = (lbl.text() or '').strip()
                                    if not txt:
                                        continue
                                    m = re.search(r"\[([^\]]+)\]", txt)
                                    if m:
                                        token = m.group(1)
                                        if token and self._normalize_source(token):
                                            src_val = token
                                            break
                                    # fallback: direct text match
                                    low = txt.lower()
                                    if 'geo' in low and 'search' in low:
                                        src_val = txt
                                        break
                                except Exception:
                                    continue
                    except Exception:
                        # Best-effort only; continue without inferred source.
                        pass

                # Log inferred provenance for debugging
                try:
                    norm_src = self._normalize_source(src_val)
                except Exception:
                    norm_src = str(src_val)
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"remove_current_tab: inferred src_val={repr(src_val)} norm={norm_src} src_idx={repr(src_idx)} title={current_tab_title}", "GEO-search-plugin", 0)
                except Exception:
                    try:
                        print(f"remove_current_tab: inferred src_val={repr(src_val)} norm={norm_src} src_idx={repr(src_idx)} title={current_tab_title}")
                    except Exception:
                        pass

                # If the inferred source is the plugin's bundled setting.json,
                # remove from that file directly.
                if norm_src == 'setting.json':
                    try:
                        # Confirm with user
                        q = QMessageBox.question(
                            self,
                            self.tr("Delete tab from plugin setting.json"),
                            self.tr("This tab was loaded from the plugin's setting.json file.\nDo you want to remove the corresponding entry from that file?"),
                            YES_NO_FLAGS,
                        )
                    except Exception:
                        q = NO_CONST

                    if q != YES_CONST:
                        try:
                            from qgis.core import QgsMessageLog
                            QgsMessageLog.logMessage("User cancelled deletion from plugin setting.json (no project variable present)", 'GEO-search-plugin', 0)
                        except Exception:
                            pass
                        return

                    plugin_dir = os.path.dirname(__file__)
                    path = os.path.join(plugin_dir, 'setting.json')
                    if not os.path.exists(path):
                        QMessageBox.warning(self, self.tr("File not found"), self.tr("Could not locate the plugin setting.json file to edit."))
                        return

                    ok = remove_entry_from_json_file(path, title=(current_tab.setting.get('Title') if isinstance(current_tab.setting, dict) else current_tab_title), src_idx=src_idx, parent=self)
                    if ok:
                        self.reload_ui("after removing tab from plugin setting.json (no project variable)")
                    return

                if norm_src == 'geo_search_json':
                    # Ask confirm
                    try:
                        q = QMessageBox.question(
                            self,
                            self.tr("Delete tab from geo_search_json"),
                            self.tr("This tab was loaded from the external geo_search_json file.\nDo you want to remove the corresponding entry from that file?"),
                            YES_NO_FLAGS,
                        )
                    except Exception:
                        # fallback: ensure q is set to NO to avoid accidental delete
                        try:
                            q = NO_CONST
                        except Exception:
                            q = 0
                    if q != YES_CONST:
                        try:
                            from qgis.core import QgsMessageLog
                            QgsMessageLog.logMessage("User cancelled deletion from geo_search_json (no project variable present)", 'GEO-search-plugin', 0)
                        except Exception:
                            pass
                        return

                    path = _resolve_geo_search_path(allow_user_pick=True)
                    if not path:
                        QMessageBox.warning(self, self.tr("File not found"), self.tr("Could not locate the geo_search_json file to edit."))
                        return

                    ok = remove_entry_from_json_file(path, title=(current_tab.setting.get('Title') if isinstance(current_tab.setting, dict) else current_tab_title), src_idx=src_idx, parent=self)
                    if ok:
                        self.reload_ui("after removing tab from geo_search_json (no project variable)")
                    return

                # Try to resolve geo_search file and look up by Title if provenance not explicit
                path = _resolve_geo_search_path(allow_user_pick=True)
                if path:
                    # attempt title-match removal
                    title_to_find = None
                    try:
                        if hasattr(current_tab, 'setting') and isinstance(current_tab.setting, dict):
                            title_to_find = current_tab.setting.get('Title')
                    except Exception:
                        title_to_find = None
                    if not title_to_find:
                        title_to_find = current_tab_title

                    # Ask user first
                    try:
                        q = QMessageBox.question(
                            self,
                            self.tr("Delete tab from geo_search_json"),
                            self.tr("This tab may be present in the external geo_search_json file.\nDo you want to attempt to remove the matching entry from that file?"),
                            YES_NO_FLAGS,
                        )
                    except Exception:
                        q = NO_CONST

                    if q != YES_CONST:
                        try:
                            from qgis.core import QgsMessageLog
                            QgsMessageLog.logMessage("User declined to search external geo_search_json for matching Title", 'GEO-search-plugin', 0)
                        except Exception:
                            pass
                        return

                    ok = remove_entry_from_json_file(path, title=title_to_find, src_idx=None, parent=self)
                    if ok:
                        self.reload_ui("after removing tab from geo_search_json (title-match)")
                    return

                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage("No project variable exists to remove from", "GEO-search-plugin", 1)
                except Exception:
                    print("No project variable exists to remove from")
                return
                
            try:
                # Try to interpret the project variable. It may be:
                #  - inline JSON (list/dict)
                #  - a JSON string
                #  - a path to an external JSON file (file-backed project variable)
                parsed = None
                container_is_file = False
                project_file_path = None

                # First, try parsing as JSON
                try:
                    parsed = json.loads(existing)
                except Exception:
                    # Not JSON; maybe it's a file path stored in the variable.
                    try:
                        # resolve relative to project dir if necessary
                        proj = QgsProject.instance()
                        proj_file = proj.fileName() or ''
                        proj_dir = os.path.dirname(proj_file) if proj_file else ''
                        candidate = existing
                        if isinstance(candidate, str) and proj_dir and not os.path.isabs(candidate):
                            candidate = os.path.join(proj_dir, candidate)
                        if isinstance(candidate, str) and os.path.exists(candidate):
                            # load JSON from file
                            with open(candidate, 'r', encoding='utf-8') as fh:
                                parsed = json.load(fh)
                            container_is_file = True
                            project_file_path = candidate
                        else:
                            parsed = None
                    except Exception:
                        parsed = None

                if parsed is None:
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage("Could not parse project variable as JSON nor locate file path.", "GEO-search-plugin", 1)
                    except Exception:
                        print("Could not parse project variable as JSON nor locate file path.")
                    QMessageBox.warning(self, self.tr("Unsupported project variable"), self.tr("Project variable 'GEO-search-plugin' does not contain JSON and is not a valid file path."))
                    return

                # Normalize parsed into a list when inline
                if not container_is_file:
                    if not isinstance(parsed, list):
                        parsed = [parsed]

                # Prepare resolved title for matching (prefer widget.setting Title)
                resolved_title = None
                try:
                    if hasattr(current_tab, 'setting') and isinstance(current_tab.setting, dict):
                        resolved_title = current_tab.setting.get('Title')
                except Exception:
                    resolved_title = None
                if not resolved_title:
                    resolved_title = current_tab_title

                # If the project variable itself points to a file (file-backed), allow deleting from that file
                if container_is_file and project_file_path:
                    # Ask for confirmation
                    try:
                        q = QMessageBox.question(
                            self,
                            self.tr("Delete tab from project-backed file"),
                            self.tr("Project variable points to an external file.\nDo you want to remove the corresponding entry from that file?"),
                            YES_NO_FLAGS,
                        )
                    except Exception:
                        q = NO_CONST

                    if q != YES_CONST:
                        try:
                            from qgis.core import QgsMessageLog
                            QgsMessageLog.logMessage("User cancelled deletion from project-backed file", 'GEO-search-plugin', 0)
                        except Exception:
                            pass
                        return

                    # Determine list container in file
                    data = parsed
                    if isinstance(data, dict) and isinstance(data.get('SearchTabs'), list):
                        target = data['SearchTabs']
                        container_is_dict = True
                    elif isinstance(data, list):
                        target = data
                        container_is_dict = False
                    else:
                        QMessageBox.warning(self, self.tr("Unsupported format"), self.tr("Project-backed file has unsupported structure; expected {'SearchTabs': [...]} or an array."))
                        return

                    # Determine remove index: prefer annotated _source_index when _source refers to project file
                    remove_idx = None
                    try:
                        if hasattr(current_tab, 'setting') and isinstance(current_tab.setting, dict):
                            src = current_tab.setting.get('_source')
                            src_idx = current_tab.setting.get('_source_index')
                            if self._normalize_source(src) == 'project' and isinstance(src_idx, int):
                                if 0 <= src_idx < len(target):
                                    remove_idx = int(src_idx)
                    except Exception:
                        remove_idx = None

                    if remove_idx is None:
                        # Fallback to Title match
                        title = resolved_title
                        for i, it in enumerate(target):
                            try:
                                if isinstance(it, dict) and it.get('Title') == title:
                                    remove_idx = i
                                    break
                            except Exception:
                                continue

                    if remove_idx is None:
                        QMessageBox.information(self, self.tr("Not found"), self.tr("Could not find corresponding entry in project-backed file to remove."))
                        return

                    # Backup and atomic remove (same pattern as geo_search_json)
                    try:
                        bak_name = f"{os.path.basename(project_file_path)}.{datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.bak"
                        bak_path = os.path.join(os.path.dirname(project_file_path), bak_name)
                        shutil.copy2(project_file_path, bak_path)
                    except Exception:
                        bak_path = None

                    try:
                        del target[remove_idx]
                        out = data if container_is_dict else target
                        dirn = os.path.dirname(project_file_path) or '.'
                        fd, tmp_path = tempfile.mkstemp(prefix='geo_search_proj_', dir=dirn, text=True)
                        try:
                            with os.fdopen(fd, 'w', encoding='utf-8') as tmpfh:
                                json.dump(out, tmpfh, ensure_ascii=False, indent=2)
                            os.replace(tmp_path, project_file_path)
                        finally:
                            try:
                                if os.path.exists(tmp_path):
                                    os.remove(tmp_path)
                            except Exception:
                                pass
                    except Exception as e:
                        QMessageBox.warning(self, self.tr("Write error"), self.tr("Failed to update project-backed file: {0}").format(str(e)))
                        try:
                            if bak_path and os.path.exists(bak_path):
                                shutil.copy2(bak_path, project_file_path)
                        except Exception:
                            pass
                        return

                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"Removed entry index={remove_idx} from project-backed file: {project_file_path} (backup={bak_path})", 'GEO-search-plugin', 0)
                    except Exception:
                        pass

                    self.reload_ui("after removing tab from project-backed file")
                    return

                # At this point we have inline parsed list (parsed)
                # Allow index-based removal if widget.setting annotated the source/index
                removed = False
                try:
                    if hasattr(current_tab, 'setting') and isinstance(current_tab.setting, dict):
                        src = current_tab.setting.get('_source')
                        src_idx = current_tab.setting.get('_source_index')
                        if self._normalize_source(src) == 'project' and isinstance(src_idx, int):
                            if 0 <= src_idx < len(parsed):
                                # remove by index
                                del parsed[int(src_idx)]
                                removed = True
                except Exception:
                    removed = False

                if not removed:
                    # Fallback: match by Title and group (remove all matching Titles)
                    updated_settings = [item for item in parsed if not (isinstance(item, dict) and item.get('Title') == resolved_title)]
                    if len(updated_settings) == len(parsed):
                        try:
                            from qgis.core import QgsMessageLog
                            QgsMessageLog.logMessage(f"Tab '{resolved_title}' not found in project variable (inline)", "GEO-search-plugin", 1)
                        except Exception:
                            print(f"Tab '{resolved_title}' not found in project variable (inline)")
                        # Nothing changed
                        new_value = json.dumps(parsed, ensure_ascii=False) if parsed else ""
                    else:
                        # We removed at least one; write back updated_settings
                        if len(updated_settings) == 0:
                            new_value = ""
                        else:
                            new_value = json.dumps(updated_settings, ensure_ascii=False)
                        # Persist
                        try:
                            ok = self._save_to_project_variable(project, new_value)
                            if not ok:
                                try:
                                    from qgis.core import QgsMessageLog
                                    QgsMessageLog.logMessage("set_project_variable returned False when removing tab (inline)", "GEO-search-plugin", 1)
                                except Exception:
                                    print("set_project_variable returned False when removing tab (inline)")
                        except Exception as e:
                            try:
                                from qgis.core import QgsMessageLog
                                QgsMessageLog.logMessage(f"Error updating project variable (inline): {e}", "GEO-search-plugin", 1)
                            except Exception:
                                print(f"Error updating project variable (inline): {e}")
                        self.reload_ui("after removing tab from project variable")
                        return

                # If we removed by index earlier, persist parsed (which was mutated)
                if removed:
                    if len(parsed) == 0:
                        new_value = ""
                    else:
                        new_value = json.dumps(parsed, ensure_ascii=False)
                    try:
                        ok = self._save_to_project_variable(project, new_value)
                        if not ok:
                            try:
                                from qgis.core import QgsMessageLog
                                QgsMessageLog.logMessage("set_project_variable returned False when removing tab (by index)", "GEO-search-plugin", 1)
                            except Exception:
                                print("set_project_variable returned False when removing tab (by index)")
                    except Exception as e:
                        try:
                            from qgis.core import QgsMessageLog
                            QgsMessageLog.logMessage(f"Error updating project variable (by index): {e}", "GEO-search-plugin", 1)
                        except Exception:
                            print(f"Error updating project variable (by index): {e}")
                    self.reload_ui("after removing tab from project variable")
                    return
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
            
            # 現在選択されているタブの情報を取得（共通ヘルパーを使用）
            try:
                current_tab, current_tab_title, current_tab_index, current_group_name, active_tabwidget, src_val, src_idx = self._get_current_tab_info()
            except Exception:
                current_tab = None
                current_tab_title = None
                current_tab_index = -1
                current_group_name = None
                src_val = None
                src_idx = None

            # Log provenance when available to help debugging (edit flow)
            try:
                if src_val is not None or src_idx is not None:
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"_get_current_tab_info provenance (edit): src_val={repr(src_val)} src_idx={repr(src_idx)} title={repr(current_tab_title)} group={repr(current_group_name)}", "GEO-search-plugin", 0)
                    except Exception:
                        print(f"_get_current_tab_info provenance (edit): src_val={repr(src_val)} src_idx={repr(src_idx)} title={current_tab_title} group={current_group_name}")
            except Exception:
                pass

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

                # プロジェクト変数IDがある場合は優先的にIDを使用して検索
                # まずIDで検索
                # Prefer to match by the widget's underlying setting Title (not
                # the possibly-localized tab text). Fall back to the visible
                # tab text when widget.setting is unavailable.
                resolved_title = None
                try:
                    if hasattr(current_tab, 'setting') and isinstance(current_tab.setting, dict):
                        resolved_title = current_tab.setting.get('Title')
                except Exception:
                    resolved_title = None
                if not resolved_title:
                    resolved_title = current_tab_title

                # Match by Title and group (IDs removed). Prefer exact Title match.
                for i, config in enumerate(parsed):
                    if config.get("Title") == resolved_title:
                        tab_config = config
                        tab_index_in_config = i
                        break

                # 設定が見つからなければ、現在のタブに基づいて新しい設定を作成
                if tab_config is None:
                    # Create a default tab_config based on current tab title.
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

            # Ensure provenance info from UI helper is reflected in the tab_config
            try:
                if 'tab_config' in locals() and tab_config is not None:
                    if src_val is not None:
                        tab_config['_source'] = src_val
                    if src_idx is not None:
                        tab_config['_source_index'] = src_idx
            except Exception:
                pass
            
            # 編集ダイアログを作成
            edit_dialog = QDialog(self)
            edit_dialog.setWindowTitle(self.tr("Edit Tab Settings: {0}").format(resolved_title if 'resolved_title' in locals() and resolved_title else current_tab_title))
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

            # 表示フィールド (ViewFields) - 編集可能に変更
            if "ViewFields" in tab_config:
                editable_fields["ViewFields"] = tab_config["ViewFields"]
                tab_config["_ViewFields"] = tab_config["ViewFields"]
            else:
                editable_fields["ViewFields"] = []
                tab_config["_ViewFields"] = []

            # selectTheme（マップテーマ名）も編集可能に追加
            # selectTheme（マップテーマ名）も編集可能に追加（既存テーマ一覧から選択可能にするためQComboBoxを使う）
            if "selectTheme" in tab_config:
                editable_fields["selectTheme"] = tab_config["selectTheme"]
            else:
                editable_fields["selectTheme"] = ""
            # 角度（map rotation）を追加: -360..360 の数値を編集できるようにする
            # 既存設定があれば引き継ぐ
            if "angle" in tab_config:
                # preserve explicit null (None) as None so UI can show '未指定'
                val = tab_config.get("angle")
                if val is None:
                    editable_fields["angle"] = None
                else:
                    try:
                        editable_fields["angle"] = float(val)
                    except Exception:
                        editable_fields["angle"] = 0.0
            else:
                editable_fields["angle"] = None
            # スケール（scale）を追加: 角度と同じ入力方式（数値＋未指定チェック）
            if "scale" in tab_config:
                val = tab_config.get("scale")
                if val is None:
                    editable_fields["scale"] = None
                else:
                    try:
                        editable_fields["scale"] = float(val)
                    except Exception:
                        editable_fields["scale"] = 0.0
            else:
                editable_fields["scale"] = None
            
            # readonly_fields に編集可能フィールドが混入すると同じ項目が編集セクションと
            # 読み取り専用セクションの両方に表示されてしまうため、編集可能にしたキーは除外する
            editable_exclude = {"group", "Title", "SearchField", "ViewFields", "selectTheme", "angle", "scale"}
            for key, value in tab_config.items():
                if key not in editable_exclude:
                    readonly_fields[key] = value
                    
            # テキストエディタを作成
            editors = {}
            
            # 編集可能フィールドの設定
            row = 0
            for field_name, field_value in editable_fields.items():
                # 日本語ラベルを使う（角度/スケールは分かりやすく表示）
                if field_name == "angle":
                    label = QLabel(self.tr("Angle (deg):"), edit_dialog)
                elif field_name == "scale":
                    label = QLabel(self.tr("Scale:"), edit_dialog)
                else:
                    label = QLabel(self.tr(f"{field_name}:") if isinstance(field_name, str) else field_name, edit_dialog)
                label.setStyleSheet("font-weight: bold;")
                grid_layout.addWidget(label, row, 0)

                if field_name == "selectTheme":
                    # selectThemeはQComboBoxで既存テーマ一覧から選択
                    from qgis.PyQt.QtWidgets import QComboBox
                    from qgis.core import QgsProject
                    editor = QComboBox(edit_dialog)
                    editor.setObjectName(f"{field_name}_editor")
                    # マップテーマ一覧を取得
                    try:
                        project = QgsProject.instance()
                        theme_collection = project.mapThemeCollection()
                        raw_themes = theme_collection.mapThemes() if theme_collection else []
                    except Exception:
                        raw_themes = []

                    # normalize theme list to names
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

                    editor.addItem("")  # 空選択肢
                    for theme in themes:
                        editor.addItem(theme)
                    # 初期値をセット
                    if field_value and field_value in [editor.itemText(i) for i in range(editor.count())]:
                        editor.setCurrentText(field_value)
                    grid_layout.addWidget(editor, row, 1)
                    editors[field_name] = editor
                elif field_name == "angle":
                    # 角度入力用の小数対応スピンボックス + 未指定チェックボックス
                    from qgis.PyQt.QtWidgets import QDoubleSpinBox, QCheckBox, QHBoxLayout
                    container = QHBoxLayout()
                    spin = QDoubleSpinBox(edit_dialog)
                    spin.setObjectName(f"{field_name}_editor")
                    # allow negative angles too: -360..360
                    spin.setRange(-360.0, 360.0)
                    spin.setSingleStep(5.0)
                    spin.setDecimals(2)
                    # checkbox: 指定しない -> NULL
                    chk = QCheckBox("指定しない (NULL)", edit_dialog)
                    # set initial state based on field_value (None means unspecified)
                    try:
                        if field_value is None:
                            chk.setChecked(True)
                            spin.setValue(0.0)
                            spin.setDisabled(True)
                        else:
                            chk.setChecked(False)
                            spin.setValue(float(field_value))
                            spin.setDisabled(False)
                    except Exception:
                        chk.setChecked(True)
                        spin.setValue(0.0)
                        spin.setDisabled(True)

                    # toggle behavior
                    def _on_chk_toggled(state, spin_box=spin):
                        try:
                            spin_box.setDisabled(bool(state))
                        except Exception:
                            pass

                    chk.toggled.connect(_on_chk_toggled)
                    from qgis.PyQt.QtWidgets import QPushButton

                    # ボタン: 現在の地図回転値を設定
                    set_current_btn = QPushButton(self.tr("Set current value"), edit_dialog)

                    def _set_current_value(btn=None, spin_box=spin):
                        try:
                            # prefer dialog's iface, fallback to parent iface
                            iface = getattr(self, 'iface', None)
                            if iface is None and hasattr(self.parent(), 'iface'):
                                iface = self.parent().iface
                            if iface is None:
                                return
                            try:
                                canvas = iface.mapCanvas()
                                rotation = canvas.rotation() if hasattr(canvas, 'rotation') else None
                            except Exception:
                                rotation = None
                            if rotation is None:
                                return
                            try:
                                spin_box.setValue(float(rotation))
                                # uncheck '指定しない' if it was checked
                                try:
                                    if chk.isChecked():
                                        chk.setChecked(False)
                                        spin_box.setDisabled(False)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                        except Exception:
                            pass

                    # capture current chk in default args to avoid late-binding of closure
                    def _set_current_value_captured(btn=None, spin_box=spin, chk=chk):
                        try:
                            iface = getattr(self, 'iface', None)
                            if iface is None and hasattr(self.parent(), 'iface'):
                                iface = self.parent().iface
                            if iface is None:
                                return
                            try:
                                canvas = iface.mapCanvas()
                                rotation = canvas.rotation() if hasattr(canvas, 'rotation') else None
                            except Exception:
                                rotation = None
                            if rotation is None:
                                return
                            try:
                                spin_box.setValue(float(rotation))
                                try:
                                    if chk.isChecked():
                                        chk.setChecked(False)
                                        spin_box.setDisabled(False)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                        except Exception:
                            pass

                    set_current_btn.clicked.connect(_set_current_value_captured)

                    container.addWidget(spin)
                    container.addWidget(chk)
                    container.addWidget(set_current_btn)
                    grid_layout.addLayout(container, row, 1)
                    # store tuple so save logic can detect checkbox and button
                    editors[field_name] = (spin, chk, set_current_btn)
                elif field_name == "scale":
                    # スケール入力用の小数対応スピンボックス + 未指定チェックボックス
                    from qgis.PyQt.QtWidgets import QDoubleSpinBox, QCheckBox, QHBoxLayout
                    container = QHBoxLayout()
                    spin = QDoubleSpinBox(edit_dialog)
                    spin.setObjectName(f"{field_name}_editor")
                    # スケールは大きめの範囲に設定
                    spin.setRange(0.0, 1e9)
                    spin.setSingleStep(100.0)
                    spin.setDecimals(2)
                    # checkbox: 指定しない -> NULL
                    chk = QCheckBox("指定しない (NULL)", edit_dialog)
                    # set initial state based on field_value (None means unspecified)
                    try:
                        if field_value is None:
                            chk.setChecked(True)
                            spin.setValue(0.0)
                            spin.setDisabled(True)
                        else:
                            chk.setChecked(False)
                            spin.setValue(float(field_value))
                            spin.setDisabled(False)
                    except Exception:
                        chk.setChecked(True)
                        spin.setValue(0.0)
                        spin.setDisabled(True)

                    # toggle behavior
                    def _on_chk_toggled_scale(state, spin_box=spin):
                        try:
                            spin_box.setDisabled(bool(state))
                        except Exception:
                            pass

                    chk.toggled.connect(_on_chk_toggled_scale)
                    from qgis.PyQt.QtWidgets import QPushButton

                    # ボタン: 現在の地図スケールを設定
                    set_current_btn = QPushButton("現在のスケールを設定", edit_dialog)

                    def _set_current_scale(btn=None, spin_box=spin):
                        try:
                            iface = getattr(self, 'iface', None)
                            if iface is None and hasattr(self.parent(), 'iface'):
                                iface = self.parent().iface
                            if iface is None:
                                return
                            try:
                                canvas = iface.mapCanvas()
                                scale_val = canvas.scale() if hasattr(canvas, 'scale') else None
                            except Exception:
                                scale_val = None
                            if scale_val is None:
                                return
                            try:
                                spin_box.setValue(float(scale_val))
                                try:
                                    if chk.isChecked():
                                        chk.setChecked(False)
                                        spin_box.setDisabled(False)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                        except Exception:
                            pass

                    # capture current chk in default args to avoid late-binding of closure
                    def _set_current_scale_captured(btn=None, spin_box=spin, chk=chk):
                        try:
                            iface = getattr(self, 'iface', None)
                            if iface is None and hasattr(self.parent(), 'iface'):
                                iface = self.parent().iface
                            if iface is None:
                                return
                            try:
                                canvas = iface.mapCanvas()
                                scale_val = canvas.scale() if hasattr(canvas, 'scale') else None
                            except Exception:
                                scale_val = None
                            if scale_val is None:
                                return
                            try:
                                spin_box.setValue(float(scale_val))
                                try:
                                    if chk.isChecked():
                                        chk.setChecked(False)
                                        spin_box.setDisabled(False)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                        except Exception:
                            pass

                    set_current_btn.clicked.connect(_set_current_scale_captured)

                    container.addWidget(spin)
                    container.addWidget(chk)
                    container.addWidget(set_current_btn)
                    grid_layout.addLayout(container, row, 1)
                    editors[field_name] = (spin, chk, set_current_btn)
                else:
                    # 既存のTQextEditエディタ
                    editor = QTextEdit(edit_dialog)
                    editor.setObjectName(f"{field_name}_editor")
                    font = self.get_monospace_font()
                    if font is not None:
                        editor.setFont(font)
                    editor.setMinimumHeight(80)
                    json_str = json.dumps(field_value, indent=2, ensure_ascii=False)
                    editor.setText(json_str)
                    grid_layout.addWidget(editor, row, 1)
                    editors[field_name] = editor
                row += 1
                
            # レイヤー名を取得
            layer_name = ""
            if "Layer" in tab_config and "Name" in tab_config["Layer"]:
                layer_name = tab_config["Layer"]["Name"]
                
            # SearchField のエディタを取得
            searchfield_editor = editors.get("SearchField")
            
            if searchfield_editor:
                # フィールド選択ボタン用のレイアウト
                searchfield_layout = QHBoxLayout()
                
                # 現在の値を取得
                try:
                    current_search_field = json.loads(searchfield_editor.toPlainText())
                except:
                    current_search_field = {}
                    
                # フィールド選択ボタン
                select_search_field_button = QPushButton("検索フィールド選択ウィザード（複数選択可 - OR検索）", edit_dialog)
                
                # ボタンクリック時の処理
                select_search_field_button.clicked.connect(
                    lambda: self.edit_search_field(
                        current_search_field,
                        layer_name,
                        edit_dialog,
                        lambda new_field: searchfield_editor.setText(json.dumps(new_field, indent=2, ensure_ascii=False))
                    )
                )
                
                searchfield_layout.addWidget(select_search_field_button)
                searchfield_layout.addStretch()
                
                # 補助ラベル
                search_field_help_label = QLabel("※「SearchField」フィールドを直接編集するか、検索フィールド選択ウィザード（複数選択可 - OR検索）を使用できます", edit_dialog)
                search_field_help_label.setStyleSheet("color: #555555; font-style: italic;")
                
                # レイアウトに追加
                layout.addLayout(searchfield_layout)
                layout.addWidget(search_field_help_label)
            
            # ViewFields 用のボタンを追加
            # フィールド選択補助ボタン - ViewFields編集用
            helper_layout = QHBoxLayout()
                
            # ViewFieldsのエディタを取得
            viewfields_editor = editors.get("ViewFields")
            
            if viewfields_editor:
                # フィールド選択ボタン
                select_fields_button = QPushButton("表示フィールド選択ウィザード", edit_dialog)
                
                # 現在の値を取得
                try:
                    current_fields = json.loads(viewfields_editor.toPlainText())
                    if not isinstance(current_fields, list):
                        current_fields = []
                except:
                    current_fields = []
                
                # ボタンクリック時の処理
                select_fields_button.clicked.connect(
                    lambda: self.edit_view_fields(
                        current_fields, 
                        layer_name, 
                        edit_dialog, 
                        lambda new_fields: viewfields_editor.setText(json.dumps(new_fields, indent=2, ensure_ascii=False))
                    )
                )
                
                helper_layout.addWidget(select_fields_button)
                helper_layout.addStretch()
                
                # 補助ラベル
                help_label = QLabel("※「ViewFields」フィールドを直接編集するか、表示フィールド選択ウィザードを使用できます", edit_dialog)
                help_label.setStyleSheet("color: #555555; font-style: italic;")
                
                # レイアウトに追加
                layout.addLayout(helper_layout)
                layout.addWidget(help_label)
            
            # 区切り線
            separator = QFrame()
            # PyQt5/6両対応: HLine, Sunken
            hline = getattr(QFrame, 'HLine', getattr(QFrame, 'Shape', QFrame).HLine if hasattr(getattr(QFrame, 'Shape', QFrame), 'HLine') else 1)
            sunken = getattr(QFrame, 'Sunken', getattr(QFrame, 'Shadow', QFrame).Sunken if hasattr(getattr(QFrame, 'Shadow', QFrame), 'Sunken') else 2)
            separator.setFrameShape(hline)
            separator.setFrameShadow(sunken)
            layout.addWidget(separator)
            
            # 読み取り専用フィールドの前にスペースを追加
            row += 1
            
            # 読み取り専用フィールドがあれば、セクション区切りを追加
            if readonly_fields:
                separator = QFrame()
                hline = getattr(QFrame, 'HLine', getattr(QFrame, 'Shape', QFrame).HLine if hasattr(getattr(QFrame, 'Shape', QFrame), 'HLine') else 1)
                sunken = getattr(QFrame, 'Sunken', getattr(QFrame, 'Shadow', QFrame).Sunken if hasattr(getattr(QFrame, 'Shadow', QFrame), 'Sunken') else 2)
                separator.setFrameShape(hline)
                separator.setFrameShadow(sunken)
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
                    font = self.get_monospace_font()
                    if font is not None:
                        editor.setFont(font)
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
            def save_and_close():
                # すべてのエディタの内容をtab_configに反映し保存（selectThemeも含む）
                self.save_tab_config_by_fields(
                    editors,
                    readonly_fields,
                    edit_dialog, 
                    all_configs, 
                    tab_index_in_config, 
                    current_tab_title
                )
            save_button.clicked.connect(save_and_close)
            button_layout.addWidget(save_button)
            
            # キャンセルボタン
            cancel_button = QPushButton("キャンセル", edit_dialog)
            cancel_button.clicked.connect(edit_dialog.reject)
            button_layout.addWidget(cancel_button)
            
            layout.addLayout(button_layout)
            
            # ダイアログを表示
            try:
                import importlib
                qt_compat = importlib.import_module('geo_search.qt_compat')
            except Exception:
                qt_compat = None
            if qt_compat is not None:
                qt_compat.exec_dialog(edit_dialog)
            else:
                # fallback: try old call
                try:
                    edit_dialog.exec_()
                except Exception:
                    try:
                        edit_dialog.exec()
                    except Exception:
                        pass
            
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"edit_project_variable error: {e}", "GEO-search-plugin", 1)
            except Exception:
                print(f"edit_project_variable error: {e}")

    def _get_current_tab_info(self):
        """現在選択されているタブ情報を共通的に取得するヘルパー。

        戻り値: (current_tab, current_tab_title, current_tab_index, current_group_name, active_tabwidget, src_val, src_idx)
        - current_tab: QWidget (選択されたタブのウィジェット) または None
        - current_tab_title: タブの表示タイトル (str) または None
        - current_tab_index: 親のタブインデックス (int) または -1
        - current_group_name: 親グループ名 (str) または None
        - active_tabwidget: current_tab を含む QTabWidget (メインか子) または None
        - src_val: 推定されたソース文字列（例: 'geo_search_json' / 'setting.json' / 'project'）または None
        - src_idx: そのソース内でのインデックス（設定から取得できれば int、無ければ None）
        """
        current_tab = None
        current_tab_title = None
        current_tab_index = -1
        current_group_name = None
        active_tabwidget = None
        src_val = None
        src_idx = None

        try:
            # グループタブが存在するか
            if getattr(self, 'tab_groups', None):
                current_group_index = getattr(self.tabWidget, 'currentIndex', lambda: -1)()
                try:
                    current_group_name = self.tabWidget.tabText(current_group_index)
                except Exception:
                    current_group_name = None
                try:
                    current_group_widget = self.tabWidget.widget(current_group_index)
                except Exception:
                    current_group_widget = None

                if isinstance(current_group_widget, QTabWidget):
                    tab_index = current_group_widget.currentIndex()
                    if tab_index >= 0:
                        current_tab = current_group_widget.widget(tab_index)
                        current_tab_title = current_group_widget.tabText(tab_index)
                        current_tab_index = tab_index
                        active_tabwidget = current_group_widget
                else:
                    # グループページが QWidget コンテナで子 QTabWidget を含む場合のフォールバック
                    child_tabs = None
                    try:
                        if current_group_name and self.tab_groups and current_group_name in self.tab_groups:
                            child_tabs = self.tab_groups.get(current_group_name)
                    except Exception:
                        child_tabs = None

                    if child_tabs is None and hasattr(current_group_widget, 'findChild'):
                        try:
                            child_tabs = current_group_widget.findChild(QTabWidget)
                        except Exception:
                            child_tabs = None

                    if isinstance(child_tabs, QTabWidget):
                        tab_index = child_tabs.currentIndex()
                        if tab_index >= 0:
                            current_tab = child_tabs.widget(tab_index)
                            current_tab_title = child_tabs.tabText(tab_index)
                            current_tab_index = tab_index
                            active_tabwidget = child_tabs
            else:
                # 通常のタブ (グループなし)
                tab_index = self.tabWidget.currentIndex()
                if tab_index >= 0:
                    current_tab = self.tabWidget.widget(tab_index)
                    current_tab_title = self.tabWidget.tabText(tab_index)
                    current_tab_index = tab_index
                    active_tabwidget = self.tabWidget

            # Try to obtain explicit provenance from widget.setting if present
            try:
                if current_tab is not None and hasattr(current_tab, 'setting') and isinstance(current_tab.setting, dict):
                    src_val = current_tab.setting.get('_source')
                    src_idx = current_tab.setting.get('_source_index')
            except Exception:
                src_val = None
                src_idx = None

            # If no explicit provenance, attempt best-effort inference from QLabel children
            if not src_val and current_tab is not None and hasattr(current_tab, 'findChildren'):
                try:
                    from qgis.PyQt.QtWidgets import QLabel
                    import re
                    for lbl in current_tab.findChildren(QLabel):
                        try:
                            txt = (lbl.text() or '').strip()
                            if not txt:
                                continue
                            m = re.search(r"\[([^\]]+)\]", txt)
                            if m:
                                token = m.group(1)
                                if token and self._normalize_source(token):
                                    src_val = token
                                    break
                            low = txt.lower()
                            if 'geo' in low and 'search' in low:
                                src_val = txt
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

            # Normalize provenance token if present
            try:
                if src_val:
                    src_val = self._normalize_source(src_val)
            except Exception:
                # leave as-is when normalization fails
                pass

        except Exception:
            # 何か失敗しても呼び出し側でログを出せるよう None/デフォルトを返す
            current_tab = None
            current_tab_title = None
            current_tab_index = -1
            current_group_name = None
            active_tabwidget = None
            src_val = None
            src_idx = None

        return current_tab, current_tab_title, current_tab_index, current_group_name, active_tabwidget, src_val, src_idx
    
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

    def choose_save_target_dialog(self):
        """ユーザーに保存先を選ばせる（Project / setting.json / geo_search_json）。

        戻り値: 'project' | 'setting_json' | 'geo_search_json'
        """
        try:
            from qgis.PyQt.QtWidgets import QInputDialog
            items = [
                "geo_search_json (project-specified file)",
                "Project variable (GEO-search-plugin)",
                "Plugin setting.json",
            ]
            # default to project, but if geo_search_json is configured, prefer that
            default_index = 0
            try:
                import os
                from qgis.core import QgsProject, QgsExpressionContextUtils
                env_val = os.environ.get('geo_search_json')
                proj = QgsProject.instance()
                try:
                    pv = QgsExpressionContextUtils.projectScope(proj).variable('geo_search_json')
                except Exception:
                    pv = None
                if env_val or pv:
                    default_index = 2
            except Exception:
                default_index = 0

            try:
                raw = QInputDialog.getItem(self, self.tr("Choose save target"), self.tr("Select where to save new setting:"), items, default_index, False)
            except Exception:
                raw = None

            # Normalize returned value from QInputDialog.getItem across PyQt versions
            item = None
            ok = False
            try:
                if raw is None:
                    item = None
                    ok = False
                elif isinstance(raw, tuple) and len(raw) == 2:
                    a, b = raw
                    # Common cases: (item, ok) or (ok, item)
                    if isinstance(a, bool) and not isinstance(b, bool):
                        ok, item = a, b
                    elif isinstance(b, bool) and not isinstance(a, bool):
                        item, ok = a, b
                    else:
                        # Heuristic: check which element matches items
                        if isinstance(a, str) and a in items:
                            item, ok = a, b
                        elif isinstance(b, str) and b in items:
                            item, ok = b, a
                        else:
                            # Fallback: assume (item, ok)
                            item, ok = a, b
                else:
                    # Some bindings may return a single value or other form
                    if isinstance(raw, str) and raw in items:
                        item = raw
                        ok = True
                    else:
                        # Unknown format
                        item = None
                        ok = False
            except Exception:
                item = None
                ok = False

            # Log raw and normalized result to help debug selection issues
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"choose_save_target_dialog raw_return={repr(raw)} normalized=(item={repr(item)}, ok={ok})", "GEO-search-plugin", 0)
            except Exception:
                try:
                    print(f"choose_save_target_dialog raw_return={repr(raw)} normalized=(item={repr(item)}, ok={ok})")
                except Exception:
                    pass

            # If user cancelled or no selection, return None so caller can decide
            if not ok or not item:
                return None

            # Map selected item to internal code
            if item == items[0]:
                return 'geo_search_json'
            if item == items[1]:
                return 'project'
            if item == items[2]:
                return 'setting_json'
            return None
        except Exception:
            # On unexpected error showing the dialog, do not silently fallback;
            # return None so callers must handle the absence of a selection.
            return None

    def _write_to_setting_json(self, new_item_or_list):
        """Write new_item_or_list into plugin's `setting.json` (append into SearchTabs if present)."""
        try:
            plugin_dir = os.path.dirname(__file__)
            path = os.path.join(plugin_dir, 'setting.json')
            data = None
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as fh:
                        text = fh.read()
                    try:
                        # try strict JSON first
                        data = json.loads(text)
                    except Exception:
                        # fallback: some legacy setting.json files contain
                        # multiple top-level objects without an enclosing array.
                        # Try to wrap in [] and parse as array of objects so
                        # we can preserve and append to them instead of
                        # overwriting the file.
                        try:
                            data = json.loads(f'[{text}]')
                        except Exception:
                            data = None
                except Exception:
                    data = None

            # Normalize incoming
            if isinstance(new_item_or_list, list):
                incoming = new_item_or_list
            else:
                incoming = [new_item_or_list]

            if data is None:
                out = {'SearchTabs': incoming}
            else:
                if isinstance(data, dict) and isinstance(data.get('SearchTabs'), list):
                    data['SearchTabs'].extend(incoming)
                    out = data
                elif isinstance(data, list):
                    data.extend(incoming)
                    out = data
                else:
                    out = {'SearchTabs': []}
                    if isinstance(data, list):
                        out['SearchTabs'].extend(data)
                    else:
                        out['SearchTabs'].append(data)
                    out['SearchTabs'].extend(incoming)

            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(out, fh, ensure_ascii=False, indent=2)
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"Wrote settings to plugin setting.json: {path}", 'GEO-search-plugin', 0)
            except Exception:
                print(f"Wrote settings to plugin setting.json: {path}")
        except Exception as e:
            print(f"_write_to_setting_json error: {e}")
            QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to write to plugin setting.json: {0}").format(str(e)))

    def _save_to_setting_json(self, item_or_list):
        """Wrapper that writes to plugin setting.json and returns success boolean."""
        try:
            self._write_to_setting_json(item_or_list)
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"save_to_setting_json: wrote item", 'GEO-search-plugin', 0)
            except Exception:
                print("save_to_setting_json: wrote item")
            return True
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"save_to_setting_json error: {e}", 'GEO-search-plugin', 2)
            except Exception:
                print(f"save_to_setting_json error: {e}")
            try:
                QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to write to plugin setting.json: {0}").format(str(e)))
            except Exception:
                pass
            return False

    def _write_to_geo_search_json(self, new_item_or_list):
        """Write new_item_or_list into external file specified by env/project variable 'geo_search_json'."""
        try:
            # resolve path from env or project variable
            path = None
            try:
                path = os.environ.get('geo_search_json')
            except Exception:
                path = None
            try:
                from qgis.core import QgsProject, QgsExpressionContextUtils
                proj = QgsProject.instance()
                pv = QgsExpressionContextUtils.projectScope(proj).variable('geo_search_json')
                if pv:
                    path = pv
                # resolve relative to project dir if necessary
                try:
                    proj_file = proj.fileName() or ''
                    proj_dir = os.path.dirname(proj_file) if proj_file else ''
                except Exception:
                    proj_dir = ''
                if path and proj_dir and not os.path.isabs(path):
                    abs_path = os.path.join(proj_dir, path)
                    path = abs_path
            except Exception:
                pass

            if not path:
                # If no geo_search_json configured, create a default file
                # next to the current project with name <project>_search.json.
                try:
                    from qgis.core import QgsProject, QgsExpressionContextUtils, QgsMessageLog
                    proj = QgsProject.instance()
                    proj_file = proj.fileName() or ''
                    if proj_file:
                        proj_dir = os.path.dirname(proj_file)
                        proj_base = os.path.splitext(os.path.basename(proj_file))[0]
                        default_name = f"{proj_base}_search.json"
                        path = os.path.join(proj_dir, default_name)

                        # Persist the chosen path into project variable so next time
                        # the same location is used. Use the centralized helper for robustness.
                        try:
                            ok = set_project_variable(proj, 'geo_search_json', path)
                            if not ok:
                                try:
                                    from qgis.core import QgsMessageLog
                                    QgsMessageLog.logMessage(f"Failed to persist geo_search_json to project variables for path={path}", 'GEO-search-plugin', 1)
                                except Exception:
                                    print(f"Failed to persist geo_search_json to project variables for path={path}")
                        except Exception:
                            pass

                        try:
                            QgsMessageLog.logMessage(f"_write_to_geo_search_json: no path configured, using default {path}", 'GEO-search-plugin', 0)
                        except Exception:
                            print(f"_write_to_geo_search_json: no path configured, using default {path}")
                    else:
                        # Unsaved project: fallback to plugin directory
                        plugin_dir = os.path.dirname(__file__)
                        path = os.path.join(plugin_dir, 'untitled_search.json')
                        try:
                            QgsMessageLog.logMessage(f"_write_to_geo_search_json: unsaved project, using fallback {path}", 'GEO-search-plugin', 1)
                        except Exception:
                            print(f"_write_to_geo_search_json: unsaved project, using fallback {path}")
                except Exception:
                    # As a last resort, inform user and abort write
                    QMessageBox.warning(self, self.tr("geo_search_json"), self.tr("No geo_search_json path configured and failed to create default path."))
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage("_write_to_geo_search_json: no path configured and failed to create default", 'GEO-search-plugin', 2)
                    except Exception:
                        print("_write_to_geo_search_json: no path configured and failed to create default")
                    return

            # ensure directory exists
            d = os.path.dirname(path)
            if d:
                os.makedirs(d, exist_ok=True)

            data = None
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as fh:
                        data = json.load(fh)
                except Exception:
                    data = None

            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"_write_to_geo_search_json: resolved path={path} exists={os.path.exists(path)}", 'GEO-search-plugin', 0)
            except Exception:
                print(f"_write_to_geo_search_json: resolved path={path} exists={os.path.exists(path)}")

            if isinstance(new_item_or_list, list):
                incoming = new_item_or_list
            else:
                incoming = [new_item_or_list]

            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"_write_to_geo_search_json: incoming count={len(incoming)} sample={json.dumps(incoming[0], ensure_ascii=False) if incoming else '[]'}", 'GEO-search-plugin', 0)
            except Exception:
                print(f"_write_to_geo_search_json: incoming count={len(incoming)}")

            if data is None:
                out = {'SearchTabs': incoming}
            else:
                if isinstance(data, dict) and isinstance(data.get('SearchTabs'), list):
                    data['SearchTabs'].extend(incoming)
                    out = data
                elif isinstance(data, list):
                    data.extend(incoming)
                    out = data
                else:
                    out = {'SearchTabs': []}
                    if isinstance(data, list):
                        out['SearchTabs'].extend(data)
                    else:
                        out['SearchTabs'].append(data)
                    out['SearchTabs'].extend(incoming)

            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(out, fh, ensure_ascii=False, indent=2)
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"Wrote settings to geo_search_json file: {path} (items_written={len(out.get('SearchTabs') if isinstance(out, dict) and out.get('SearchTabs') else out if isinstance(out, list) else 1)})", 'GEO-search-plugin', 0)
            except Exception:
                print(f"Wrote settings to geo_search_json file: {path}")

        except Exception as e:
            print(f"_write_to_geo_search_json error: {e}")
            QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to write to geo_search_json file: {0}").format(str(e)))

    def _save_to_geo_search_json(self, item_or_list):
        """Wrapper that writes to geo_search_json (env/project) and returns success boolean."""
        try:
            self._write_to_geo_search_json(item_or_list)
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage("save_to_geo_search_json: wrote item", 'GEO-search-plugin', 0)
            except Exception:
                print("save_to_geo_search_json: wrote item")
            return True
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"save_to_geo_search_json error: {e}", 'GEO-search-plugin', 2)
            except Exception:
                print(f"save_to_geo_search_json error: {e}")
            try:
                QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to write to geo_search_json file: {0}").format(str(e)))
            except Exception:
                pass
            return False

    def _save_to_project_variable(self, project, new_value):
        """Wrapper that writes the given JSON text into project variable 'GEO-search-plugin'. Returns True on success."""
        try:
            ok = set_project_variable(project, 'GEO-search-plugin', new_value)
            if ok:
                try:
                    from qgis.core import QgsExpressionContextUtils, QgsMessageLog
                    read_back = QgsExpressionContextUtils.projectScope(project).variable('GEO-search-plugin')
                    QgsMessageLog.logMessage(f"_save_to_project_variable: wrote project variable: {str(read_back)}", 'GEO-search-plugin', 0)
                except Exception:
                    pass
                return True
            else:
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage("_save_to_project_variable: set_project_variable returned False", 'GEO-search-plugin', 1)
                except Exception:
                    print("_save_to_project_variable: set_project_variable returned False")
                try:
                    QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to write project variable 'GEO-search-plugin'."))
                except Exception:
                    pass
                return False
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"_save_to_project_variable error: {e}", 'GEO-search-plugin', 2)
            except Exception:
                print(f"_save_to_project_variable error: {e}")
            try:
                QMessageBox.warning(self, self.tr("Error"), self.tr("Failed to write project variable 'GEO-search-plugin': {0}").format(str(e)))
            except Exception:
                pass
            return False
    
    def edit_view_fields(self, current_fields, layer_name, dialog, callback):
        """ViewFieldsを編集するためのダイアログを表示する"""
        try:
            # レイヤーを取得
            layer = None
            project = QgsProject.instance()
            # QGIS 3.40+ では mapLayersByName を優先利用
            candidates = project.mapLayersByName(layer_name)
            if candidates:
                layer = candidates[0]
            
            # レイヤーの属性を取得
            available_fields = []  # リストの各要素は (field_name, display_name) のタプル
            field_aliases = {}     # フィールド名と別名の辞書
            
            if layer:
                for field in layer.fields():
                    field_name = field.name()
                    field_alias = field.alias() or field_name  # エイリアスがなければ名前を使用
                    
                    # フィールド名と表示名（フィールド名 - エイリアス）のタプルを保存
                    if field_alias != field_name and field_alias:
                        display_name = f"{field_name} - {field_alias}"
                    else:
                        display_name = field_name
                        
                    available_fields.append((field_name, display_name))
                    field_aliases[field_name] = field_alias
            else:
                # レイヤーが見つからない場合、現在のフィールドを使用
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"レイヤー '{layer_name}' が見つかりません。現在のフィールドを使用します。", "GEO-search-plugin", 1)
                except Exception:
                    print(f"レイヤー '{layer_name}' が見つかりません。現在のフィールドを使用します。")
                
                # 現在のフィールドが空でない場合は使用
                if isinstance(current_fields, list) and current_fields:
                    available_fields = [(field, field) for field in current_fields]
            
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
            for field_name, display_name in available_fields:
                checkbox = QCheckBox(display_name, scroll_content)
                # 現在選択されているフィールドはチェックを入れる
                if isinstance(current_fields, list) and field_name in current_fields:
                    checkbox.setChecked(True)
                scroll_layout.addWidget(checkbox)
                checkboxes[field_name] = checkbox  # キーはフィールド名、値はチェックボックス
            
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
            try:
                import importlib
                qt_compat = importlib.import_module('geo_search.qt_compat')
            except Exception:
                qt_compat = None
            if qt_compat is not None:
                qt_compat.exec_dialog(fields_dialog)
            else:
                try:
                    fields_dialog.exec_()
                except Exception:
                    try:
                        fields_dialog.exec()
                    except Exception:
                        pass
            
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"edit_view_fields error: {e}", "GEO-search-plugin", 1)
            except Exception:
                print(f"edit_view_fields error: {e}")
            QMessageBox.warning(dialog, "エラー", f"表示フィールドの編集中にエラーが発生しました:\n{str(e)}")
            
    def edit_search_field(self, current_search_field, layer_name, dialog, callback):
        """SearchFieldを編集するためのダイアログを表示する"""
        try:
            # レイヤーを取得
            layer = None
            project = QgsProject.instance()
            # QGIS 3.40+ では mapLayersByName を優先利用
            candidates = project.mapLayersByName(layer_name)
            if candidates:
                layer = candidates[0]
            
            # 利用可能なフィールドを取得
            available_fields = []  # リストの各要素は (field_name, display_name) のタプル
            field_aliases = {}     # フィールド名と別名の辞書
            
            if layer:
                for field in layer.fields():
                    field_name = field.name()
                    field_alias = field.alias() or field_name  # エイリアスがなければ名前を使用
                    
                    # フィールド名と表示名（フィールド名 - エイリアス）のタプルを保存
                    if field_alias != field_name and field_alias:
                        display_name = f"{field_name} - {field_alias}"
                    else:
                        display_name = field_name
                        
                    available_fields.append((field_name, display_name))
                    field_aliases[field_name] = field_alias
            else:
                # レイヤーが見つからない場合は、現在のフィールドから取得
                if isinstance(current_search_field, dict) and current_search_field:
                    # 既存のSearchField構造からフィールド名を抽出
                    for key in current_search_field:
                        if key != "ViewName" and key != "all":  # 特殊キーを除外
                            available_fields.append((key, key))  # 別名情報がないのでフィールド名のみ
                
            # All フィールドを先頭に追加
            available_fields.insert(0, ("全フィールド検索", "全フィールド検索"))
            
            # ダイアログを作成
            fields_dialog = QDialog(dialog)
            fields_dialog.setWindowTitle(f"検索フィールドの選択: {layer_name}")
            fields_dialog.setMinimumSize(400, 300)
            
            layout = QVBoxLayout(fields_dialog)
            
            # 説明ラベル
            info_label = QLabel("検索に使用するフィールドを選択してください（複数選択可 - OR検索）:", fields_dialog)
            layout.addWidget(info_label)
            
            # スクロールエリア
            scroll_area = QScrollArea(fields_dialog)
            scroll_area.setWidgetResizable(True)
            scroll_content = QWidget(scroll_area)
            scroll_layout = QVBoxLayout(scroll_content)
            
            # チェックボックス（複数選択可能）
            checkboxes = {}  # フィールド名とチェックボックスのマッピングを保持
            all_checkbox = None  # 「全フィールド検索」のチェックボックス
            
            for i, (field_name, display_name) in enumerate(available_fields):
                checkbox = QCheckBox(display_name, scroll_content)
                
                # 現在の設定と一致するフィールドを選択状態にする
                if i == 0:  # 「全フィールド検索」の場合
                    all_checkbox = checkbox  # 「全フィールド検索」のチェックボックスを保持
                    if isinstance(current_search_field, dict) and not current_search_field:
                        # 空のオブジェクトは「全フィールド検索」
                        checkbox.setChecked(True)
                    elif isinstance(current_search_field, dict) and current_search_field.get("all"):
                        # "all": true がある場合も「全フィールド検索」
                        checkbox.setChecked(True)
                else:
                    # 特定のフィールド検索の場合
                    if isinstance(current_search_field, dict) and field_name in current_search_field:
                        checkbox.setChecked(True)
                
                # 「全フィールド検索」と他のチェックボックスの排他制御
                if i == 0:
                    # 「全フィールド検索」がチェックされたら他のチェックボックスを無効化
                    checkbox.stateChanged.connect(lambda state, cb=checkbox: self._toggle_other_checkboxes(cb, checkboxes))
                else:
                    # 他のチェックボックスがチェックされたら「全フィールド検索」のチェックを外す
                    checkbox.stateChanged.connect(lambda state, cb=checkbox, ac=all_checkbox: self._uncheck_all_checkbox(cb, ac))
                
                checkboxes[field_name] = checkbox
                scroll_layout.addWidget(checkbox)
            
            # 空きスペースを追加
            scroll_layout.addStretch(1)
            
            scroll_content.setLayout(scroll_layout)
            scroll_area.setWidget(scroll_content)
            layout.addWidget(scroll_area)
            
            # ボタン配置
            button_layout = QHBoxLayout()
            
            # 保存ボタン
            save_button = QPushButton("保存", fields_dialog)
            save_button.clicked.connect(lambda: self._save_search_field(checkboxes, available_fields, field_aliases, fields_dialog, callback))
            button_layout.addWidget(save_button)
            
            # キャンセルボタン
            cancel_button = QPushButton("キャンセル", fields_dialog)
            cancel_button.clicked.connect(fields_dialog.reject)
            button_layout.addWidget(cancel_button)
            
            layout.addLayout(button_layout)
            
            # ダイアログを表示
            try:
                import importlib
                qt_compat = importlib.import_module('geo_search.qt_compat')
            except Exception:
                qt_compat = None
            if qt_compat is not None:
                qt_compat.exec_dialog(fields_dialog)
            else:
                try:
                    fields_dialog.exec_()
                except Exception:
                    try:
                        fields_dialog.exec()
                    except Exception:
                        pass
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"edit_search_field error: {e}", "GEO-search-plugin", 1)
            except Exception:
                print(f"edit_search_field error: {e}")
            QMessageBox.warning(dialog, "エラー", f"検索フィールドの編集中にエラーが発生しました:\n{str(e)}")
    
    def _save_search_field(self, checkboxes, available_fields, field_aliases, dialog, callback):
        """選択された検索フィールドを保存する（複数選択対応）"""
        try:
            # チェックされているフィールドを取得
            selected_fields = []
            for field_name, checkbox in checkboxes.items():
                if checkbox.isChecked():
                    selected_fields.append(field_name)

            # 選択がない場合は全フィールド検索
            if not selected_fields:
                search_field = {"FieldType": "Text"}
            elif "全フィールド検索" in selected_fields:
                # 「全フィールド検索」が選択されている場合
                search_field = {"FieldType": "Text", "ViewName": "All", "all": True}
            else:
                # 複数または単一フィールドが選択されている場合
                search_field = {"FieldType": "Text"}

                # ViewName は最初に選択されたフィールドの別名を使用
                first_field = selected_fields[0]
                if first_field in field_aliases and field_aliases[first_field] != first_field:
                    view_name = field_aliases[first_field]  # 別名をViewNameに使用
                else:
                    view_name = first_field  # 別名がなければフィールド名を使用

                # 複数選択の場合、ViewNameを「OR検索」にし、フィールド名も表示
                if len(selected_fields) > 1:
                    # フィールド名を集約（最大3つまで表示）
                    display_fields = selected_fields[:3]
                    field_display = ", ".join(display_fields)
                    if len(selected_fields) > 3:
                        field_display += f" 他{len(selected_fields)-3}個"
                    view_name = f"OR検索: {field_display}"

                search_field["ViewName"] = view_name

                # 選択されたフィールドをカンマ区切りで1つのキーにまとめる
                search_field["Field"] = ", ".join(selected_fields)
            
            # コールバック関数を呼び出して結果を返す
            callback(search_field)
            
            # ダイアログを閉じる
            dialog.accept()
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"_save_search_field error: {e}", "GEO-search-plugin", 1)
            except Exception:
                print(f"_save_search_field error: {e}")
            QMessageBox.warning(dialog, "エラー", f"検索フィールドの保存中にエラーが発生しました:\n{str(e)}")
    
    def _toggle_other_checkboxes(self, all_checkbox, checkboxes):
        """「全フィールド検索」チェックボックスが選択された時、他のチェックボックスを無効化する"""
        try:
            is_checked = all_checkbox.isChecked()
            # 「全フィールド検索」以外のチェックボックスを全て無効化/有効化
            for field_name, checkbox in checkboxes.items():
                if field_name != "全フィールド検索":
                    if is_checked:
                        # 「全フィールド検索」がチェックされたら他のチェックを外して無効化
                        checkbox.setChecked(False)
                        checkbox.setEnabled(False)
                    else:
                        # 「全フィールド検索」のチェックが外れたら他のを有効化
                        checkbox.setEnabled(True)
        except Exception as e:
            print(f"_toggle_other_checkboxes error: {e}")
    
    def _uncheck_all_checkbox(self, field_checkbox, all_checkbox):
        """個別のフィールドチェックボックスがチェックされた時、「全フィールド検索」のチェックを外す"""
        try:
            if field_checkbox.isChecked() and all_checkbox and all_checkbox.isChecked():
                # シグナルの再帰を防ぐためにブロックしてから状態変更
                all_checkbox.blockSignals(True)
                all_checkbox.setChecked(False)
                all_checkbox.blockSignals(False)
        except Exception as e:
            print(f"_uncheck_all_checkbox error: {e}")
    
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
                if field_name == "selectTheme":
                    # QComboBoxまたはQLineEdit対応
                    try:
                        if editor is None:
                            tab_config[field_name] = ""
                        elif hasattr(editor, "currentText"):
                            val = editor.currentText()
                            tab_config[field_name] = val.strip() if val else ""
                        else:
                            txt = editor.text() if hasattr(editor, 'text') else ''
                            tab_config[field_name] = txt.strip()
                    except Exception as e:
                        try:
                            from qgis.core import QgsMessageLog
                            QgsMessageLog.logMessage(f"save_tab_config_by_fields: selectTheme read error: {e}", "GEO-search-plugin", 1)
                        except Exception:
                            pass
                        tab_config[field_name] = ""
                elif field_name == "angle":
                    # editor may be a tuple (spin, checkbox) to support 'unspecified'
                    try:
                        # editor may be a tuple (spin, checkbox) or (spin, checkbox, button)
                        if isinstance(editor, tuple) and len(editor) >= 2:
                            spin_box = editor[0]
                            checkbox = editor[1]
                            try:
                                if checkbox.isChecked():
                                    tab_config[field_name] = None
                                else:
                                    tab_config[field_name] = float(spin_box.value())
                            except Exception:
                                tab_config[field_name] = None
                        else:
                            if hasattr(editor, 'value'):
                                tab_config[field_name] = float(editor.value())
                            else:
                                tab_config[field_name] = float(editor.toPlainText())
                    except Exception:
                        tab_config[field_name] = None
                elif field_name == "scale":
                    # editor may be a tuple (spin, checkbox) to support 'unspecified'
                    try:
                        if isinstance(editor, tuple) and len(editor) >= 2:
                            spin_box = editor[0]
                            checkbox = editor[1]
                            try:
                                if checkbox.isChecked():
                                    tab_config[field_name] = None
                                else:
                                    tab_config[field_name] = float(spin_box.value())
                            except Exception:
                                tab_config[field_name] = None
                        else:
                            if hasattr(editor, 'value'):
                                tab_config[field_name] = float(editor.value())
                            else:
                                tab_config[field_name] = float(editor.toPlainText())
                    except Exception:
                        tab_config[field_name] = None
                else:
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
                
            # ユーザーが入力したタイトルをそのまま使用する
            # (タイトル変更を許可するため、タイトル修正の処理を削除)
                
            # ViewFieldsはすでに編集可能フィールドとして処理されているため、
            # 特別な処理は必要ありません
            
            # バリデーション: angle が存在する場合は範囲内に収める（JSON直接編集でも安全に）
            try:
                if 'angle' in tab_config and tab_config.get('angle') is not None:
                    try:
                        a = float(tab_config.get('angle'))
                        # clamp to [-360, 360]
                        if a < -360.0:
                            a = -360.0
                        if a > 360.0:
                            a = 360.0
                        tab_config['angle'] = a
                    except Exception:
                        # if not numeric, treat as unspecified
                        tab_config['angle'] = None
            except Exception:
                pass

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
                
                # ユーザーが入力したタイトルをそのまま使用する
                # (タイトル変更を許可するため、タイトル修正の処理を削除)
                    
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
            
            # Ask user where to save the updated configuration
            try:
                save_target = self.choose_save_target_dialog()
            except Exception:
                # dialog failed to open; treat as no selection
                save_target = None

            try:
                # If user cancelled/no selection, abort save and keep edit dialog open
                if save_target is None:
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage("No save target selected; aborting update_config_and_save", "GEO-search-plugin", 0)
                    except Exception:
                        print("No save target selected; aborting update_config_and_save")
                    # Inform the user
                    try:
                        QMessageBox.information(dialog, self.tr("Save cancelled"), self.tr("No save target selected. The configuration was not saved."))
                    except Exception:
                        pass
                    return

                if save_target == 'project':
                    # Use centralized helper to persist project-scoped setting
                    try:
                        ok = self._save_to_project_variable(project, new_value)
                        if not ok:
                            try:
                                from qgis.core import QgsMessageLog
                                QgsMessageLog.logMessage("set_project_variable returned False when writing GEO-search-plugin", "GEO-search-plugin", 1)
                            except Exception:
                                print("set_project_variable returned False when writing GEO-search-plugin")
                        else:
                            try:
                                from qgis.core import QgsExpressionContextUtils, QgsMessageLog
                                read_back = QgsExpressionContextUtils.projectScope(project).variable('GEO-search-plugin')
                                QgsMessageLog.logMessage(f"Updated project variable via helper: {str(read_back)}", "GEO-search-plugin", 0)
                            except Exception:
                                pass
                    except Exception as err:
                        try:
                            from qgis.core import QgsMessageLog
                            QgsMessageLog.logMessage(f"Error while persisting via set_project_variable: {err}", "GEO-search-plugin", 1)
                        except Exception:
                            print(f"Error while persisting via set_project_variable: {err}")
                elif save_target == 'setting_json':
                    try:
                        self._write_to_setting_json(all_configs)
                    except Exception as e:
                        print(f"Failed to write to setting.json: {e}")
                elif save_target == 'geo_search_json':
                    try:
                        self._write_to_geo_search_json(all_configs)
                    except Exception as e:
                        print(f"Failed to write to geo_search_json file: {e}")
                else:
                    try:
                        ok = self._save_to_project_variable(project, new_value)
                        if not ok:
                            try:
                                from qgis.core import QgsMessageLog
                                QgsMessageLog.logMessage("set_project_variable returned False when writing GEO-search-plugin (update flow)", "GEO-search-plugin", 1)
                            except Exception:
                                print("set_project_variable returned False when writing GEO-search-plugin (update flow)")
                    except Exception as e:
                        try:
                            from qgis.core import QgsMessageLog
                            QgsMessageLog.logMessage(f"Error while persisting via set_project_variable (update flow): {e}", "GEO-search-plugin", 1)
                        except Exception:
                            print(f"Error while persisting via set_project_variable (update flow): {e}")

            except Exception as e:
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"Failed to save configuration to chosen target: {e}", "GEO-search-plugin", 1)
                except Exception:
                    print(f"Failed to save configuration to chosen target: {e}")

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
