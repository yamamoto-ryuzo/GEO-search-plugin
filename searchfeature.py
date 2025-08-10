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
        self.view_fields = setting["ViewFields"]
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
        self.result_dialog.tableWidget.itemSelectionChanged.connect(self.zoom_items)
        self.result_dialog.tableWidget.itemPressed.connect(self.zoom_items)

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

    def zoom_items(self):
        items = self.result_dialog.tableWidget.selectedItems()
        self.zoom_features([item.data(self.data_role) for item in items])

    def zoom_features(self, feature_ids=None):
        """検索結果にズーム"""
        if feature_ids is None and not self.result_features:
            return
        elif feature_ids is None:
            feature_ids = self.result_features.keys()
        self.layer.selectByIds(feature_ids)
        self.iface.mapCanvas().zoomToSelected(self.layer)

    def show_features(self):
        """検索結果を表示する"""
        if not self.layer:
            return
        features = self.search_feature()
        self.result_dialog.set_features(self.view_fields, features)
        self.result_dialog.show()

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
        expres_list = []
        all_field_search = False
        all_value = None
        # Check if the "All" field is enabled and has input
        from qgis.core import QgsMessageLog
        for field, search_widget in zip(self.fields, self.widget.search_widgets):
            # 空dict（Allフィールド）のみ all_field_search を実行
            if field == {}:
                all_value = search_widget.text()
                if all_value:
                    all_field_search = True
                QgsMessageLog.logMessage(f"DEBUG: field={{}} (All), text={search_widget.text()}", "GEO-search-plugin", 0)
                break
        if all_field_search:
            # --- all_field_search 実行箇所 ---
            import os
            QgsMessageLog.logMessage("[INFO] all_field_search is executed: searching all fields.", "GEO-search-plugin", 0)
            QgsMessageLog.logMessage(f"[DEBUG] searchfeature.py path: {os.path.abspath(__file__)}", "GEO-search-plugin", 0)
            
            # レイヤの詳細情報をログ出力
            QgsMessageLog.logMessage(f"[DEBUG] layer: {self.layer}", "GEO-search-plugin", 0)
            QgsMessageLog.logMessage(f"[DEBUG] layer.isValid(): {self.layer.isValid() if self.layer else 'None'}", "GEO-search-plugin", 0)
            QgsMessageLog.logMessage(f"[DEBUG] layer.name(): {self.layer.name() if self.layer else 'None'}", "GEO-search-plugin", 0)
            QgsMessageLog.logMessage(f"[DEBUG] layer.featureCount(): {self.layer.featureCount() if self.layer else 'None'}", "GEO-search-plugin", 0)
            
            if not self.layer or not self.layer.isValid():
                QgsMessageLog.logMessage("[ERROR] Layer is None or invalid!", "GEO-search-plugin", 0)
                return []
            
            fields = self.layer.fields()
            QgsMessageLog.logMessage(f"[DEBUG] fields object: {fields}", "GEO-search-plugin", 0)
            QgsMessageLog.logMessage(f"[DEBUG] fields.count(): {fields.count()}", "GEO-search-plugin", 0)
            
            search_fields = []
            field_types = []
            field_aliases = []
            for i, field in enumerate(fields):
                field_name = field.name()
                field_type = field.typeName()
                field_alias = field.alias() or field_name  # 別名がない場合は実名を使用
                search_fields.append(field_name)  # 実フィールド名を使用
                field_types.append(f"{field_name}:{field_type}")
                field_aliases.append(f"{field_name}(alias:{field_alias})")
                QgsMessageLog.logMessage(f"[DEBUG] field[{i}]: name='{field_name}', type='{field_type}', alias='{field_alias}'", "GEO-search-plugin", 0)
            
            QgsMessageLog.logMessage(f"search_fields: {search_fields}", "GEO-search-plugin", 0)
            QgsMessageLog.logMessage(f"search_fields (name:type): {field_types}", "GEO-search-plugin", 0)
            QgsMessageLog.logMessage(f"search_fields (name:alias): {field_aliases}", "GEO-search-plugin", 0)

            # 全文検索アプローチ: 文字列フィールドのみを連結して検索
            string_fields = []
            for field in fields:
                if field.type() == 10:  # String type (QVariant::String = 10)
                    string_fields.append(field.name())
            
            QgsMessageLog.logMessage(f"[DEBUG] String fields for full-text search: {string_fields}", "GEO-search-plugin", 0)
            
            if string_fields:
                # CONCATを使用して文字列フィールドを連結し、一括検索
                concat_fields = " || ' ' || ".join([f'COALESCE("{field}", \'\')' for field in string_fields])
                full_text_expr = f'({concat_fields}) LIKE \'%{all_value}%\''
                QgsMessageLog.logMessage(f"[DEBUG] Full-text search expression: {full_text_expr}", "GEO-search-plugin", 0)
                
                expression = QgsExpression(full_text_expr)
                
                # 式の有効性をチェック
                if expression.hasEvalError():
                    QgsMessageLog.logMessage(f"[ERROR] Expression error: {expression.evalErrorString()}", "GEO-search-plugin", 0)
                    return []
                
                request = QgsFeatureRequest(expression)
                if limit:
                    request.setLimit(limit)
                
                features = list(layer.getFeatures(request))
                QgsMessageLog.logMessage(f"[ALL RESULT] Full-text search found {len(features)} features", "GEO-search-plugin", 0)
                
                return features
            else:
                QgsMessageLog.logMessage("[WARNING] No string fields found for full-text search!", "GEO-search-plugin", 0)
                return []
        else:
            # --- 通常検索（個別フィールド検索）実行箇所 ---
            QgsMessageLog.logMessage("[INFO] Normal field search is executed.", "GEO-search-plugin", 0)
            QgsMessageLog.logMessage(f"[DEBUG] self.fields: {self.fields}", "GEO-search-plugin", 0)
            
            for field, search_widget in zip(self.fields, self.widget.search_widgets):
                if field.get("all"):
                    continue
                field_name = field.get("Field") or field.get("ViewName")
                value = search_widget.text()
                QgsMessageLog.logMessage(f"[DEBUG] field config: {field}, field_name: '{field_name}', value: '{value}'", "GEO-search-plugin", 0)
                
                if not value:
                    continue
                    
                # フィールド名の存在確認
                if self.layer and self.layer.fields().indexFromName(field_name) == -1:
                    QgsMessageLog.logMessage(f"[WARNING] Field '{field_name}' not found in layer fields!", "GEO-search-plugin", 0)
                    # 別名での検索も試行
                    for layer_field in self.layer.fields():
                        if layer_field.alias() == field_name:
                            field_name = layer_field.name()  # 実フィールド名に変換
                            QgsMessageLog.logMessage(f"[INFO] Found field by alias: '{field.get('Field')}' -> '{field_name}'", "GEO-search-plugin", 0)
                            break
                
                expres_list.append(
                    '"{field}" LIKE \'%{value}%\''.format(field=field_name, value=value)
                )
                QgsMessageLog.logMessage(f"[DEBUG] Added expression: \"{field_name}\" LIKE '%{value}%'", "GEO-search-plugin", 0)
            
            expression_str = self.andor.join(expres_list)
            QgsMessageLog.logMessage(f"[DEBUG] Final expression: {expression_str}", "GEO-search-plugin", 0)
            expression = QgsExpression(expression_str)
        request = QgsFeatureRequest(expression)
        if limit:
            request.setLimit(limit)
        
        # 検索結果の詳細ログ
        features = list(layer.getFeatures(request))
        QgsMessageLog.logMessage(f"[RESULT] Found {len(features)} features", "GEO-search-plugin", 0)
        
        # 最初の数件の詳細を出力（デバッグ用）
        for i, feature in enumerate(features[:3]):  # 最初の3件のみ
            attrs = {}
            for field in layer.fields():
                field_name = field.name()
                alias = field.alias() or field_name
                value = feature[field_name]
                attrs[f"{field_name}({alias})"] = str(value)
            QgsMessageLog.logMessage(f"[RESULT] Feature {i+1}: {attrs}", "GEO-search-plugin", 0)
        
        return features


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
            regexp = ""
            for i, value in enumerate(regexp_values):
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
                if i == len(regexp_values) - 1:
                    continue
                elif not any(regexp_values[i + 1 :]):
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
