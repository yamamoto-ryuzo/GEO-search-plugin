# -*- coding: utf-8 -*-
import os
import math

from qgis.PyQt.QtCore import QDate, pyqtSignal
from qgis.PyQt.QtWidgets import QDialog, QTableWidgetItem, QTabWidget, QTableWidget, QHeaderView
from qgis.PyQt import uic


UI_FILE = "result.ui"

#検索結果表示ダイアログ
class ResultDialog(QDialog):
    # dialog-level signals to decouple callers from concrete table widgets
    selectionChanged = pyqtSignal()
    itemPressed = pyqtSignal(object)

    def __init__(self, parent=None, page_limit=500):
        QDialog.__init__(self, parent)
        directory = os.path.join(os.path.dirname(__file__), "ui")
        ui_file = os.path.join(directory, UI_FILE)
        uic.loadUi(ui_file, self)
        self.data_role = 15
        self.page_limit = page_limit
        self.nextButton.clicked.connect(self.next_page)
        self.prevButton.clicked.connect(self.prev_page)
        self.pageBox.valueChanged.connect(self.move_page)
        # replace single table widget with a tab widget containing one or more tables
        # keep existing self.tableWidget as the first tab for backward compatibility
        try:
            # remove existing tableWidget from layout and insert a QTabWidget
            self.gridLayout.removeWidget(self.tableWidget)
        except Exception:
            pass
        self.tabWidget = QTabWidget(self)
        # add tabWidget to the same grid position as original (row 0, col 0, colspan 6)
        self.gridLayout.addWidget(self.tabWidget, 0, 0, 1, 6)
        # add the original tableWidget as the first tab
        self.tabWidget.addTab(self.tableWidget, "Results")
        # keep track of per-tab data: list of dicts with fields/features/table
        self._tabs = []
        # map the first tab
        self._tabs.append({
            "layer": None,
            "fields": None,
            "features": [],
            "table": self.tableWidget,
        })
        # current active table reference
        self.current_table = self.tableWidget
        # forward signals from contained tables to dialog-level signals
        self.current_table.itemSelectionChanged.connect(lambda: self.selectionChanged.emit())
        self.current_table.itemPressed.connect(lambda item: self.itemPressed.emit(item))
        self.tabWidget.currentChanged.connect(self._on_tab_changed)

    def next_page(self):
        value = self.pageBox.value()
        self.pageBox.setValue(value + 1)

    def prev_page(self):
        value = self.pageBox.value()
        self.pageBox.setValue(value - 1)

    def move_page(self, page):
        # operate on the currently selected tab's feature list
        idx = self.tabWidget.currentIndex()
        tab = self._tabs[idx]
        features = tab.get("features") or []
        try:
            from qgis.core import QgsMessageLog
            QgsMessageLog.logMessage(f"move_page: tab_index={idx} tab_layer={getattr(tab.get('layer'), 'name', lambda: None)() if tab.get('layer') else 'None'} features_total={len(features)} page={page}", "GEO-search-plugin", 0)
        except Exception:
            pass
        s = (page - 1) * self.page_limit
        e = page * self.page_limit
        page_features = features[s:e]
        try:
            from qgis.core import QgsMessageLog
            QgsMessageLog.logMessage(f"move_page: s={s} e={e} page_features_count={len(page_features)}", "GEO-search-plugin", 0)
        except Exception:
            pass

        rows = len(page_features)
        if rows > self.page_limit:
            rows = self.page_limit
        table = tab.get("table") or self.current_table
        table.setRowCount(rows)
        table.setVerticalHeaderLabels([f"{i}" for i in range(s, e)])
        self.set_feature_items(page_features, table, tab.get("fields"))

    def set_features(self, fields, features):
        """
        Backwards-compatible setter for single-layer results (old callers).
        If callers pass features as list of tuples (layer, feature) consider using
        set_features_by_layer for per-layer tab display.
        """
        # simple single-table behavior
        self._tabs = []
        # reuse existing table as a single tab
        tab = {"layer": None, "fields": fields, "features": features, "table": self.tableWidget}
        self._tabs.append(tab)
        # prepare table columns
        self.tableWidget.setColumnCount(len(fields) if fields else 0)
        if fields:
            self.tableWidget.setHorizontalHeaderLabels([field.displayName() for field in fields])
            header = self.tableWidget.horizontalHeader()
            for i in range(len(fields)):
                header.setSectionResizeMode(i, header.Stretch)

        self.setWindowTitle(f"検索結果: {len(features)}件")
        max_page = math.ceil(len(features) / self.page_limit) if features else 1
        self.pageBox.setMaximum(max_page)
        self.pageLabel.setText(f" / {max_page}")
        # ensure tabWidget has this single table
        # remove extra tabs and reset
        while self.tabWidget.count() > 1:
            self.tabWidget.removeTab(1)
        if self.tabWidget.indexOf(self.tableWidget) == -1:
            self.tabWidget.insertTab(0, self.tableWidget, "Results")
        self.tabWidget.setCurrentIndex(0)
        # connect table signals
        self.current_table = self.tableWidget
        self.current_table.itemSelectionChanged.connect(lambda: self.selectionChanged.emit())
        self.current_table.itemPressed.connect(lambda item: self.itemPressed.emit(item))
        self.pageBox.setValue(1)
        self.move_page(1)

    def set_features_by_layer(self, layers_with_features):
        """Accepts an iterable of (layer, fields, features) and creates a tab per layer."""
        # clear existing tabs
        self._tabs = []
        # remove all tabs
        while self.tabWidget.count() > 0:
            widget = self.tabWidget.widget(0)
            self.tabWidget.removeTab(0)
        total_count = 0
        for layer, fields, features in layers_with_features:
            total_count += len(features)
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"set_features_by_layer: preparing tab for layer={getattr(layer, '__repr__', lambda: layer)()} features_count={len(features)}", "GEO-search-plugin", 0)
            except Exception:
                pass
            # create a new table for this tab
            table = QTableWidget(self)
            table.setEditTriggers(self.tableWidget.editTriggers())
            table.setSelectionMode(self.tableWidget.selectionMode())
            table.setSelectionBehavior(self.tableWidget.selectionBehavior())
            table.setSortingEnabled(self.tableWidget.isSortingEnabled())
            # set columns
            heads = len(fields) if fields else 0
            table.setColumnCount(heads)
            if fields:
                table.setHorizontalHeaderLabels([field.displayName() for field in fields])
                header = table.horizontalHeader()
                for i in range(len(fields)):
                    header.setSectionResizeMode(i, header.Stretch)
            # connect signals
            table.itemSelectionChanged.connect(lambda: self.selectionChanged.emit())
            table.itemPressed.connect(lambda item: self.itemPressed.emit(item))
            # add tab
            # support layer being a (label, layer) tuple
            actual_layer = layer
            tab_label = None
            try:
                if isinstance(layer, (list, tuple)) and len(layer) >= 2:
                    tab_label, actual_layer = layer[0], layer[1]
                else:
                    actual_layer = layer
            except Exception:
                actual_layer = layer

            name = tab_label if tab_label is not None else (actual_layer.name() if actual_layer is not None else "Results")
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"set_features_by_layer: adding tab name={name} features={len(features)}", "GEO-search-plugin", 0)
            except Exception:
                pass
            self.tabWidget.addTab(table, name)
            self._tabs.append({"layer": actual_layer, "fields": fields, "features": features, "table": table})
            # populate this tab's first page immediately so rows are visible
            try:
                # ensure row count is set before inserting items
                rows = len(features)
                if rows > self.page_limit:
                    rows = self.page_limit
                table.setRowCount(rows)
                # populate first page directly
                self.set_feature_items(features[:self.page_limit], table, fields)
                # ensure row heights are reasonable and widget repainted
                try:
                    table.resizeRowsToContents()
                except Exception:
                    pass
                try:
                    table.repaint()
                    table.setVisible(True)
                except Exception:
                    pass
            except Exception:
                pass

        self.setWindowTitle(f"検索結果: {total_count}件")
        # initialize first tab
        self.tabWidget.setCurrentIndex(0)
        # setup paging for first tab
        first_features = self._tabs[0].get("features") or []
        max_page = math.ceil(len(first_features) / self.page_limit) if first_features else 1
        self.pageBox.setMaximum(max_page)
        self.pageLabel.setText(f" / {max_page}")
        self.pageBox.setValue(1)
        self.move_page(1)
        try:
            # force-select each tab to ensure its table and viewport are initialized
            from qgis.PyQt.QtCore import QCoreApplication
            current = self.tabWidget.currentIndex()
            for i in range(self.tabWidget.count()):
                try:
                    self.tabWidget.setCurrentIndex(i)
                    # let Qt process events so the widget can layout
                    QCoreApplication.processEvents()
                    # call move_page to ensure the table for this tab is populated
                    self.move_page(1)
                except Exception:
                    pass
            # restore selection
            try:
                self.tabWidget.setCurrentIndex(current)
            except Exception:
                pass
            QCoreApplication.processEvents()
        except Exception:
            pass
        try:
            from qgis.core import QgsMessageLog
            # dump internal _tabs structure for debugging
            for i, tab in enumerate(self._tabs):
                layer = tab.get('layer')
                fields = tab.get('fields') or []
                features = tab.get('features') or []
                feat_type = None
                try:
                    if features:
                        f0 = features[0]
                        # try to get id if possible
                        fid = getattr(f0, 'id', lambda: None)()
                        feat_type = f"feature(id={fid})"
                    else:
                        feat_type = 'no-features'
                except Exception:
                    feat_type = str(type(f0))
                QgsMessageLog.logMessage(f"set_features_by_layer: tab_index={i} layer={getattr(layer, 'name', lambda: layer)()} fields_count={len(fields)} features_count={len(features)} first_feature={feat_type}", "GEO-search-plugin", 0)
        except Exception:
            pass

    def set_feature_items(self, features, table=None, fields=None):
        """Fill provided table with features using provided fields. If not given use current."""
        if table is None:
            table = self.current_table
        if fields is None:
            # find fields from current tab
            idx = self.tabWidget.currentIndex()
            fields = self._tabs[idx].get("fields") if self._tabs else self.fields
        table.clearContents()
        try:
            from qgis.core import QgsMessageLog
            QgsMessageLog.logMessage(f"set_feature_items: table={table} fields_count={len(fields) if fields else 0} features_count={len(features)}", "GEO-search-plugin", 0)
            # show sample feature ids/attrs
            sample_info = []
            for i, feat in enumerate(features[:3]):
                try:
                    sample_info.append({ 'id': feat.id(), 'attrs': { f.name(): feat[f.name()] for f in fields } })
                except Exception:
                    sample_info.append(str(feat))
            QgsMessageLog.logMessage(f"set_feature_items: samples={sample_info}", "GEO-search-plugin", 0)
        except Exception:
            pass
        for index, feature in enumerate(features):
            for column, field in enumerate(fields):
                item = self.create_item(field, feature)
                table.setItem(index, column, item)
        try:
            # ensure UI updates and columns are sized
            table.resizeColumnsToContents()
            # repaint and ensure the first cell is focused/visible
            table.repaint()
            if table.rowCount() > 0 and table.columnCount() > 0:
                try:
                    # make first cell current and visible
                    table.setCurrentCell(0, 0)
                except Exception:
                    pass
                try:
                    table.scrollToItem(table.item(0, 0))
                except Exception:
                    pass
                try:
                    # give table keyboard focus to help rendering in some environments
                    table.setFocus()
                except Exception:
                    pass
            try:
                # nudge Qt to process pending events so the UI updates immediately
                from qgis.PyQt.QtCore import QCoreApplication
                QCoreApplication.processEvents()
            except Exception:
                pass
            try:
                # additional defensive updates
                table.viewport().update()
                table.updateGeometry()
                header = table.horizontalHeader()
                header.repaint()
                self.tabWidget.update()
                self.update()
                try:
                    # bring dialog to front if possible
                    self.raise_()
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass

    def create_item(self, field, feature):
        # 検索結果をテーブルにセットしていく
        # フィールド名を取得
        name = field.name()
        item = QTableWidgetItem()
        # アイテムに指定フィールドの属性をセット
        # 日付の場合の場合はも書式を指定して文字列に変換
        val = feature.attribute(name)
        if isinstance(val, QDate):
            item.setText(QDate.toString(val, 'yyyy/M/d'))
        else:
            # その他はそのまま（Python3互換）
            item.setText(str(val))
        item.setData(self.data_role, feature.id())
        return item

    def _on_tab_changed(self, index):
        # update page controls to reflect selected tab
        if index < 0 or index >= len(self._tabs):
            return
        tab = self._tabs[index]
        self.current_table = tab.get("table")
        # rewire table signals to dialog signals
        try:
            self.current_table.itemSelectionChanged.connect(lambda: self.selectionChanged.emit())
            self.current_table.itemPressed.connect(lambda item: self.itemPressed.emit(item))
        except Exception:
            pass
        # update paging
        features = tab.get("features") or []
        max_page = math.ceil(len(features) / self.page_limit) if features else 1
        self.pageBox.setMaximum(max_page)
        self.pageLabel.setText(f" / {max_page}")
        self.pageBox.setValue(1)
