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
        self.tabWidget.addTab(self.tableWidget, self.tr("Results"))
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
            self.tableWidget.setHorizontalHeaderLabels([self.tr(field.displayName()) for field in fields])
            header = self.tableWidget.horizontalHeader()
            # Prefer sizing to contents and then stretch the last column so
            # attributes do not collapse to very small widths under Qt6.
            try:
                header.setMinimumSectionSize(60)
            except Exception:
                pass
            for i in range(len(fields)):
                try:
                    header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
                except Exception:
                    # fallback to Stretch if ResizeToContents not available
                    try:
                        header.setSectionResizeMode(i, QHeaderView.Stretch)
                    except Exception:
                        pass
            try:
                # make last column expand to fill available space
                header.setStretchLastSection(True)
            except Exception:
                pass

        self.setWindowTitle(self.tr("Search Results: {0} items").format(len(features)))
        max_page = math.ceil(len(features) / self.page_limit) if features else 1
        self.pageBox.setMaximum(max_page)
        self.pageLabel.setText(self.tr(" / {0}").format(max_page))
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
            # defensive: ensure features is a concrete list (caller may pass an iterator)
            try:
                features = list(features)
            except Exception:
                pass
            total_count += len(features)
            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"set_features_by_layer: preparing tab for layer={getattr(layer, '__repr__', lambda: layer)()} features_count={len(features)}", "GEO-search-plugin", 0)
            except Exception:
                pass
            # ensure fields is a concrete sequence of field objects
            try:
                fields = list(fields) if fields is not None else []
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
                table.setHorizontalHeaderLabels([self.tr(field.displayName()) for field in fields])
                header = table.horizontalHeader()
                try:
                    header.setMinimumSectionSize(60)
                except Exception:
                    pass
                for i in range(len(fields)):
                    try:
                        header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
                    except Exception:
                        try:
                            header.setSectionResizeMode(i, QHeaderView.Stretch)
                        except Exception:
                            pass
                try:
                    header.setStretchLastSection(True)
                except Exception:
                    pass
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
            self.tabWidget.addTab(table, self.tr(name))
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

        self.setWindowTitle(self.tr("Search Results: {0} items").format(total_count))
        # initialize first tab
        self.tabWidget.setCurrentIndex(0)
        # setup paging for first tab
        first_features = self._tabs[0].get("features") or []
        max_page = math.ceil(len(first_features) / self.page_limit) if first_features else 1
        self.pageBox.setMaximum(max_page)
        self.pageLabel.setText(self.tr(" / {0}").format(max_page))
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
            # Prefer to resolve fields by matching the provided table to a tab entry
            fields = None
            try:
                for tab in self._tabs:
                    if tab.get('table') is table:
                        fields = tab.get('fields')
                        break
            except Exception:
                fields = None
            # fallback: use current tab if still unresolved
            if fields is None:
                try:
                    idx = self.tabWidget.currentIndex()
                    fields = self._tabs[idx].get("fields") if self._tabs else self.fields
                except Exception:
                    fields = self.fields
        table.clearContents()
        try:
            from qgis.core import QgsMessageLog
            QgsMessageLog.logMessage(f"set_feature_items: table={table} fields_count={len(fields) if fields else 0} features_count={len(features)}", "GEO-search-plugin", 0)
        except Exception:
            pass

        # Defensive fallback: if no fields were provided, attempt to derive them from
        # the features (prefer QgsFields from the first feature) or the table's layer.
        if not fields:
            try:
                if features:
                    f0 = features[0]
                    try:
                        derived = list(f0.fields())
                        if derived:
                            fields = derived
                    except Exception:
                        # fallback: try to read attribute keys via .attributes() and create
                        # a minimal list of objects with name() via simple wrappers
                        try:
                            attr_names = []
                            try:
                                # try feature.fields().names() if available
                                attr_names = [f.name() for f in f0.fields()]
                            except Exception:
                                # last resort: use indices
                                attr_names = []
                            if attr_names:
                                # create simple anonymous objects with name() method via lambda class
                                class _FakeField:
                                    def __init__(self, n):
                                        self._n = n
                                    def name(self):
                                        return self._n
                                    def displayName(self):
                                        return self._n
                                fields = [_FakeField(n) for n in attr_names]
                        except Exception:
                            fields = []
                else:
                    fields = []
            except Exception:
                fields = []

        # If we derived fields, ensure the table has appropriate columns and headers
        try:
            if fields:
                # ensure column count matches
                try:
                    table.setColumnCount(len(fields))
                except Exception:
                    pass
                try:
                    # header labels: prefer displayName() if present, else name()
                    labels = []
                    for f in fields:
                        try:
                            labels.append(f.displayName())
                        except Exception:
                            try:
                                labels.append(f.name())
                            except Exception:
                                labels.append(str(f))
                    table.setHorizontalHeaderLabels([self.tr(label) for label in labels])
                except Exception:
                    pass
        except Exception:
            pass

        # show sample feature ids/attrs for debugging
        try:
            from qgis.core import QgsMessageLog
            sample_info = []
            for i, feat in enumerate(features[:3]):
                try:
                    sample_info.append({ 'id': feat.id(), 'attrs': { (f.name() if hasattr(f, 'name') else str(f)): feat[f.name()] if hasattr(f, 'name') else None for f in fields } })
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
            # After sizing to contents, ensure columns are not too narrow under Qt6.
            try:
                header = table.horizontalHeader()
                # enforce a sensible minimum column width
                try:
                    header.setMinimumSectionSize(60)
                except Exception:
                    pass
                # if total column widths are noticeably smaller than the table viewport,
                # let the last section stretch to avoid a single narrow column
                try:
                    total = 0
                    for c in range(table.columnCount()):
                        total += table.columnWidth(c)
                    viewport_w = table.viewport().width() if table.viewport() is not None else table.width()
                    if viewport_w > total * 1.1:
                        try:
                            header.setStretchLastSection(True)
                        except Exception:
                            pass
                except Exception:
                    pass
            except Exception:
                pass
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
