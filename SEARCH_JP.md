[English version (translation): `SEARCH.md`](./SEARCH.md)

# 検索機能（日本語）

## 概要

このドキュメントは `GEO Search System` の検索サブシステムに関する詳細です。地番検索・所有者検索・汎用属性検索の動作、検索ロジック、検索タブ設定やテーマ連携など、システム全体との統合観点を含めて説明します。

## サブシステム図と境界（開発者向け）

簡易図（テキスト）:

```
 UI (検索ダイアログ / SearchTab 設定)
            |
            v
 [Search Subsystem]
     - Search widgets (SearchTibanWidget, SearchOwnerWidget, SearchTextWidget)
     - Search features (SearchTibanFeature, SearchOwnerFeature, SearchTextFeature)
            |
            +--> Theme Management (selectTheme)  <--> Theme サブシステム
            |
            v
     Result Presentation (レイヤごとのタブ、ViewFields、ページング)
```

主要実装ファイル:

- `geo_search/widget/searchwidget.py` — SearchTibanWidget / SearchOwnerWidget / SearchTextWidget
- `geo_search/searchfeature.py` — SearchFeature 実装（結果取得・表示）
- `geo_search/plugin.py` — プラグイン起動・タブ設定の読み込みと注釈付与

連携ポイント（テーマ管理）:

- `selectTheme`（各 SearchTab の設定）: 検索実行前に適用するマップテーマ名を指定できます。
- テーマ適用はテーマサブシステムへ委譲され、追加表示モード（additive）により表示の合成を行えます（THEMES.md 参照）。

---

## 地番検索

- 地番（筆番号）で検索します。正規表現／完全一致／あいまい検索（近傍番号）をサポートします。
- 結果はレイヤごとにタブ化されたテーブルでページング表示されます。

## 汎用属性検索

- 任意の属性フィールドに対する検索です。表示するカラムやページングはタブごとの設定で制御できます。

## 所有者検索

- 所有者名で検索します。全角カナ→半角カナ変換や空白処理などの正規化を行い、複数フィールドの組合せ検索や前方一致／部分一致が設定により可能です。

## 検索ロジック（実装概要）

### 全文検索風
- 実装ファイル: `geo_search/widget/searchwidget.py`（ウィジェット） と `geo_search/searchfeature.py`（Feature 実装）。
- 動作: 入力された検索語を正規化し、設定された検索フィールド群に対して LIKE 相当の条件を組み立てて検索を実行します。

### 地番検索
- 実装ファイル: `geo_search/widget/searchwidget.py` / `geo_search/searchfeature.py`。
- 動作: 地番用の入力を受け取り、正規表現や近傍番号によるあいまい検索を行います。

### 所有者検索
- 実装ファイル: `geo_search/widget/searchwidget.py` / `geo_search/searchfeature.py`。
- 動作: 複数フィールドを選択して検索可能。カナ正規化や空白処理を行い、LIKE 条件で検索します。

### 表示レイヤ検索／全レイヤ検索
- `SearchTextFeature.show_features` は、タブタイトルが `表示レイヤ` または `全レイヤ` の場合、現在表示中のレイヤ／プロジェクト内全レイヤを横断して検索し、結果をレイヤごとにタブ表示します。

### 補助機能
- サジェスト（補完）機能: `unique_values` を用いて `QCompleter` を生成します。
- マップテーマ適用: 各タブの `selectTheme` に指定されたテーマを検索時に適用可能です。

---

## UI設定画面

- 各タブごとの設定（対象レイヤ、検索フィールド、表示フィールド、マップテーマ）を GUI で編集でき、設定はプロジェクトファイルに保存されます。

クイックスタート（日本語）:

- インストール: `geo_search` フォルダを QGIS のユーザープラグインディレクトリへ配置するか、ZIP から導入してください。
- 起動: QGIS でプラグインを有効化し、ツールバーの起動ボタンから検索ダイアログを開きます。
- 検索: タブを選択または設定し、地番・所有者名・属性などを入力して `検索` を押します。
- 結果: レイヤごとのタブに結果が表示され、行をクリックすると地図上で選択・移動します。

詳細は README を参照してください。

---

## 設定項目

設定例や `setting.json.sample` のサンプルはプラグイン同梱のファイルを参照してください。以下は主要項目の要点です。

```json
{
  "SearchTabs": [
    {
      "Title": "サンプル",
      "Layer": { "LayerType": "Database", "DataType": "postgres", "Host": "Host名", "Port": "5432", "Database": "データベース名", "User": "ユーザー名", "Password": "パスワード", "Schema": "public", "Table": "kihonp", "Key": "ogc_fid", "Geometry": "wkb_geometry", "FormatSQL": "format.sql" },
      "TibanField": "地番属性",
      "AzaTable": { "DataType": "postgres", "Host": "...", "Port": "5433", "Database": "...", "User": "...", "Password": "...", "Schema": "public", "Table": "コード表_字", "Columns": [ { "Name": "表示する属性名", "View": "表示用名称" } ] },
      "SearchFields": [ { "FieldType": "Text", "ViewName": "検索ダイアログのラベル表示名", "Field": "検索に使用する属性", "KanaHankaku": true } ],
      "SampleFields": ["一時テーブルに表示する属性"],
      "ViewFields": ["結果に表示する属性"],
      "Message": "？ボタンで表示されるメッセージ",
      "SampleTableLimit": 100,
      "selectTheme": "テーマ名"
    }
  ]
}
```

### 設定（要点）
- `Title`: タブ表示名
- `Layer`: レイヤ読み込み情報（`LayerType` に `Name`/`File`/`Database` を指定）
- `SearchFields` / `SearchField`: 検索対象フィールドの指定
- `ViewFields`: 結果表示フィールド（空配列で全フィールド表示）
- `selectTheme`: 検索時に適用するマップテーマ名（`"検索前"` を指定するとプラグイン起動時に保存された表示状態が適用されます）

### 表示フィールの振る舞い
- 未指定または空配列: レイヤの全フィールドを表示
- 存在するフィールドのみ指定: 指定されたフィールドのみ表示
- 存在しないフィールドが指定されていると空表になる（QGIS メッセージに警告）

### 選択後の地図移動
- ズーム to 選択（デフォルト）: 選択地物に合わせて自動ズーム
- 中心パン（ズーム維持）: 縮尺を保ったままパン
- 固定スケール表示: 指定スケールでセンタリング
- アニメーションパン: アニメーションで移動してフィット
- 選択のみ: 表示変更なし

---

## 設定ソース（読み込み元）と注釈

- 読み込み順（結合順）は次のとおりです: `setting.json` (プラグイン内) → プロジェクト変数 `GEO-search-plugin` (inline JSON またはファイル参照) → 外部 `geo_search_json`（環境変数またはプロジェクト変数で指定されたファイル）。
- 各タブ設定には実行時に以下の注釈が付与されます:
  - `_source`: 読み込み元トークン（例: `setting.json`, `project variable`, `geo_search_json`）
  - `_source_index`: そのソース内での 0-based インデックス（読み込み順に基づく）

- これらの注釈は、タブの編集・削除を行う際の対象特定に利用されます。削除処理はまず `_source_index` による直接指定を試み、範囲外や不一致の場合は `Title` によるフォールバック検索を行います。
- ファイル更新はバックアップを取りつつ原子的に行われ、成功後にプラグインが UI を再構築して注釈（`_source_index` 等）を再計算します。

例: UI 上のソース表示は `[{short}]` から `[{short} #{index}]` の形式になり、`setting.json` の 3 番目の要素なら `[setting.json #2]` のように表示されます。

---

## 設定ファイル説明（主要項目）

- `Title`: タブに表示されるタイトル
- `group`: タブをまとめるグループ名
- `Layer`: 読み込むレイヤ情報
- `SearchField` / `SearchFields`: 検索対象の属性情報
- `ViewFields`: 検索結果で表示する属性（空配列で全フィールド表示）
- `Message`: ヘルプ表示用のテキスト
- `TibanField`: 地番属性名
- `AzaTable`: 地番検索用の字コード設定
- `angle`: 検索時に適用する回転角度（度）
- `scale`: 検索時に適用する縮尺（分母）
- `selectTheme`: 検索時に適用する QGIS マップテーマ名

### マップテーマ機能（概要）

1. プラグイン起動時に現在の表示状態を `検索前` という名前で自動保存します。
2. ツールバーにテーマ選択ドロップダウンを配置し、任意のテーマを即時適用できます。
3. 各タブの `selectTheme` を指定すると、検索時にそのテーマが適用されます（`検索前` を指定すると起動時の保存表示に戻せます）。
4. 追加表示モード（Additive display mode）: ON の場合、テーマ適用時に現在表示中のレイヤを残したままテーマの可視レイヤを上に追加表示します。OFF の場合はテーマで表示が置換されます。

---

## 課題と注意点

- 外部ファイルが別プロセスで同時更新されると、UI の表示とファイル中のインデックスが一時的にずれる可能性があります。UI 再構築で整合されます。
- `ViewFields` に存在しないフィールド名を指定すると空の表になります。

---

## 参考ファイル

- `geo_search/widget/searchwidget.py`
- `geo_search/searchfeature.py`
- `geo_search/plugin.py`
- `THEMES.md`

``` 
```
