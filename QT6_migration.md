GEO-search-plugin: Qt6 移行準備メモ

要約
- リポジトリ内を検索したところ、`PyQt4` や Qt4 の直接参照は見つかりませんでした。
- 既に多くのファイルが `qgis.PyQt` を経由して Qt を参照しており、これは QGIS の shim により PyQt5/PyQt6/PySide2/PySide6 を吸収できます。

行った変更
- `GEO_search/qt_compat.py` を追加しました。これは将来的な Qt6 特有の差分を吸収するための最小限の互換層です。

今後の推奨手順 (安全に移行するため)
1. 環境準備
   - QGIS が Qt6 を搭載するバージョン (およびターゲットの QGIS バージョン) を確認してください。QGIS 側の shim が Qt6 を提供していなければ、プラグイン側だけで完全互換にすることはできません。

2. リソースファイルの更新
   - `resources.py` は PyQt5 用の rcc で生成されている可能性があります。Qt6 環境で問題が出る場合は、Qt6 用の rcc (pyrcc6) で再生成を検討してください。例:

```powershell
# Qt6 用に rcc を再生成する例 (必要に応じて実行)
# pyrcc6 は Qt のインストールや Python バインディングに依存します
pyrcc6 -o GEO_search\resources.py GEO_search\resources.qrc
```

3. 列挙型と API の差分対応
   - Qt6 では多くの列挙型がクラス化される（例: Qt.AlignLeft -> Qt.AlignmentFlag.AlignLeft）。
   - コード中で列挙型のフルパスを使っている箇所をチェックし、`qt_compat.py` に必要な変換ユーティリティを追加して吸収します。

4. 文字列/バイト列の扱い、API の戻り値
   - Qt6 で返る型が変わる API（例えば一部の toString 相当や QVariant の扱い）に注意し、テストを用意してください。

5. テストと手動検証
   - QGIS (Qt5) 上で現在の動作を回帰テスト。
   - QGIS (Qt6) 上で同様に動作を確認。
   - UI の表示、トランスレーション、リソース読み込み、シグナル/スロットの挙動を重点的に確認します。

6. 段階的な置換
   - まずは内部開発用に `from GEO_search.qt_compat import QtWidgets, QtCore` をファイル頭に追加して段階的に差し替えを進めると安全です。

該当ファイル一覧 (qgis.PyQt を参照している主なファイル)
- GEO_search\widget\searchwidget.py
- GEO_search\utils.py
- GEO_search\searchfeature.py
- GEO_search\searchdialog.py
- GEO_search\resultdialog.py
- GEO_search\resources.py
- GEO_search\plugin.py
- GEO_search\autodialog.py

その他のメモ
- 現時点で Qt4 は見つかりませんでした。削除は不要です。
- こちらの作業は最小限の準備です。実際の Qt6 対応では個別の API 差分に応じた細かい修正が必要になります。
