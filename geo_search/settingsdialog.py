# -*- coding: utf-8 -*-
"""
Simple settings dialog for GEO-search-plugin.
日本語コメント: 設定ダイアログの実装ファイル。必要な設定ウィジェットをここに追加してください。
"""
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from qgis.PyQt.QtWidgets import QInputDialog, QMessageBox, QComboBox, QFileDialog
import os
import re


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

        # テーマ操作用コントロール（ユーザーテーマの保存 / 読込）
        theme_ctrl = QHBoxLayout()
        save_user_btn = QPushButton(self.tr("Save User Theme..."), self)
        load_user_btn = QPushButton(self.tr("Load User Theme..."), self)
        theme_ctrl.addWidget(save_user_btn)
        theme_ctrl.addWidget(load_user_btn)
        theme_ctrl.addStretch()
        layout.addLayout(theme_ctrl)

        # export/import buttons removed per request
        save_user_btn.clicked.connect(self.save_user_theme_dialog)
        load_user_btn.clicked.connect(self.load_user_theme_dialog)

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
    def _safe_filename(self, s: str, maxlen: int = 120) -> str:
        """ファイル名に使えるように安全化する（日本語コメント）"""
        if not s:
            return "unnamed"
        r = re.sub(r'[^A-Za-z0-9\-_.]', '_', s)
        return r[:maxlen]

    def _qmsg_button(self, name: str):
        """QMessageBox のボタン列挙を互換的に取得するヘルパ。

        Qt6 / PyQt6 では QMessageBox.StandardButton.Yes のように
        ネストされた enum を使う必要がある場合があるため、まず
        それを試し、なければ従来の QMessageBox.Yes を返す。
        """
        try:
            sb = getattr(QMessageBox, 'StandardButton', None)
            if sb is not None:
                v = getattr(sb, name, None)
                if v is not None:
                    return v
        except Exception:
            pass
        try:
            return getattr(QMessageBox, name)
        except Exception:
            return None

    def update_theme_list(self):
        """プロジェクトの map themes をコンボに読み込む"""
        try:
            from qgis.core import QgsProject
            project = QgsProject.instance()
            tc = project.mapThemeCollection()
            try:
                raw = tc.mapThemes()
            except Exception:
                raw = []
        except Exception:
            raw = []

        names = []
        for t in (raw or []):
            try:
                if isinstance(t, str):
                    names.append(t)
                else:
                    if hasattr(t, 'name') and callable(getattr(t, 'name')):
                        names.append(t.name())
                    elif hasattr(t, 'title') and callable(getattr(t, 'title')):
                        names.append(t.title())
                    else:
                        names.append(str(t))
            except Exception:
                continue
        # テーマ一覧は返す。UI 表示は不要なのでコンボ操作は行わない
        return names

    def export_themes_dialog(self):
        """デフォルトをプロジェクト内 `themes/` にセットして、ユーザーが保存先を選べるようにする"""
        try:
            from qgis.core import QgsProject
            project = QgsProject.instance()
            proj_file = project.fileName() or ""
            if not proj_file:
                QMessageBox.warning(self, self.tr("Export Themes"), self.tr("Please save the QGIS project before exporting themes."))
                return
            default_dir = os.path.join(os.path.dirname(proj_file), "themes")
            # プロジェクト変数に保存された保存先があればそれを優先
            key_group = 'GEO-search-plugin'
            key_field = 'themes_dir'
            try:
                # まず readEntry を試す（より互換性の高い保存先）
                ok, val = project.readEntry(key_group, key_field, default_dir)
                if ok and val:
                    default_dir = str(val)
                else:
                    # フォールバックで customProperty を確認
                    try:
                        prev = project.customProperty(f"{key_group}:{key_field}")
                        if prev:
                            default_dir = str(prev)
                    except Exception:
                        pass
            except Exception:
                try:
                    prev = project.customProperty(f"{key_group}:{key_field}")
                    if prev:
                        default_dir = str(prev)
                except Exception:
                    pass
            os.makedirs(default_dir, exist_ok=True)
            # ユーザーに出力先を選ばせる（デフォルトは project/themes またはプロジェクト変数）
            d = QFileDialog.getExistingDirectory(self, self.tr("Select export directory"), default_dir)
            if not d:
                return
            # 選択をプロジェクト変数に保存（writeEntry を優先、ダメなら setCustomProperty）
            try:
                try:
                    project.writeEntry(key_group, key_field, d)
                except Exception:
                    # writeEntry で失敗したら customProperty に保存
                    try:
                        project.setCustomProperty(f"{key_group}:{key_field}", d)
                    except Exception:
                        pass
            except Exception:
                pass
            exported = self.export_all_project_themes(d)
            if exported:
                QMessageBox.information(self, self.tr("Export Themes"), self.tr("Exported %n files", None, len(exported)))
            else:
                QMessageBox.information(self, self.tr("Export Themes"), self.tr("No themes exported."))
        except Exception as e:
            QMessageBox.warning(self, self.tr("Export Themes"), str(e))

    def import_themes_dialog(self):
        """デフォルトをプロジェクト内 `themes/` にセットして、ユーザーが読み込み元を選べるようにする"""
        try:
            from qgis.core import QgsProject
            project = QgsProject.instance()
            proj_file = project.fileName() or ""
            if not proj_file:
                QMessageBox.warning(self, self.tr("Import Themes"), self.tr("Please save the QGIS project before importing themes."))
                return
            default_dir = os.path.join(os.path.dirname(proj_file), "themes")
            # プロジェクト変数に保存された読み込み元があればそれを優先
            key_group = 'GEO-search-plugin'
            key_field = 'themes_dir'
            try:
                ok, val = project.readEntry(key_group, key_field, default_dir)
                if ok and val:
                    default_dir = str(val)
                else:
                    try:
                        prev = project.customProperty(f"{key_group}:{key_field}")
                        if prev:
                            default_dir = str(prev)
                    except Exception:
                        pass
            except Exception:
                try:
                    prev = project.customProperty(f"{key_group}:{key_field}")
                    if prev:
                        default_dir = str(prev)
                except Exception:
                    pass
            # ユーザーにディレクトリを選ばせる（デフォルトは project/themes またはプロジェクト変数）
            d = QFileDialog.getExistingDirectory(self, self.tr("Select import directory"), default_dir)
            if not d:
                return
            # 選択をプロジェクト変数に保存（writeEntry を優先、ダメなら setCustomProperty）
            try:
                try:
                    project.writeEntry(key_group, key_field, d)
                except Exception:
                    try:
                        project.setCustomProperty(f"{key_group}:{key_field}", d)
                    except Exception:
                        pass
            except Exception:
                pass
            applied = self.import_themes_from_dir(d)
            if applied:
                QMessageBox.information(self, self.tr("Import Themes"), self.tr("Imported %n themes", None, len(applied)))
                try:
                    self.update_theme_list()
                except Exception:
                    pass
            else:
                QMessageBox.information(self, self.tr("Import Themes"), self.tr("No themes imported."))
        except Exception as e:
            QMessageBox.warning(self, self.tr("Import Themes"), str(e))

    # export_all_project_themes removed per user request


    def save_user_theme_dialog(self):
        """Save a minimal user-theme (JSON) representing visible layers and legend state."""
        try:
            from qgis.core import QgsProject
            project = QgsProject.instance()
            proj_file = project.fileName() or ""
            if not proj_file:
                QMessageBox.warning(self, self.tr("Save User Theme"), self.tr("Please save the QGIS project before saving user themes."))
                return
            proj_base = os.path.splitext(os.path.basename(proj_file))[0] or "project"
            default_dir = os.path.join(os.path.dirname(proj_file), "themes")
            os.makedirs(default_dir, exist_ok=True)
            default_name = f"{proj_base}__user_theme.usertheme.json"
            path, _ = QFileDialog.getSaveFileName(self, self.tr("Save User Theme"), os.path.join(default_dir, default_name), "User theme (*.usertheme.json);;JSON (*.json)")
            if not path:
                return
            try:
                from . import theme as theme_mod
                ok = theme_mod.save_user_theme(path)
            except Exception as ex:
                ok = False
            if ok:
                QMessageBox.information(self, self.tr("Save User Theme"), self.tr("Saved user theme."))
            else:
                QMessageBox.warning(self, self.tr("Save User Theme"), self.tr("Failed to save user theme."))
        except Exception as e:
            QMessageBox.warning(self, self.tr("Save User Theme"), str(e))


    def load_user_theme_dialog(self):
        """Load a user-theme JSON and apply it to the current project."""
        try:
            from qgis.core import QgsProject
            project = QgsProject.instance()
            proj_file = project.fileName() or ""
            if not proj_file:
                QMessageBox.warning(self, self.tr("Load User Theme"), self.tr("Please save the QGIS project before loading user themes."))
                return
            default_dir = os.path.join(os.path.dirname(proj_file), "themes")
            path, _ = QFileDialog.getOpenFileName(self, self.tr("Load User Theme"), default_dir, "User theme (*.usertheme.json);;JSON (*.json)")
            if not path:
                return
            try:
                from . import theme as theme_mod
                data = theme_mod.load_user_theme(path)
                if not data:
                    QMessageBox.warning(self, self.tr("Load User Theme"), self.tr("Failed to read user theme file."))
                    return
                applied = theme_mod.apply_user_theme(data)
            except Exception as ex:
                QMessageBox.warning(self, self.tr("Load User Theme"), str(ex))
                return
            QMessageBox.information(self, self.tr("Load User Theme"), self.tr("Applied theme to %n layers", None, len(applied)))
        except Exception as e:
            QMessageBox.warning(self, self.tr("Load User Theme"), str(e))

    def import_themes_from_dir(self, theme_dir: str):
        """ディレクトリ内の .xml ファイルを読み込んでプロジェクトのテーマコレクションへ追加する。追加したテーマ名のリストを返す"""
        # import_themes_from_dir removed per user request
