# -*- coding: utf-8 -*-
import os

import psycopg2
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QCompleter, QDialog, QMessageBox, QTableWidgetItem
from qgis.core import (
    QgsApplication,
    QgsDataSourceUri,
    QgsVectorLayer,
    QgsFeatureRequest,
    QgsExpression,
    QgsProject,
    QgsTask,
)
from . import jaconv

from .resultdialog import ResultDialog
from .utils import name2layer, unique_values, get_feature_by_id


class SearchFeature(object):

    @property
    def layer(self):
        # レイヤ指定がなければ常に最新のカレントレイヤを返す
        if not hasattr(self, '_layer_setting') or not self._layer_setting:
            return self.iface.activeLayer()
        return self.load_layer(self._layer_setting)
    def __init__(self, iface, setting, widget, andor=" And ", page_limit=1000):
        self.iface = iface
        self.setting = setting
        self.fields = setting.get("SearchFields", [setting.get("SearchField")])
        self.title = setting["Title"]
        self.view_fields = setting.get("ViewFields", [])
        self.sample_fields = setting.get("SampleFields", [])
        self._layer_setting = setting.get("Layer")
        if self._layer_setting and isinstance(self._layer_setting, dict):
            self.layer_type = self._layer_setting.get("LayerType")
            self.layer_name = self._layer_setting.get("Name")
        else:
            self.layer_type = None
            self.layer_name = None
        self.message = setting.get("Message")
        self.suggest_flg = setting.get("Suggest", False)

        self.widget = widget
        self.features = []
        self.data_role = 15
        self.andor = andor
        self.result_dialog = ResultDialog(widget.parent(), page_limit=page_limit)
        # Connect to dialog-level signals (ResultDialog forwards table signals)
        try:
            self.result_dialog.selectionChanged.connect(self.zoom_items)
            self.result_dialog.itemPressed.connect(self.zoom_items)
        except Exception:
            # fallback to legacy table widget signals if necessary
            try:
                self.result_dialog.tableWidget.itemSelectionChanged.connect(self.zoom_items)
                self.result_dialog.tableWidget.itemPressed.connect(self.zoom_items)
            except Exception:
                pass

        self.sample_table_task = None
        # 検索ウィジェットは常に有効化（カレントレイヤがNoneでも入力可能にする）
        self.widget.setEnabled(True)


    @property
    def view_fields(self):
        layer = self.layer
        if not layer:
            return []
        layer_fields = [field for field in layer.fields()]
        if not self.__view_fields:
            return layer_fields
        fields = layer.fields()
        setting_fields = [fields.indexFromName(field) for field in self.__view_fields]
        return [
            layer_fields[fid] for fid in setting_fields if fid != -1
        ] or layer_fields

    @view_fields.setter
    def view_fields(self, fields):
        self.__view_fields = fields

    @property
    def sample_fields(self):
        layer = self.layer
        if not layer:
            return []
        layer_fields = [field for field in layer.fields()]
        if not self.__sample_fields:
            return layer_fields
        fields = layer.fields()
        setting_fields = [fields.indexFromName(field) for field in self.__sample_fields]
        return [
            layer_fields[fid] for fid in setting_fields if fid != -1
        ] or layer_fields

    @sample_fields.setter
    def sample_fields(self, fields):
        self.__sample_fields = fields

    def load_layer(self, setting):
        # レイヤ設定がなければカレントレイヤを返す
        if not setting or not isinstance(setting, dict) or not setting.get("LayerType"):
            # iface.activeLayer() でカレントレイヤ取得
            return self.iface.activeLayer()
        layer_type = setting["LayerType"]
        layer_name = setting.get("Name")
        if layer_type == "Name":
            return name2layer(layer_name)
        return self.create_layer(setting)

    def create_layer(self, setting):
        # FIXME: 読み込み失敗の対処
        layer = None
        layer_type = setting["LayerType"]
        if layer_type == "File":
            path = setting["Path"]
            project = QgsProject.instance()
            directory = os.path.dirname(project.fileName())
            if directory:
                path = os.path.abspath(os.path.join(directory, path))
            name, ext = os.path.splitext(os.path.basename(path))
            layer = QgsVectorLayer(path, name, "ogr")

            encoding = setting.get("Encoding")
            if encoding:
                layer.setProviderEncoding(encoding)
        elif layer_type == "Database":
            uri = QgsDataSourceUri()
            host = setting.get("Host")
            port = setting.get("Port")
            database = setting.get("Database")
            user = setting.get("User")
            password = setting.get("Password")
            table = setting.get("Table")
            uri.setConnection(host, port, database, user, password)
            uri.setDataSource(setting.get("Schema"), table, setting.get("Geometry"))
            uri.setKeyColumn(setting.get("Key"))
            if setting.get("DataType") == "postgres":
                if not self.format_table(
                    host, port, database, user, password, sql=setting.get("FormatSQL")
                ):
                    return

            layer = QgsVectorLayer(uri.uri(), table, setting.get("DataType"))
        return layer

    def format_table(self, host, port, database, user, password, sql=None):
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                connect_timeout=1,
            )
            cursor = conn.cursor()
            if sql:
                sql = os.path.join(os.path.dirname(__file__), sql)
                with open(sql) as f:
                    query = f.read()

                cursor.execute(query)
                conn.commit()
            cursor.close()
            conn.close()

        except psycopg2.OperationalError:
            return False
        except psycopg2.errors.SyntaxError:
            return False
        return True

    def load(self):
        raise NotImplementedError

    def unload(self):
        raise NotImplementedError

    def search_feature(self):
        raise NotImplementedError
    
    def normalize_search_value(self, value):
        """検索値を正規化する（全角英数字を半角に変換）"""
        if not value:
            return value
        
        try:
            # jaconvを使用して全角英数字を半角に変換
            # ascii=True: 全角ASCII文字を半角に変換
            # digit=True: 全角数字を半角に変換
            # kana=False: カナ変換は行わない（速度優先）
            normalized = jaconv.z2h(value, ascii=True, digit=True, kana=False)
            
            # ログ出力（デバッグ用、変換があった場合のみ）
            if normalized != value:
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"検索値正規化: '{value}' -> '{normalized}'", "GEO-search-plugin", 0)
                except Exception:
                    pass
            
            return normalized
        except Exception as e:
            # 変換に失敗した場合は元の値を返す
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"検索値正規化エラー: {e}", "GEO-search-plugin", 1)
            except Exception:
                pass
            return value

    def show_message(self):
        window = self.widget.parent()
        QMessageBox.information(self.widget, window.windowTitle(), self.message)

    def open_feature_form(self, item):
        if not item:
            return
        feature_id = item.data(self.data_role)
        feature = get_feature_by_id(self.layer, feature_id)
        self.iface.openFeatureForm(self.layer, feature)

    def zoom_item(self, item):
        """クリックした地物アイテムの座標にズームする"""
        if not item:
            return
        value = item.data(self.data_role)
        self.zoom_features([value])

    def zoom_items(self, item=None):
        # support tabbed tables: prefer dialog's current_table if present
        table = getattr(self.result_dialog, 'current_table', None) or getattr(self.result_dialog, 'tableWidget', None)
        if table is None:
            return
        # if this was called from an itemPressed signal, an item may be provided
        if item is not None:
            try:
                fid = item.data(self.data_role)
                from qgis.core import QgsMessageLog
                layer_name = (getattr(table, 'parent', lambda: None)() and getattr(self.result_dialog._tabs[self.result_dialog.tabWidget.currentIndex()], 'get', lambda *a, **k: None)('layer'))
                QgsMessageLog.logMessage(f"zoom_items (itemPressed): item fid={fid} on layer={layer_name}", "GEO-search-plugin", 0)
            except Exception:
                pass
            # determine target layer for current tab
            try:
                idx = getattr(self.result_dialog, 'tabWidget', None).currentIndex()
                tab = self.result_dialog._tabs[idx]
                layer = tab.get('layer') or self.layer
            except Exception:
                layer = self.layer

            self.zoom_features([fid], layer=layer)
            return

        items = table.selectedItems()
        # determine the layer associated with the currently visible tab (if available)
        layer = None
        try:
            idx = getattr(self.result_dialog, 'tabWidget', None).currentIndex()
            tab = self.result_dialog._tabs[idx]
            layer = tab.get('layer') or self.layer
        except Exception:
            layer = self.layer

        ids = [item.data(self.data_role) for item in items]
        # if no items returned (depends on selection mode), try to gather ids by selected rows/indexes
        if not ids:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage("zoom_items: selectedItems() returned empty, trying selectedIndexes/currentRow fallback", "GEO-search-plugin", 0)
            except Exception:
                pass
            rows = set()
            try:
                indexes = table.selectedIndexes()
                for idx in indexes:
                    rows.add(idx.row())
            except Exception:
                # fallback to currentRow
                try:
                    r = table.currentRow()
                    if r is not None and r >= 0:
                        rows.add(r)
                except Exception:
                    rows = set()

            # collect ids from first non-empty column cell in each row
            for r in sorted(rows):
                cols = table.columnCount()
                fid = None
                for c in range(cols):
                    try:
                        it = table.item(r, c)
                        if it is not None:
                            v = it.data(self.data_role)
                            if v is not None:
                                fid = v
                                break
                    except Exception:
                        continue
                if fid is not None:
                    ids.append(fid)
        try:
            # log selection and target layer
            from qgis.core import QgsMessageLog
            layer_name = layer.name() if layer is not None else 'None'
            QgsMessageLog.logMessage(f"zoom_items: selected {len(ids)} items on layer={layer_name}, ids={ids}", "GEO-search-plugin", 0)
        except Exception:
            pass

        self.zoom_features(ids, layer=layer)

    def zoom_features(self, feature_ids=None, layer=None):
        """検索結果にズーム。feature_ids はシーケンス。layer を指定するとそのレイヤで選択・ズームする。"""
    # resolve feature ids
        if feature_ids is None:
            try:
                feature_ids = list(self.result_features.keys())
            except Exception:
                feature_ids = []

        # normalize ids to ints and remove duplicates
        ids = []
        for fid in feature_ids:
            try:
                i = int(fid)
            except Exception:
                continue
            if i not in ids:
                ids.append(i)

        if not ids:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage("zoom_features: no valid feature ids to zoom", "GEO-search-plugin", 0)
            except Exception:
                pass
            return

        # resolve layer to operate on
        target_layer = layer or self.layer
        if not target_layer:
            return

        try:
            from qgis.core import QgsMessageLog
            layer_name = getattr(target_layer, 'name', lambda: 'Unknown')()
            QgsMessageLog.logMessage(f"zoom_features: attempting selectByIds on layer={layer_name} ids={ids}", "GEO-search-plugin", 0)
            target_layer.selectByIds(ids)
            self.iface.mapCanvas().zoomToSelected(target_layer)
            QgsMessageLog.logMessage(f"zoom_features: zoomed to selected on layer={layer_name}", "GEO-search-plugin", 0)
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"zoom_features: failed to zoom on layer={getattr(target_layer, 'name', lambda: 'Unknown')()} ids={ids} error={e}", "GEO-search-plugin", 0)
            except Exception:
                pass
            return

    def show_features(self):
        """検索結果を表示する"""
        # マップテーマ（Map Theme）APIでテーマ一覧取得・切り替え
        try:
            from qgis.core import QgsMessageLog, QgsProject
            project = QgsProject.instance()
            theme_collection = project.mapThemeCollection()
            themes = theme_collection.mapThemes()
            # JSON設定からテーマ名を取得（なければNone）
            theme_name = self.setting.get("selectTheme")
            
            # 適用するテーマ名を決定
            apply_theme_name = None
            if theme_name and theme_name in themes:
                # 設定で指定されたテーマを使用
                apply_theme_name = theme_name
            elif "検索前" in themes:
                # 「検索前」テーマを使用
                apply_theme_name = "検索前"
            
            # テーマを適用
            if apply_theme_name:
                root = project.layerTreeRoot()
                model = self.iface.layerTreeView().layerTreeModel()
                theme_collection.applyTheme(apply_theme_name, root, model)
                QgsMessageLog.logMessage(f"テーマ '{apply_theme_name}' を適用しました", "GEO-search-plugin", 0)
            elif theme_name:
                QgsMessageLog.logMessage(f"テーマ '{theme_name}' が見つかりません", "GEO-search-plugin", 1)
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"テーマ適用エラー: {str(e)}", "GEO-search-plugin", 2)
            except Exception:
                pass
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"マップテーマAPIエラー: {str(e)}", "GEO-search-plugin", 2)
            except Exception:
                pass
        if not self.layer:
            return
        features = self.search_feature()
        # Always present results as per-layer tabs, even for single (current) layer
        try:
            self.result_dialog.set_features_by_layer([(self.layer, self.view_fields, features)])
        except Exception:
            # fallback to legacy single-table API
            self.result_dialog.set_features(self.view_fields, features)
        self.result_dialog.show()

        # 検索後にレイヤテーマ"test"へ切り替え（後処理）
        try:
            from qgis.PyQt.QtWidgets import QApplication
            QgsProject.instance().layerTreeRoot().readLayerVisibilityPreset("test")
            QApplication.processEvents()
        except Exception:
            pass

    def get_visible_vector_layers(self):
        """現在マップ上で表示されているベクタレイヤ一覧を返す"""
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        layers = []
        # iterate layer-tree nodes so the same layer referenced by multiple nodes
        # is seen once per node (preserve duplicates from the tree)
        try:
            nodes = root.findLayers()
        except Exception:
            nodes = []

        for node in nodes:
            try:
                if not node.isVisible():
                    continue
                layer = node.layer()
                if layer is None:
                    continue
                if isinstance(layer, QgsVectorLayer):
                    # return tuple (node, layer) so callers can distinguish nodes
                    layers.append((node, layer))
            except Exception:
                continue

        return layers

    def get_all_vector_layers(self):
        """プロジェクト内の全てのベクタレイヤを返す"""
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        layers = []
        try:
            nodes = root.findLayers()
        except Exception:
            nodes = []

        for node in nodes:
            try:
                layer = node.layer()
                if layer is None:
                    continue
                if isinstance(layer, QgsVectorLayer):
                    layers.append((node, layer))
            except Exception:
                continue

        return layers

    def add_search_task(self):
        task = QgsTask.fromFunction(
            "地図検索",
            self.search_task,
            on_finished=self.search_finished,
        )

        QgsApplication.taskManager().addTask(task)
        self.sample_table_task = task

    def search_task(self, task):
        """検索最中に検索テーブルを更新する"""
        try:
            features = self.search_feature()
        except:
            features = []
        return features

    def search_finished(self, exception, result=None):
        if result is None:
            result = []
        # show results as per-layer tab(s)
        try:
            self.result_dialog.set_features_by_layer([(self.layer, self.view_fields, result)])
        except Exception:
            self.result_dialog.set_features(self.view_fields, result)


# "通常の検索"
class SearchTextFeature(SearchFeature):
    def load(self):
        if self.suggest_flg:
            self.set_suggest()

    def unload(self):
        pass

    def set_suggest(self):
        """サジェスト表示"""
        layer = self.layer
        if not layer:
            return

        for field, search_widget in zip(self.fields, self.widget.search_widgets):
            field_name = field["Field"]
            suggest_list = map(str, unique_values(layer, field_name))
            comp = QCompleter(suggest_list)
            search_widget.setCompleter(comp)

    def search_feature(self, limit=None):
        layer = self.layer
        if not layer:
            return []
        
        from qgis.core import QgsMessageLog
        
        # 検索値を取得して正規化
        search_value = None
        for widget in self.widget.search_widgets:
            value = widget.text()
            if value:
                search_value = self.normalize_search_value(value)
                break
        
        if not search_value:
            return []  # 検索値がなければ何も返さない
        
        # 検索対象のフィールドを特定
        target_fields = self._get_target_fields()
        
        if not target_fields:
            try:
                QgsMessageLog.logMessage(f"検索条件なし: fields={self.fields}", "GEO-search-plugin", 0)
            except Exception:
                pass
            return []
        
        # 検索条件を構築
        expres_list = []
        for field_name in target_fields:
            expres_list.append('"{field}" LIKE \'%{value}%\''.format(field=field_name, value=search_value))
        
        try:
            QgsMessageLog.logMessage(f"search_feature: search with fields={target_fields}, value={search_value}", "GEO-search-plugin", 0)
            QgsMessageLog.logMessage(f"検索式: expres_list={expres_list}", "GEO-search-plugin", 0)
        except Exception:
            pass
        
        # クエリを実行
        expression_str = self.andor.join(expres_list)
        expression = QgsExpression(expression_str)
        
        if expression.hasEvalError():
            try:
                QgsMessageLog.logMessage(f"[ERROR] Expression error: {expression.evalErrorString()}", "GEO-search-plugin", 1)
            except Exception:
                pass
            return []
        
        request = QgsFeatureRequest(expression)
        if limit:
            request.setLimit(limit)
        
        features = list(layer.getFeatures(request))
        return features
        
    def _get_target_fields(self):
        """検索対象のフィールドを特定する"""
        target_fields = []
        
        for field, search_widget in zip(self.fields, self.widget.search_widgets):
            # skip invalid field entries
            if not isinstance(field, dict):
                continue
            
            # 空dict（全フィールド検索）の場合は文字列フィールドを全て対象にする
            if field == {}:
                if search_widget.text():  # 入力がある場合のみ
                    string_fields = [f.name() for f in self.layer.fields() if f.type() == 10]
                    target_fields.extend(string_fields)
                    try:
                        from qgis.core import QgsMessageLog
                        QgsMessageLog.logMessage(f"全フィールド検索: string_fields={string_fields}", "GEO-search-plugin", 0)
                    except Exception:
                        pass
                break
            
            try:
                # all フラグがある場合はスキップ
                if field.get("all"):
                    continue
                
                # ViewNameが"OR検索:"で始まる場合は、検索フィールド選択ウィザードで選択された複数フィールド
                view_name = field.get("ViewName", "")
                if view_name and view_name.startswith("OR検索:"):
                    # 辞書のキーからViewName, FieldType以外のキーを抽出
                    for key in field.keys():
                        if key not in ["ViewName", "FieldType", "all"]:
                            field_name = self._resolve_field_name(key)
                            if field_name:
                                target_fields.append(field_name)
                else:
                    # 通常の単一フィールド検索
                    field_name = field.get("Field") or field.get("ViewName")
                    field_name = self._resolve_field_name(field_name)
                    if field_name:
                        target_fields.append(field_name)
                        
            except Exception as e:
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"フィールド処理エラー: {e}", "GEO-search-plugin", 1)
                except Exception:
                    pass
                continue
        
        return target_fields
    
    def _resolve_field_name(self, field_name):
        """フィールド名を解決する（別名対応）"""
        if not field_name or not self.layer:
            return None
            
        # フィールド名が存在するかチェック
        if self.layer.fields().indexFromName(field_name) != -1:
            return field_name
            
        # 別名で検索
        for layer_field in self.layer.fields():
            if layer_field.alias() == field_name:
                return layer_field.name()
                
        return field_name  # 見つからない場合でも元の名前を返す

    def show_features(self):
        """表示レイヤ用の検索処理: タイトルが「表示レイヤ」の場合、現在表示中のベクタレイヤを順に検索して集約表示する"""
        # 通常の動作（設定レイヤまたはカレントレイヤ）
        if self.title not in ("表示レイヤ", "全レイヤ"):
            return super(SearchTextFeature, self).show_features()

        # 表示レイヤ検索 or 全レイヤ検索: 対象レイヤを取得して各レイヤで検索を実行
        if self.title == "表示レイヤ":
            layers = self.get_visible_vector_layers()
        else:
            layers = self.get_all_vector_layers()
        try:
            from qgis.core import QgsMessageLog
            QgsMessageLog.logMessage(f"show_features: target layer items count={len(layers)}", "GEO-search-plugin", 0)
        except Exception:
            pass
        all_features = []
        all_fields = []
        for item in layers:
            # item may be either (node, layer) when coming from get_visible_vector_layers
            # or a bare layer when coming from get_all_vector_layers. Normalize.
            node = None
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                node, layer = item[0], item[1]
            else:
                layer = item
                node = None

            original_layer_setting = getattr(self, '_layer_setting', None)
            try:
                try:
                    from qgis.core import QgsMessageLog
                    node_id = getattr(node, 'layerId', lambda: None)() if node is not None else None
                    node_name = None
                    if node is not None:
                        try:
                            name_attr = getattr(node, 'name', None)
                            node_name = name_attr() if callable(name_attr) else name_attr
                        except Exception:
                            node_name = None
                    QgsMessageLog.logMessage(f"show_features: searching node={node_name} node_id={node_id} layer={getattr(layer, 'name', lambda: None)()}", "GEO-search-plugin", 0)
                except Exception:
                    pass

                features = self._search_on_layer(layer)
            finally:
                self._layer_setting = original_layer_setting

            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"show_features: node={getattr(node, 'name', lambda: None)() if node is not None else 'None'} features_found={len(features)}", "GEO-search-plugin", 0)
            except Exception:
                pass

            if features:
                # preserve node information so duplicates are treated separately
                for f in features:
                    all_features.append((node, layer, f))

        # If no results, show empty
        if not all_features:
            self.result_dialog.set_features([], [])
            self.result_dialog.show()
            return

        # Build per-layer lists for tabbed display
        # group results per node (or per layer when node is None)
        layers_map = []
        for node, layer, feature in all_features:
            # use node as primary key to distinguish duplicate nodes; fall back to layer
            key = node if node is not None else layer
            # compute a human-readable node path label for tab naming
            label = None
            if node is not None:
                try:
                    parts = []
                    n = node
                    while n is not None:
                        name_attr = getattr(n, 'name', None)
                        name = name_attr() if callable(name_attr) else name_attr
                        if name:
                            parts.insert(0, name)
                        parent_attr = getattr(n, 'parent', None)
                        n = parent_attr() if callable(parent_attr) else parent_attr
                    if parts:
                        label = "/".join(parts)
                except Exception:
                    label = None
            if not label:
                try:
                    label = layer.name() if layer is not None else "Results"
                except Exception:
                    label = "Results"

            entry = next((e for e in layers_map if e[0] == key), None)
            if entry is None:
                entry = [key, layer, label, [field for field in layer.fields()], [feature]]
                layers_map.append(entry)
            else:
                entry[4].append(feature)

        # call new API to set per-layer tabs; pass (label, layer) as the layer value
        self.result_dialog.set_features_by_layer([((e[2], e[1]), e[3], e[4]) for e in layers_map])
        self.result_dialog.show()

    def _search_on_layer(self, layer):
        """既存の search_feature ロジックを再利用して与えたレイヤで検索を実行するヘルパー"""
        if not layer or not layer.isValid():
            return []
            
        # 元のレイヤ設定を一時的に保存
        original_layer = getattr(self, '_layer_setting', None)
        
        try:
            # 一時的にレイヤを変更して統一ロジックを使用
            self._layer_setting = layer
            
            # 検索値を取得して正規化
            search_value = None
            for widget in self.widget.search_widgets:
                value = widget.text()
                if value:
                    search_value = self.normalize_search_value(value)
                    break
            
            if not search_value:
                return []
            
            # 統一されたフィールド特定ロジックを使用
            target_fields = self._get_target_fields_for_layer(layer)
            
            if not target_fields:
                return []
            
            # 統一された検索条件構築ロジックを使用
            expres_list = []
            for field_name in target_fields:
                expres_list.append('"{field}" LIKE \'%{value}%\''.format(field=field_name, value=search_value))
            
            expression_str = self.andor.join(expres_list)
            expression = QgsExpression(expression_str)
            
            if expression.hasEvalError():
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"_search_on_layer: expression error: {expression.evalErrorString()}", "GEO-search-plugin", 0)
                except Exception:
                    pass
                return []
            
            request = QgsFeatureRequest(expression)
            features = list(layer.getFeatures(request))
            
            try:
                from qgis.core import QgsMessageLog
                layer_name = getattr(layer, 'name', lambda: 'None')()
                QgsMessageLog.logMessage(f"_search_on_layer: layer={layer_name} fields={target_fields} found={len(features)}", "GEO-search-plugin", 0)
            except Exception:
                pass
                
            return features
            
        finally:
            # 元のレイヤ設定を復元
            self._layer_setting = original_layer
    
    def _get_target_fields_for_layer(self, layer):
        """指定されたレイヤに対して検索対象フィールドを特定する"""
        target_fields = []
        
        for field, search_widget in zip(self.fields, self.widget.search_widgets):
            if not isinstance(field, dict):
                continue
            
            # 全フィールド検索の場合
            if field == {}:
                if search_widget.text():
                    string_fields = [f.name() for f in layer.fields() if f.type() == 10]
                    target_fields.extend(string_fields)
                break
            
            try:
                if field.get("all"):
                    continue
                
                # OR検索フィールド
                view_name = field.get("ViewName", "")
                if view_name and view_name.startswith("OR検索:"):
                    for key in field.keys():
                        if key not in ["ViewName", "FieldType", "all"]:
                            field_name = self._resolve_field_name_for_layer(key, layer)
                            if field_name:
                                target_fields.append(field_name)
                else:
                    # 単一フィールド検索
                    field_name = field.get("Field") or field.get("ViewName")
                    field_name = self._resolve_field_name_for_layer(field_name, layer)
                    if field_name:
                        target_fields.append(field_name)
                        
            except Exception as e:
                try:
                    from qgis.core import QgsMessageLog
                    QgsMessageLog.logMessage(f"_get_target_fields_for_layer: フィールド処理エラー: {e}", "GEO-search-plugin", 1)
                except Exception:
                    pass
                continue
        
        return target_fields
    
    def _resolve_field_name_for_layer(self, field_name, layer):
        """指定されたレイヤでフィールド名を解決する"""
        if not field_name or not layer:
            return None
            
        # フィールド名が存在するかチェック
        if layer.fields().indexFromName(field_name) != -1:
            return field_name
            
        # 別名で検索
        for layer_field in layer.fields():
            if layer_field.alias() == field_name:
                return layer_field.name()
                
        return field_name


# "地番検索"
class SearchTibanFeature(SearchTextFeature):
    FUZZY_NUM = 2

    def load(self):
        if self.suggest_flg:
            self.set_suggest()
        dialog = self.widget.dialog
        # 問題
        dialog.questionButton.setVisible(bool(self.message))
        dialog.questionButton.clicked.connect(self.show_message)
        self.init_code_table()
        self.widget.code_table.itemSelectionChanged.connect(self.set_aza_code)

    def unload(self):
        dialog = self.widget.dialog
        # 問題
        dialog.questionButton.clicked.disconnect(self.show_message)
        self.widget.code_table.itemSelectionChanged.disconnect(self.set_aza_code)

    def init_code_table(self):
        setting = self.setting.get("AzaTable")
        if not setting:
            return
        if self.widget.code_table.rowCount():
            return
        columns = setting.get("Columns", [])
        self.set_code_table_columns(columns)
        rows = self.get_codes(setting)
        self.set_code_table_items(rows)

    def set_code_table_columns(self, columns):
        table = self.widget.code_table
        heads = len(columns)
        table.setColumnCount(heads)
        table.setHorizontalHeaderLabels([col["View"] for col in columns])
        header = table.horizontalHeader()
        for i in range(len(columns)):
            header.setSectionResizeMode(i, header.Stretch)

    def get_codes(self, setting):
        host = setting.get("Host")
        port = setting.get("Port")
        database = setting.get("Database")
        user = setting.get("User")
        password = setting.get("Password")
        table = setting.get("Table")
        columns = [f'"{col["Name"]}"' for col in setting.get("Columns", [])]
        query = f"SELECT {','.join(columns)} FROM \"{table}\""
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                connect_timeout=1,
            )
            cursor = conn.cursor()
            cursor.execute(query)
            result = cursor.fetchall()
            cursor.close()
            conn.close()

        except psycopg2.OperationalError:
            return []
        except psycopg2.errors.SyntaxError:
            return []
        except psycopg2.errors.UndefinedTable:
            return []
        return result

    def set_code_table_items(self, rows):
        table = self.widget.code_table
        table.setRowCount(len(rows))

        for index, values in enumerate(rows):
            for column, value in enumerate(values):
                # 検索結果をテーブルにセットしていく
                item = QTableWidgetItem()
                if isinstance(value, int):
                    item.setText(f"{value:05}")
                else:
                    item.setText(value)
                table.setItem(index, column, item)

    def set_aza_code(self):
        items = self.widget.code_table.selectedItems()
        if items:
            item, *_ = items
            self.widget.search_widgets[0].setText(item.text())

    def search_feature(self, limit=None):
        layer = self.layer
        tiban_field = self.setting.get("TibanField", "")
        if not layer:
            return []
        expres_list = []
        regexp_values = []
        for field, search_widget in zip(self.fields, self.widget.search_widgets):
            field_name = field["Field"]
            fuzzy = field.get("Fuzzy", 0)
            value = search_widget.text()
            if field_name == tiban_field:
                regexp_values.append(value)
                continue
            if not value:
                continue
            
            # 全角英数字を半角に変換
            value = self.normalize_search_value(value)
            # 地番の場合、あいまい検索のフラグ
            if fuzzy and value.isdigit() and not self.widget.perfect_button.isChecked():
                value = int(value)
                values = map(str, range(value - fuzzy, value + fuzzy + 1))
                expres = '"{field}" in ({value})'.format(
                    field=field_name,
                    value=",".join(values),
                )
            else:
                expres = "\"{field}\" = '{value}'".format(
                    field=field_name,
                    value=value,
                )
            expres_list.append(expres)
        if any(regexp_values):
            # 地番値も正規化処理を適用
            normalized_regexp_values = [self.normalize_search_value(v) if v else v for v in regexp_values]
            
            regexp = ""
            for i, value in enumerate(normalized_regexp_values):
                if i == 0 and value and value.isdigit():
                    value = int(value)
                    fuzzy_values = map(
                        str, range(value - self.FUZZY_NUM, value + self.FUZZY_NUM + 1)
                    )
                    regexp += f"({'|'.join(fuzzy_values)})"
                elif value:
                    regexp += f"({value})([^-]*)?"
                else:
                    regexp += "([^-]*)?"
                if i == len(normalized_regexp_values) - 1:
                    continue
                elif not any(normalized_regexp_values[i + 1 :]):
                    regexp += "(-[^-]*)*"
                    break
                else:
                    regexp += "-"
            regexp = f"^{regexp}$"
            expres_list.append(
                "regexp_match(\"{field}\", '{regexp}')".format(
                    field=tiban_field,
                    regexp=regexp,
                )
            )
        expression = QgsExpression(self.andor.join(expres_list))
        request = QgsFeatureRequest(expression)
        if limit:
            request.setLimit(limit)
        return list(layer.getFeatures(request))


# "所有者検索"
class SearchOwnerFeature(SearchTextFeature):
    def load(self):
        if self.suggest_flg:
            self.set_suggest()
        dialog = self.widget.dialog
        dialog.questionButton.setVisible(bool(self.message))
        dialog.questionButton.clicked.connect(self.show_message)

    def unload(self):
        dialog = self.widget.dialog
        dialog.questionButton.clicked.disconnect(self.show_message)

    def search_feature(self, limit=None):
        layer = self.layer
        if not layer:
            return []
        search_widget = self.widget.search_widgets[0]
        expres_list = []
        for field, check in zip(self.fields, self.widget.check_list):
            field_name = field["Field"]
            if not check.isChecked():
                continue
            value = search_widget.text()
            if not value:
                continue
            
            # 全角英数字を半角に変換（既存の処理の前に実行）
            value = self.normalize_search_value(value)

            if field.get("KanaHankaku", False):
                #                value = jaconv.z2h(value, digit=False, ascii=False)
                value = (
                    value.replace("ｬ", "ﾔ")
                    .replace("ｭ", "ﾕ")
                    .replace("ｮ", "ﾖ")
                    .replace("ｯ", "ﾂ")
                    .replace("ｧ", "ｱ")
                    .replace("ｨ", "ｲ")
                    .replace("ｩ", "ｳ")
                    .replace("ｪ", "ｴ")
                    .replace("ｫ", "ｵ")
                )
            else:
                value = (
                    value.replace("ャ", "ヤ")
                    .replace("ュ", "ユ")
                    .replace("ョ", "ヨ")
                    .replace("ッ", "ツ")
                    .replace("ァ", "ア")
                    .replace("ィ", "イ")
                    .replace("ゥ", "ウ")
                    .replace("ェ", "エ")
                    .replace("ォ", "オ")
                )

            value = (
                f"%{value}%" if self.widget.forward_button.isChecked() else f"{value}%"
            )

            if field.get("KanaHankaku", False):
                expres_list.append(
                    "replace(\"{field}\", array('\\\\s', '　','ｧ','ｨ','ｩ','ｪ','ｫ','ｬ','ｭ','ｮ','ｯ','ァ','ィ','ゥ','ェ','ォ','ャ','ュ','ョ','ッ','ア','イ','ウ','エ','オ','カ','キ','ク','ケ','コ','サ','シ','ス','セ','ソ','タ','チ','ツ','テ','ト','ナ','ニ','ヌ','ネ','ノ','ハ','ヒ','フ','ヘ','ホ','マ','ミ','ム','メ','モ','ヤ','ユ','ヨ','ラ','リ','ル','レ','ロ', 'ワ','ヰ','ヱ','ヲ','ン','ガ','ギ','グ','ゲ','ゴ','ザ','ジ','ズ','ゼ','ゾ','ダ','ヂ','ヅ','デ','ド','バ','ビ','ブ','ベ','ボ','パ','ピ','プ','ペ','ポ','ァ','ィ','ゥ','ェ','ォ','ャ','ュ','ョ','ッ'), array('', '','ｱ','ｲ','ｳ','ｴ','ｵ','ﾔ','ﾕ','ﾖ','ﾂ','ア','イ','ウ','エ','オ','ヤ','ユ','ヨ','ツ','ｱ','ｲ','ｳ','ｴ','ｵ','ｶ','ｷ','ｸ','ｹ','ｺ','ｻ','ｼ','ｽ','ｾ','ｿ','ﾀ','ﾁ','ﾂ','ﾃ','ﾄ', 'ﾅ','ﾆ','ﾇ','ﾈ','ﾉ','ﾊ','ﾋ','ﾌ','ﾍ','ﾎ','ﾏ','ﾐ','ﾑ','ﾒ','ﾓ','ﾔ','ﾕ','ﾖ','ﾗ','ﾘ','ﾙ','ﾚ','ﾛ','ﾜ','ｲ','ｴ','ｦ','ﾝ','ｶﾞ','ｷﾞ','ｸﾞ','ｹﾞ','ｺﾞ','ｻﾞ','ｼﾞ','ｽﾞ','ｾﾞ','ｿﾞ','ﾀﾞ','ﾁﾞ','ﾂﾞ','ﾃﾞ','ﾄﾞ','ﾊﾞ','ﾋﾞ','ﾌﾞ','ﾍﾞ','ﾎﾞ','ﾊﾟ','ﾋﾟ','ﾌﾟ','ﾍﾟ','ﾎﾟ','ｱ','ｲ','ｳ','ｴ','ｵ','ﾔ','ﾕ','ﾖ','ﾂ')) LIKE '{value}'".format(
                        field=field_name,
                        value=value,
                    )
                )
            else:
                expres_list.append(
                    "replace(\"{field}\", array('\\\\s', '　','ｧ','ｨ','ｩ','ｪ','ｫ','ｬ','ｭ','ｮ','ｯ','ァ','ィ','ゥ','ェ','ォ','ャ','ュ','ョ','ッ','ｱ','ｲ','ｳ','ｴ','ｵ','ｶ','ｷ','ｸ','ｹ','ｺ','ｻ','ｼ','ｽ','ｾ','ｿ','ﾀ','ﾁ','ﾂ','ﾃ','ﾄ', 'ﾅ','ﾆ','ﾇ','ﾈ','ﾉ','ﾊ','ﾋ','ﾌ','ﾍ','ﾎ','ﾏ','ﾐ','ﾑ','ﾒ','ﾓ','ﾔ','ﾕ','ﾖ','ﾗ','ﾘ','ﾙ','ﾚ','ﾛ','ﾜ','ｲ','ｴ','ｦ','ﾝ','ｶﾞ','ｷﾞ','ｸﾞ','ｹﾞ','ｺﾞ','ｻﾞ','ｼﾞ','ｽﾞ','ｾﾞ','ｿﾞ','ﾀﾞ','ﾁﾞ','ﾂﾞ','ﾃﾞ','ﾄﾞ','ﾊﾞ','ﾋﾞ','ﾌﾞ','ﾍﾞ','ﾎﾞ','ﾊﾟ','ﾋﾟ','ﾌﾟ','ﾍﾟ','ﾎﾟ','ｧ','ｨ','ｩ','ｪ','ｫ','ｬ','ｭ','ｮ','ｯ'), array('', '','ｱ','ｲ','ｳ','ｴ','ｵ','ﾔ','ﾕ','ﾖ','ﾂ','ア','イ','ウ','エ','オ','ヤ','ユ','ヨ','ツ','ア','イ','ウ','エ','オ','カ','キ','ク','ケ','コ','サ','シ','ス','セ','ソ','タ','チ','ツ','テ','ト','ナ','ニ','ヌ','ネ','ノ','ハ','ヒ','フ','ヘ','ホ','マ','ミ','ム','メ','モ','ヤ','ユ','ヨ','ラ','リ','ル','レ','ロ', 'ワ','ヰ','ヱ','ヲ','ン','ガ','ギ','グ','ゲ','ゴ','ザ','ジ','ズ','ゼ','ゾ','ダ','ヂ','ヅ','デ','ド','バ','ビ','ブ','ベ','ボ','パ','ピ','プ','ペ','ポ','ア','イ','ウ','エ','オ','ヤ','ユ','ヨ','ツ')) LIKE '{value}'".format(
                        field=field_name,
                        value=value,
                    )
                )
        expression = QgsExpression(self.andor.join(expres_list))
        request = QgsFeatureRequest(expression)
        if limit:
            request.setLimit(limit)
        return list(layer.getFeatures(request))

    def set_suggest(self):
        """サジェスト表示"""
        if not self.layer:
            return
        search_widget = self.widget.search_widgets[0]
        suggest_list = []
        for field_name, check in zip(self.field_names, self.widget.check_list):
            if check.checkState() == Qt.Checked:
                suggest_list += map(str, unique_values(self.layer, field_name))
        comp = QCompleter(suggest_list)
        search_widget.setCompleter(comp)
