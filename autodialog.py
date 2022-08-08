# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import QTableWidgetItem


class AutoDialog:
    def __init__(self, table, fields=[], page_limit=100):
        self.data_role = 15
        self.page_limit = page_limit
        self.fields = fields
        self.table = table
        self.set_fields(fields)

    def set_fields(self, fields):
        heads = len(fields)
        self.table.setColumnCount(heads)
        self.table.setHorizontalHeaderLabels([field.displayName() for field in fields])
        header = self.table.horizontalHeader()
        for i in range(len(fields)):
            header.setSectionResizeMode(i, header.Stretch)
        self.fields = fields

    def set_features(self, features):
        len_features = len(features)
        # ページチェック
        if len_features <= self.page_limit:
            rows = len_features
        else:
            rows = self.page_limit
        self.table.setRowCount(rows)

        for index, feature in enumerate(features):
            for column, field in enumerate(self.fields):
                # 検索結果をテーブルにセットしていく
                item = QTableWidgetItem()
                item.setText(unicode(feature.attribute(field.name())))
                item.setData(self.data_role, feature.id())
                self.table.setItem(index, column, item)
