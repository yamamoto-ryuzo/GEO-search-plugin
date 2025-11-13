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
        from qgis.PyQt.QtWidgets import QLabel, QHBoxLayout

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
            angle_text = "角度: 未指定"
        else:
            try:
                angle_text = f"角度: {float(angle)}°"
            except Exception:
                angle_text = f"角度: {angle}"

        if scale is None:
            scale_text = "スケール: 未指定"
        else:
            try:
                # show as integer when possible
                s = float(scale)
                if abs(s - int(s)) < 1e-6:
                    scale_text = f"スケール: {int(s)}"
                else:
                    scale_text = f"スケール: {s}"
            except Exception:
                scale_text = f"スケール: {scale}"

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
        return h


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
            label = QLabel("{}".format(view_name))
        else:
            label = QLabel("{}: ".format(view_name))
            
        line_edit = QLineEdit()
        # For "All" field, set placeholder
        if field.get("all"):
            line_edit.setPlaceholderText("Search all fields")
        # OR検索の場合はプレースホルダーテキストでヒントを表示
        elif ":" in view_name and "OR検索" in view_name:
            line_edit.setPlaceholderText("複数フィールドをOR検索します")
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
        self.perfect_button = QRadioButton("完全一致")
        self.about_button = QRadioButton("あいまい検索")
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
        self.label = QLabel("所有者検索")
        self.label.setStyleSheet("font-weight: bold;")
        self.line_edit = QLineEdit()

        self.search_widgets = [self.line_edit]
        self.check_list = []
        self.type_button_group = QButtonGroup()
        self.forward_button = QRadioButton("部分一致")
        self.parts_button = QRadioButton("前方一致")
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
