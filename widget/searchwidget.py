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


class SearchWidget(QWidget):
    def __init__(self, setting, parent=None):
        super(SearchWidget, self).__init__(parent=parent)
        search_fields = setting.get("SearchFields")
        if not search_fields:
            search_fields = [setting.get("SearchField")]
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
        layout = QHBoxLayout()
        for widget in widgets:
            layout.addWidget(widget)
        self.setLayout(layout)


# 通常検索
class SearchTextWidget(SearchWidget):
    # TODO: テキスト編集時に検索動作
    # 住所と面積検索のUI
    def create_widgets(self, setting):
        self.labels = []
        self.search_widgets = []
        for field in setting:
            label, edit = self.create_widget(field)
            self.labels.append(label)
            self.search_widgets.append(edit)

        widgets = []
        for i in zip(self.labels, self.search_widgets):
            for j in i:
                widgets.append(j)
        return widgets

    def create_widget(self, field):
        label = QLabel("{}: ".format(field["ViewName"]))
        line_edit = QLineEdit()
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
        self.code_table.setSelectionBehavior(QTableWidget.SelectRows)
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
