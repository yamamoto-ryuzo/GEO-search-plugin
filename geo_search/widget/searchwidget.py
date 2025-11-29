# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QWidget,
    QLineEdit,
    QLabel,
    QHBoxLayout,
    QTableWidget,
    QVBoxLayout,
    QButtonGroup,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpacerItem,
    QLayout,
    QLayoutItem,
)
import importlib


class SearchWidget(QWidget):
    def __init__(self, setting, parent=None):
        super(SearchWidget, self).__init__(parent=parent)
        # keep setting so widgets can show per-tab configuration (angle/scale)
        self.setting = setting or {}
        search_fields = setting.get("SearchFields")
        if not search_fields:
            search_field = setting.get("SearchField")
            # If SearchField is empty, use only "All"
            if not search_field or (isinstance(search_field, dict) and not search_field):
                search_fields = [{"ViewName": "All", "all": True}]
            else:
                search_fields = [search_field]
        widgets = self.create_widgets(search_fields)
        self._dialog = None
        self.init_layout(widgets)

    @property
    def dialog(self):
        if not self._dialog:
            parent = self.parent()
            while not isinstance(parent, QDialog):
                if not parent:
                    return
                parent = parent.parent()
            self._dialog = parent
        return self._dialog

    def create_widgets(self, setting):
        raise NotImplementedError

    def create_widget(self, setting):
        raise NotImplementedError

    def init_layout(self, widgets):
        # create an outer vertical layout so we can place the input widgets
        # on the first row and the angle/scale display on the second row
        outer = QVBoxLayout()
        inner = QHBoxLayout()
        for widget in widgets:
            # preserve any QLayout items by adding layout or widget appropriately
            try:
                if isinstance(widget, QLayout):
                    inner.addLayout(widget)
                else:
                    inner.addWidget(widget)
            except Exception:
                try:
                    inner.addWidget(widget)
                except Exception:
                    pass

        outer.addLayout(inner)
        # add angle/scale display on a new row under the inputs
        try:
            outer.addLayout(self._angle_scale_layout())
        except Exception:
            pass

        self.setLayout(outer)

    def _angle_scale_layout(self):
        """Return a QHBoxLayout containing angle and scale labels based on self.setting."""
        # Use a vertical layout: angle/scale on top row, source label on second row.
        from qgis.PyQt.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout

        v = QVBoxLayout()
        h = QHBoxLayout()
        try:
            angle = self.setting.get('angle') if isinstance(self.setting, dict) else None
        except Exception:
            angle = None
        try:
            scale = self.setting.get('scale') if isinstance(self.setting, dict) else None
        except Exception:
            scale = None

        if angle is None:
            angle_text = self.tr("Angle: Not specified")
        else:
            try:
                angle_text = self.tr("Angle: {0}°").format(float(angle))
            except Exception:
                angle_text = self.tr("Angle: {0}").format(angle)

        if scale is None:
            scale_text = self.tr("Scale: Not specified")
        else:
            try:
                s = float(scale)
                if abs(s - int(s)) < 1e-6:
                    scale_text = self.tr("Scale: {0}").format(int(s))
                else:
                    scale_text = self.tr("Scale: {0}").format(s)
            except Exception:
                scale_text = self.tr("Scale: {0}").format(scale)

        la = QLabel(angle_text)
        ls = QLabel(scale_text)
        la.setStyleSheet("color: #333333; font-size: 11px;")
        ls.setStyleSheet("color: #333333; font-size: 11px;")
        h.addWidget(la)
        h.addWidget(ls)
        # stretch to push labels to the left
        try:
            from qgis.PyQt.QtWidgets import QSpacerItem, QSizePolicy
            spacer = QSpacerItem(20, 10, QSizePolicy.Expanding, QSizePolicy.Minimum)
            # layouts accept addItem
            h.addItem(spacer)
        except Exception:
            pass

        v.addLayout(h)

        # Per-tab source label shown under the angle/scale row.
        try:
            src = None
            if isinstance(self.setting, dict):
                src = self.setting.get('_source')
        except Exception:
            src = None

        src_text = ""
        try:
            if src:
                if src == 'geo_search_json':
                    short = 'geo_search_json'
                elif src == 'project variable':
                    short = 'project variable'
                elif src == 'setting.json':
                    short = 'setting.json'
                else:
                    short = str(src)
                src_text = f"[{short}]"
        except Exception:
            src_text = ""

        src_label = QLabel(src_text)
        src_label.setStyleSheet("color: #666666; font-size: 10px;")
        try:
            from qgis.PyQt.QtCore import Qt
            src_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        except Exception:
            pass

        v.addWidget(src_label)
        return v


# 通常検索
class SearchTextWidget(SearchWidget):
    # TODO: テキスト編集時に検索動作
    # 住所と面積検索のUI
    def create_widgets(self, setting):
        self.labels = []
        self.search_widgets = []
        all_field_index = None
        for idx, field in enumerate(setting):
            label, edit = self.create_widget(field)
            self.labels.append(label)
            self.search_widgets.append(edit)
            if field.get("all"):
                all_field_index = idx

        # QLineEdit for "All" field
        all_field_edit = self.search_widgets[all_field_index] if all_field_index is not None else None

        # Enable only "All" or other fields
        def update_fields():
            if all_field_edit and all_field_edit.text():
                # Disable all except "All"
                for i, edit in enumerate(self.search_widgets):
                    if i != all_field_index:
                        edit.setDisabled(True)
            else:
                for i, edit in enumerate(self.search_widgets):
                    if i != all_field_index:
                        edit.setDisabled(False)

        if all_field_edit:
            all_field_edit.textChanged.connect(update_fields)
            update_fields()

        widgets = []
        for i in zip(self.labels, self.search_widgets):
            for j in i:
                widgets.append(j)
        return widgets

    def create_widget(self, field):
        # OR検索対象のフィールド名を表示
        view_name = field.get("ViewName", "")
        if ":" in view_name and "OR検索" in view_name:
            # OR検索の場合は既に対象フィールドが含まれているので、そのまま表示
            label = QLabel(str(view_name))
        else:
            label = QLabel(f"{view_name}: ")

        line_edit = QLineEdit()
        # For "All" field, set placeholder
        if field.get("all"):
            line_edit.setPlaceholderText(self.tr("Search all fields"))
        # OR検索の場合はプレースホルダーテキストでヒントを表示
        elif ":" in view_name and "OR検索" in view_name:
            line_edit.setPlaceholderText(self.tr("OR search for multiple fields"))
        return label, line_edit


# 地番検索
class SearchTibanWidget(SearchTextWidget):
    def init_layout(self, widgets):
        layout = QVBoxLayout()
        for widget in widgets:
            if isinstance(widget, QLayout):
                layout.addLayout(widget)
            else:
                layout.addWidget(widget)
        # add angle/scale display for this widget
        try:
            layout.addLayout(self._angle_scale_layout())
        except Exception:
            pass
        self.setLayout(layout)

    def create_widgets(self, setting):
        self.labels = []
        self.search_widgets = []
        search_layout = QHBoxLayout()
        input_layout = QVBoxLayout()
        self.type_button_group = QButtonGroup()
        self.perfect_button = QRadioButton(self.tr("Exact Match"))
        self.about_button = QRadioButton(self.tr("Fuzzy Search"))
        self.type_button_group.addButton(self.perfect_button)
        self.type_button_group.addButton(self.about_button)

        self.perfect_button.setChecked(True)

        type_layout = QHBoxLayout()
        type_layout.addWidget(self.perfect_button)
        type_layout.addWidget(self.about_button)

        input_layout.addLayout(type_layout)
        for field in setting:
            label, edit = self.create_widget(field)
            self.labels.append(label)
            self.search_widgets.append(edit)
            input_layout.addWidget(label)
            input_layout.addWidget(edit)

        self.code_table = QTableWidget()
        self.code_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.code_table.setSelectionMode(QTableWidget.SingleSelection)
        # Qt5: QTableWidget.SelectRows (alias of QAbstractItemView.SelectRows)
        # Qt6: enum moved to QAbstractItemView.SelectionBehavior.SelectRows
        try:
            qt_compat = importlib.import_module('geo_search.qt_compat')
        except Exception:
            qt_compat = None

        sel = None
        if qt_compat is not None:
            try:
                sel = qt_compat.get_enum_value(qt_compat.QtWidgets.QAbstractItemView, 'SelectRows')
            except Exception:
                sel = None
            if sel is None:
                try:
                    sel = qt_compat.get_enum_value(qt_compat.QtWidgets.QTableWidget, 'SelectRows')
                except Exception:
                    sel = None

        if sel is not None:
            try:
                self.code_table.setSelectionBehavior(sel)
            except Exception:
                try:
                    self.code_table.setSelectionBehavior(1)
                except Exception:
                    pass
        else:
            try:
                self.code_table.setSelectionBehavior(1)
            except Exception:
                pass
        v_header = self.code_table.verticalHeader()
        v_header.setVisible(False)
        search_layout.addLayout(input_layout)
        search_layout.addWidget(self.code_table)

        widgets = [search_layout]
        return widgets


# 所有者検索
class SearchOwnerWidget(SearchTextWidget):
    def init_layout(self, widgets):
        layout = QVBoxLayout()
        for widget in widgets:
            if isinstance(widget, QLayout):
                layout.addLayout(widget)
            elif isinstance(widget, QLayoutItem):
                layout.addItem(widget)
            else:
                layout.addWidget(widget)

        # add angle/scale display for this widget
        try:
            layout.addLayout(self._angle_scale_layout())
        except Exception:
            pass

        self.setLayout(layout)

    def create_widgets(self, setting):
        self.label = QLabel(self.tr("Owner Search"))
        self.label.setStyleSheet("font-weight: bold;")
        self.line_edit = QLineEdit()

        self.search_widgets = [self.line_edit]
        self.check_list = []
        self.type_button_group = QButtonGroup()
        self.forward_button = QRadioButton(self.tr("Partial Match"))
        self.parts_button = QRadioButton(self.tr("Forward Match"))
        self.type_button_group.addButton(self.forward_button)
        self.type_button_group.addButton(self.parts_button)

        self.forward_button.setChecked(True)

        label_layout = QHBoxLayout()
        label_layout.addWidget(self.label)
        label_layout.addWidget(self.forward_button)
        label_layout.addWidget(self.parts_button)

        self.QHBox = QHBoxLayout()
        self.button_group = QButtonGroup()
        for i, field in enumerate(setting):
            check = QPushButton(field["ViewName"])
            check.setCheckable(True)
            check.setFlat(True)
            if i == 0:
                check.setChecked(True)
            if field.get("Default"):
                check.setChecked(True)
            self.check_list.append(check)
            self.button_group.addButton(check)
            self.QHBox.addWidget(check)
        spacer = QSpacerItem(20, 40, QSizePolicy.Expanding)

        return [label_layout, self.QHBox, self.line_edit, spacer]
