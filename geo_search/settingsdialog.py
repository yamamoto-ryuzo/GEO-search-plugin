# -*- coding: utf-8 -*-
"""
Simple settings dialog for GEO-search-plugin.
日本語コメント: 設定ダイアログの実装ファイル。必要な設定ウィジェットをここに追加してください。
"""
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QLineEdit
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

        # geo_search_json ファイル指定用コントロール
        geo_ctrl = QHBoxLayout()
        geo_label = QLabel(self.tr("Settings file (geo_search_json):"), self)
        self.geo_line = QLineEdit(self)
        # 現在値を取得して表示（環境変数優先）
        try:
            import os
            from qgis.core import QgsProject, QgsExpressionContextUtils
            env_val = os.environ.get('geo_search_json')
        except Exception:
            env_val = None
        try:
            if env_val:
                self.geo_line.setText(str(env_val))
            else:
                try:
                    proj = QgsProject.instance()
                    try:
                        pv = QgsExpressionContextUtils.projectScope(proj).variable('geo_search_json')
                    except Exception:
                        pv = None
                    if pv:
                        self.geo_line.setText(str(pv))
                except Exception:
                    pass
        except Exception:
            pass
        browse_geo_btn = QPushButton(self.tr("Browse..."), self)
        apply_geo_btn = QPushButton(self.tr("Apply"), self)
        geo_ctrl.addWidget(geo_label)
        geo_ctrl.addWidget(self.geo_line)
        geo_ctrl.addWidget(browse_geo_btn)
        geo_ctrl.addWidget(apply_geo_btn)
        layout.addLayout(geo_ctrl)

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
        # geo_search_json 用のハンドラ
        try:
            browse_geo_btn.clicked.connect(self._browse_geo_search_json)
        except Exception:
            pass
        try:
            apply_geo_btn.clicked.connect(self._apply_geo_search_json)
        except Exception:
            pass

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


    def _browse_geo_search_json(self):
        """ファイル選択ダイアログで geo_search_json のファイルを選択する。"""
        try:
            start_dir = ""
            # 現在のテキストから有効なファイルを解決する（プロジェクト相対も考慮）
            cur = ""
            try:
                cur = str(self.geo_line.text()).strip()
            except Exception:
                cur = ""

            resolved = None
            if cur:
                try:
                    # 絶対パスで存在するか
                    if os.path.isabs(cur) and os.path.exists(cur):
                        resolved = os.path.abspath(cur)
                    else:
                        # プロジェクトのフォルダを基準に解決してみる
                        try:
                            from qgis.core import QgsProject
                            proj = QgsProject.instance()
                            proj_file = proj.fileName() or ""
                            proj_dir = os.path.dirname(proj_file) if proj_file else ""
                        except Exception:
                            proj_dir = ""
                        if proj_dir:
                            cand = os.path.join(proj_dir, cur)
                            if os.path.exists(cand):
                                resolved = os.path.abspath(cand)
                        # それでも見つからなければカレントからの相対も試す
                        if not resolved and os.path.exists(cur):
                            resolved = os.path.abspath(cur)
                except Exception:
                    resolved = None

            if resolved:
                start_dir = os.path.dirname(resolved)
            else:
                # 指定ファイルがない場合はプロジェクトフォルダを初期ディレクトリにする
                try:
                    from qgis.core import QgsProject
                    proj = QgsProject.instance()
                    proj_file = proj.fileName() or ""
                    if proj_file:
                        start_dir = os.path.dirname(proj_file)
                except Exception:
                    # フォールバック
                    try:
                        start_dir = os.path.dirname(__file__)
                    except Exception:
                        start_dir = ""
        except Exception:
            try:
                start_dir = os.path.dirname(__file__)
            except Exception:
                start_dir = ""

        try:
            path, _ = QFileDialog.getOpenFileName(self, self.tr("Select settings file"), start_dir, "JSON files (*.json);;All files (*)")
        except Exception:
            path = None
        if path:
            try:
                self.geo_line.setText(path)
            except Exception:
                pass

    def _apply_geo_search_json(self):
        """選択されたパスをプロジェクト変数 `geo_search_json` として保存し、ランタイム環境変数にも設定する。"""
        try:
            path = str(self.geo_line.text()).strip()
        except Exception:
            path = ""
        if not path:
            QMessageBox.warning(self, self.tr("geo_search_json"), self.tr("No file selected."))
            return
        try:
            from qgis.core import QgsProject, QgsExpressionContextUtils, QgsMessageLog
            proj = QgsProject.instance()
            try:
                # プロジェクトが保存されている場合はプロジェクトディレクトリ基準の相対パスに変換して保存する
                try:
                    proj_file = proj.fileName() or ""
                    proj_dir = os.path.dirname(proj_file) if proj_file else ""
                except Exception:
                    proj_dir = ""

                save_val = path
                try:
                    if proj_dir:
                        abs_path = os.path.abspath(path)
                        abs_proj = os.path.abspath(proj_dir)
                        try:
                            # path がプロジェクトディレクトリ以下にある場合は相対パスで保存
                            if os.path.commonpath([abs_proj, abs_path]) == abs_proj:
                                rel = os.path.relpath(abs_path, abs_proj)
                                save_val = rel
                        except Exception:
                            # commonpath may raise on different drives on Windows; fall back to absolute
                            save_val = path
                except Exception:
                    save_val = path

                QgsExpressionContextUtils.setProjectVariable(proj, 'geo_search_json', save_val)
                try:
                    QgsMessageLog.logMessage(f"Set project variable 'geo_search_json' to: {save_val}", 'GEO-search-plugin', 0)
                except Exception:
                    pass
            except Exception as e:
                try:
                    QgsMessageLog.logMessage(f"Failed to set project variable 'geo_search_json': {e}", 'GEO-search-plugin', 2)
                except Exception:
                    pass
        except Exception:
            # qgis.core が使えない環境でもランタイム環境変数は設定する
            pass
        # ランタイム環境変数としても設定（永続化はしない）
        try:
            import os
            os.environ['geo_search_json'] = path
        except Exception:
            pass
        QMessageBox.information(self, self.tr("geo_search_json"), self.tr("Saved geo_search_json to project variables (and runtime env)."))

    def import_themes_from_dir(self, theme_dir: str):
        """ディレクトリ内の .xml ファイルを読み込んでプロジェクトのテーマコレクションへ追加する。追加したテーマ名のリストを返す"""
        # import_themes_from_dir removed per user request
