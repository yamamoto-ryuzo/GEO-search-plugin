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
        # display mode: 'table' or 'form'
        self.display_mode = 'table'
        try:
            # connect UI button if present in the .ui
            self.modeToggleButton.setText(self.tr('Form'))
            self.modeToggleButton.clicked.connect(self._toggle_display_mode)
        except Exception:
            try:
                # fallback: ensure attribute exists
                getattr(self, 'modeToggleButton', None)
            except Exception:
                pass
        # ensure top-level attribute combo (next to mode button) is hidden initially
        try:
            if getattr(self, 'formAttributeCombo', None) is not None:
                try:
                    self.formAttributeCombo.setVisible(False)
                except Exception:
                    pass
        except Exception:
            pass

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
        # if a static formWidget exists in the UI, ensure it's hidden when showing tables
        try:
            if getattr(self, 'formWidget', None) is not None:
                try:
                    self.formWidget.setVisible(False)
                except Exception:
                    pass
        except Exception:
            pass
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
        # ensure the main tab widget is visible (hide any static form widget)
        try:
            if getattr(self, 'formWidget', None) is not None:
                try:
                    self.formWidget.setVisible(False)
                    try:
                        self.tabWidget.setVisible(True)
                    except Exception:
                        pass
                except Exception:
                    pass
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

    def set_form(self, fields, features):
        """Placeholder API: set results for 'form' display mode (single layer).
        This stub records provided data and shows the dialog; UI rendering
        for form mode is implemented later.
        """
        # For single-layer form mode, delegate to set_form_by_layer with single entry
        try:
            self.set_form_by_layer([(None, fields, features)])
        except Exception:
            # fallback minimal behavior
            try:
                self._form_tabs = [{"layer": None, "fields": fields, "features": features}]
                self.setWindowTitle(self.tr("Search Results (Form): {0} items").format(len(features) if features else 0))
                try:
                    self.show()
                except Exception:
                    pass
            except Exception:
                pass

    def set_form_by_layer(self, layers_with_features):
        """Placeholder API: set results for 'form' display mode with per-layer tabs.
        Records the provided structures for later rendering.
        """
        # Concrete implementation: left = list of first-field values across features,
        # right = attribute display for selected feature.
        try:
            self._form_tabs = []
            total = 0
            for layer, fields, features in layers_with_features:
                try:
                    features = list(features) if features is not None else []
                except Exception:
                    features = []
                total += len(features) if features else 0
                self._form_tabs.append({"layer": layer, "fields": fields, "features": features})

            first_tab = self._form_tabs[0] if self._form_tabs else None
            if not first_tab:
                self.setWindowTitle(self.tr("Search Results (Form): 0 items"))
                try:
                    self.show()
                except Exception:
                    pass
                return

            features = first_tab.get('features') or []
            fields = first_tab.get('fields') or []
            if not features:
                self.setWindowTitle(self.tr("Search Results (Form): 0 items"))
                try:
                    self.show()
                except Exception:
                    pass
                return

            # determine first field name
            first_field_name = None
            try:
                if fields:
                    f0 = fields[0]
                    first_field_name = f0.name() if hasattr(f0, 'name') else str(f0)
                else:
                    # try derive from feature.fields()
                    try:
                        ff = list(features[0].fields())
                        if ff:
                            first_field_name = ff[0].name() if hasattr(ff[0], 'name') else str(ff[0])
                    except Exception:
                        first_field_name = None
            except Exception:
                first_field_name = None

            # If the UI provides a `formWidget` with `formFieldList` and `formValueText`, prefer that.
            try:
                if getattr(self, 'formWidget', None) is not None and getattr(self, 'formFieldList', None) is not None and getattr(self, 'formValueText', None) is not None:
                    list_widget = self.formFieldList
                    value_widget = self.formValueText
                    # ensure it's visible and hide the tabWidget
                    try:
                        self.tabWidget.setVisible(False)
                    except Exception:
                        pass
                    try:
                        self.formWidget.setVisible(True)
                    except Exception:
                        pass
                    try:
                        splitter = getattr(self, 'formWidget', None)
                        if splitter is not None:
                            try:
                                # prefer stretch factors
                                splitter.setStretchFactor(0, 2)
                                splitter.setStretchFactor(1, 8)
                            except Exception:
                                pass
                            try:
                                # ensure sizes respect the current widget width by using proportions
                                from qgis.PyQt.QtCore import QCoreApplication
                                QCoreApplication.processEvents()
                                total = splitter.width() or self.width() or 1000
                                left = int(total * 0.2)
                                right = max(1, total - left)
                                splitter.setSizes([left, right])
                            except Exception:
                                try:
                                    splitter.setSizes([200, 800])
                                except Exception:
                                    pass
                    except Exception:
                        pass
                else:
                    from qgis.PyQt.QtWidgets import QWidget, QHBoxLayout, QListWidget, QTextEdit, QListWidgetItem
                    container = QWidget(self)
                    layout = QHBoxLayout(container)
                    list_widget = QListWidget(container)
                    value_widget = QTextEdit(container)
                    value_widget.setReadOnly(True)
                    layout.addWidget(list_widget)
                    layout.addWidget(value_widget)
            except Exception:
                return

            # prepare combos if present
            table_combo = getattr(self, 'formTableCombo', None)
            column_combo = getattr(self, 'formColumnCombo', None)
            top_combo = getattr(self, 'formAttributeCombo', None)

            # helper to populate left list given a field name and feature list
            def _populate_left_for_field(field_name, feats=None):
                if feats is None:
                    feats = features
                self._form_feature_map = []
                try:
                    from qgis.PyQt.QtWidgets import QListWidgetItem
                except Exception:
                    QListWidgetItem = None
                try:
                    list_widget.clear()
                except Exception:
                    pass
                for feat in (feats or []):
                    try:
                        if field_name:
                            try:
                                v = feat.attribute(field_name)
                            except Exception:
                                try:
                                    v = feat[field_name]
                                except Exception:
                                    v = ''
                        else:
                            try:
                                v = feat.id()
                            except Exception:
                                v = ''
                        try:
                            if QListWidgetItem is not None:
                                item = QListWidgetItem(str(v))
                                try:
                                    item.setData(self.data_role, feat.id())
                                except Exception:
                                    pass
                                list_widget.addItem(item)
                            else:
                                list_widget.addItem(str(v))
                        except Exception:
                            try:
                                list_widget.addItem(str(v))
                            except Exception:
                                pass
                        self._form_feature_map.append(feat)
                    except Exception:
                        continue

            # initially populate with the first_field_name
            _populate_left_for_field(first_field_name, features)

            # connect selection -> show attributes of selected feature
            def _on_select():
                try:
                    row = list_widget.currentRow()
                    if row < 0 or row >= len(self._form_feature_map):
                        value_widget.setPlainText('')
                        return
                    f = self._form_feature_map[row]
                    # build attribute text
                    lines = []
                    # prefer fields order if available
                    try:
                        fld_objs = fields if fields else list(f.fields())
                    except Exception:
                        fld_objs = []
                    if fld_objs:
                        for fo in fld_objs:
                            try:
                                fname = fo.name() if hasattr(fo, 'name') else str(fo)
                                try:
                                    val = f.attribute(fname)
                                except Exception:
                                    try:
                                        val = f[fname]
                                    except Exception:
                                        val = ''
                                lines.append(f"{fname}: {val}")
                            except Exception:
                                continue
                    else:
                        # fallback: use attribute names from feature
                        try:
                            for k in f.fields():
                                try:
                                    kn = k.name() if hasattr(k, 'name') else str(k)
                                    try:
                                        val = f.attribute(kn)
                                    except Exception:
                                        val = ''
                                    lines.append(f"{kn}: {val}")
                                except Exception:
                                    continue
                        except Exception:
                            # final fallback: attributes() list
                            try:
                                attrs = f.attributes()
                                for i, v in enumerate(attrs):
                                    lines.append(f"{i}: {v}")
                            except Exception:
                                lines = [str(f)]
                    value_widget.setPlainText('\n'.join(lines))
                except Exception:
                    try:
                        value_widget.setPlainText('')
                    except Exception:
                        pass

            list_widget.currentRowChanged.connect(lambda _: _on_select())

            # wire column_combo to update left list when available
            try:
                if column_combo is not None:
                    def _on_column(idx):
                        try:
                            if idx < 0:
                                return
                            try:
                                col = column_combo.itemText(idx)
                            except Exception:
                                col = None
                            if col:
                                _populate_left_for_field(col, self._form_feature_map or features)
                        except Exception:
                            pass
                    column_combo.currentIndexChanged.connect(_on_column)
            except Exception:
                pass

            # wire table_combo to switch feature set and refresh column list
            try:
                if table_combo is not None:
                    try:
                        table_combo.clear()
                        for t in self._form_tabs:
                            layer = t.get('layer')
                            try:
                                name = layer.name() if layer is not None else self.tr('Results')
                            except Exception:
                                name = str(layer)
                            table_combo.addItem(str(name))

                        def _on_table(idx):
                            try:
                                if idx < 0 or idx >= len(self._form_tabs):
                                    return
                                sel = self._form_tabs[idx]
                                feats = sel.get('features') or []
                                flds = sel.get('fields') or []
                                # populate column combo
                                if column_combo is not None:
                                    try:
                                        column_combo.clear()
                                        cols = [f.name() if hasattr(f, 'name') else str(f) for f in flds]
                                        for c in cols:
                                            column_combo.addItem(str(c))
                                    except Exception:
                                        pass
                                # repopulate left using first column or fid
                                try:
                                    if flds:
                                        first = flds[0].name() if hasattr(flds[0], 'name') else str(flds[0])
                                        _populate_left_for_field(first, feats)
                                    else:
                                        _populate_left_for_field(None, feats)
                                except Exception:
                                    _populate_left_for_field(None, feats)
                            except Exception:
                                pass

                        table_combo.currentIndexChanged.connect(_on_table)
                        if table_combo.count() > 0:
                            table_combo.setCurrentIndex(0)
                    except Exception:
                        pass
            except Exception:
                pass

            # wire top-level attribute combo to mirror column choices if present
            try:
                if top_combo is not None:
                    try:
                        # if column_combo exists, copy its items
                        top_combo.clear()
                        cols = []
                        try:
                            if column_combo is not None and column_combo.count() > 0:
                                for i in range(column_combo.count()):
                                    top_combo.addItem(column_combo.itemText(i))
                            else:
                                # derive from fields
                                if fields:
                                    for f in fields:
                                        name = f.name() if hasattr(f, 'name') else (f.displayName() if hasattr(f, 'displayName') else str(f))
                                        top_combo.addItem(str(name))
                        except Exception:
                            pass
                        try:
                            top_combo.setVisible(True)
                        except Exception:
                            pass
                        def _on_top(idx):
                            try:
                                if idx < 0:
                                    return
                                try:
                                    name = top_combo.itemText(idx)
                                except Exception:
                                    name = None
                                if name and column_combo is not None:
                                    # find same name in column_combo
                                    try:
                                        for i in range(column_combo.count()):
                                            if column_combo.itemText(i) == name:
                                                column_combo.setCurrentIndex(i)
                                                return
                                    except Exception:
                                        pass
                                    # fallback: directly populate left
                                _populate_left_for_field(name)
                            except Exception:
                                pass
                        try:
                            top_combo.currentIndexChanged.connect(_on_top)
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception:
                pass

            # clear existing tabs and insert the container as a single tab
            try:
                while self.tabWidget.count() > 0:
                    self.tabWidget.removeTab(0)
            except Exception:
                pass
            try:
                self.tabWidget.addTab(container, self.tr('Form'))
            except Exception:
                try:
                    self.tabWidget.insertTab(0, container, self.tr('Form'))
                except Exception:
                    pass

            # update internal tab mapping to point to our list widget as table for selection handlers
            try:
                self._tabs = [{"layer": first_tab.get('layer'), "fields": fields, "features": features, "table": list_widget}]
                self.current_table = list_widget
            except Exception:
                pass

            # auto-select first item to show its attributes
            try:
                if list_widget.count() > 0:
                    list_widget.setCurrentRow(0)
            except Exception:
                pass

            try:
                from qgis.core import QgsMessageLog
                QgsMessageLog.logMessage(f"set_form_by_layer: built form list with {len(self._form_feature_map)} items (first_field={first_field_name})", "GEO-search-plugin", 0)
            except Exception:
                pass

            self.setWindowTitle(self.tr("Search Results (Form): {0} items").format(total))
            try:
                self.show()
            except Exception:
                pass
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

    def _toggle_display_mode(self):
        """Toggle between table and form display modes.
        When switching to form mode we call the placeholder `set_form_by_layer`.
        Switching back restores the table via `set_features_by_layer`.
        """
        try:
            if getattr(self, 'display_mode', 'table') == 'table':
                # build layer tuples from current tabs
                layers = []
                for tab in getattr(self, '_tabs', []) or []:
                    layers.append((tab.get('layer'), tab.get('fields'), tab.get('features')))
                # call placeholder form API
                try:
                    self.set_form_by_layer(layers)
                except Exception:
                    pass
                self.display_mode = 'form'
                try:
                    self.modeToggleButton.setText(self.tr('Table'))
                except Exception:
                    try:
                        self.modeToggleButton.setText('Table')
                    except Exception:
                        pass
                # populate and show the top-level attribute combo if present
                try:
                    combo = getattr(self, 'formAttributeCombo', None)
                    if combo is not None:
                        try:
                            combo.clear()
                            names = []
                            try:
                                tabs = getattr(self, '_form_tabs', []) or []
                                if tabs:
                                    flds = tabs[0].get('fields') or []
                                    names = [ (f.displayName() if hasattr(f, 'displayName') else (f.name() if hasattr(f, 'name') else str(f))) for f in flds ]
                                # fallback derive from features
                                if not names:
                                    try:
                                        feats = tabs[0].get('features') or []
                                        if feats:
                                            ff = list(feats[0].fields())
                                            names = [f.name() if hasattr(f, 'name') else str(f) for f in ff]
                                    except Exception:
                                        pass
                            except Exception:
                                names = []
                            for n in names:
                                combo.addItem(str(n))
                            try:
                                combo.setVisible(True)
                            except Exception:
                                pass

                            # sync selection to the internal formColumnCombo if present
                            def _on_attr(idx):
                                try:
                                    if idx < 0:
                                        return
                                    try:
                                        name = combo.itemText(idx)
                                    except Exception:
                                        name = None
                                    if not name:
                                        return
                                    cc = getattr(self, 'formColumnCombo', None)
                                    if cc is not None:
                                        try:
                                            for i in range(cc.count()):
                                                if cc.itemText(i) == name:
                                                    cc.setCurrentIndex(i)
                                                    return
                                            cc.addItem(name)
                                            cc.setCurrentIndex(cc.count() - 1)
                                        except Exception:
                                            pass
                                except Exception:
                                    pass

                            try:
                                combo.currentIndexChanged.connect(_on_attr)
                            except Exception:
                                pass
                            try:
                                if combo.count() > 0:
                                    combo.setCurrentIndex(0)
                            except Exception:
                                pass
                        except Exception:
                            pass
                except Exception:
                    pass
            else:
                # restore table view
                # prefer using stored _form_tabs if available
                source = getattr(self, '_form_tabs', None)
                if source:
                    layers = []
                    for t in source:
                        layers.append((t.get('layer'), t.get('fields'), t.get('features')))
                    try:
                        self.set_features_by_layer(layers)
                    except Exception:
                        pass
                else:
                    # fallback to current _tabs
                    layers = []
                    for tab in getattr(self, '_tabs', []) or []:
                        layers.append((tab.get('layer'), tab.get('fields'), tab.get('features')))
                    try:
                        self.set_features_by_layer(layers)
                    except Exception:
                        pass
                self.display_mode = 'table'
                try:
                    self.modeToggleButton.setText(self.tr('Form'))
                except Exception:
                    try:
                        self.modeToggleButton.setText('Form')
                    except Exception:
                        pass
                # hide top-level attribute combo when returning to table view
                try:
                    if getattr(self, 'formAttributeCombo', None) is not None:
                        try:
                            self.formAttributeCombo.setVisible(False)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass
