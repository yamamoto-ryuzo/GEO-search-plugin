# -*- coding: utf-8 -*-
"""
Simple settings dialog for GEO-search-plugin.
日本語コメント: 設定ダイアログの実装ファイル。必要な設定ウィジェットをここに追加してください。
"""
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton


class SettingsDialog(QDialog):
    def __init__(self, parent=None, iface=None):
        """設定ダイアログの初期化。

        :param parent: 親ウィンドウ
        :param iface: QGIS iface を渡すとダイアログから map/canvas にアクセスできます
        """
        super(SettingsDialog, self).__init__(parent=parent)
        # iface を保持しておく（将来的に地図情報を参照する際に使用）
        self.iface = iface

        self.setWindowTitle(self.tr("Settings"))
        self.setMinimumSize(420, 140)

        layout = QVBoxLayout(self)

        # 説明ラベル（ここに設定項目ウィジェットを追加してください）
        info = QLabel(self.tr("Settings dialog: add options here."), self)
        layout.addWidget(info)

        # 下部に OK / Cancel を右寄せで配置
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton(self.tr("OK"), self)
        cancel_btn = QPushButton(self.tr("Cancel"), self)
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    # 必要なら保存用のメソッドやプロパティをここに追加
