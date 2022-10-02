# -*- coding: utf-8 -*-
import os
import math

from qgis.PyQt.QtCore import QDate
from qgis.PyQt.QtWidgets import QDialog, QTableWidgetItem
from qgis.PyQt import uic


UI_FILE = "result.ui"

#検索結果
class ResultDialog(QDialog):
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

    def next_page(self):
        value = self.pageBox.value()
        self.pageBox.setValue(value + 1)

    def prev_page(self):
        value = self.pageBox.value()
        self.pageBox.setValue(value - 1)

    def move_page(self, page):
        s = (page - 1) * self.page_limit
        e = page * self.page_limit
        features = self.features[s:e]

        rows = len(features)
        if rows > self.page_limit:
            rows = self.page_limit
        self.tableWidget.setRowCount(rows)
        self.tableWidget.setVerticalHeaderLabels([f"{i}" for i in range(s, e)])
        self.set_feature_items(features)

    def set_features(self, fields, features):
        self.features = features
        self.fields = fields
        self.setWindowTitle(f"検索結果: {len(self.features)}件")
        heads = len(self.fields)
        self.tableWidget.setColumnCount(heads)
        self.tableWidget.setHorizontalHeaderLabels(
            [field.displayName() for field in self.fields]
        )
        header = self.tableWidget.horizontalHeader()
        for i in range(len(fields)):
            header.setSectionResizeMode(i, header.Stretch)
        max_page = math.ceil(len(self.features) / self.page_limit)
        self.pageBox.setMaximum(max_page)
        self.pageLabel.setText(f" / {max_page}")

        self.pageBox.setValue(1)
        self.move_page(1)

    def set_feature_items(self, features):
        self.tableWidget.clearContents()
        for index, feature in enumerate(features):
            for column, field in enumerate(self.fields):
                item = self.create_item(field, feature)
                self.tableWidget.setItem(index, column, item)

    def create_item(self, field, feature):
        # 検索結果をテーブルにセットしていく
        # フィールド名を取得
        name = field.name()
        item = QTableWidgetItem()
        # アイテムに指定フィールドの属性をセット
        # 日付の場合の場合はも書式を指定して文字列に変換
        if isinstance(feature.attribute(name),QDate):
            item.setText(QDate.toString(feature.attribute(name),'yyyy/M/d')) 
        else:
        # その他はそのまま
            item.setText(unicode(feature.attribute(name)))     
        item.setData(self.data_role, feature.id())
        return item
