# 検索機能 / Search Features

## 目次 / Table of Contents

- [Overview](#overview)
- [Lot-number search / 地番検索](#lot-number-search--地番検索)
- [General attribute search / 汎用的な検索](#general-attribute-search--汎用的な検索)
- [Owner-name search / 所有者検索](#owner-name-search--所有者検索)
- [検索ロジック（実装概要）](#検索ロジック実装概要)
- [UI settings / UI設定画面 (project-saved)](#ui-settings--uisettings画面-project-saved)
- [設定項目 / Configuration](#設定項目--configuration)
- [SearchTab 設定（要点）](#searchtab-設定要点)
- [ViewFields の振る舞い](#viewfieldsの振る舞い)
- [パンモード（選択後の地図移動）](#パンモード選択後の地図移動)

## Overview — Search Subsystem

This document describes the Search Subsystem of the GEO Search System. It contains detailed descriptions of core search features (lot-number, owner-name and general attribute searches), the high-level search logic, and configuration points used to integrate search into the larger system (per-tab settings, theme selection, and result presentation).

日本語: 本ドキュメントは `GEO Search System` の検索サブシステムに関する詳細です。地番検索・所有者検索・汎用属性検索の動作、検索ロジック、検索タブ設定やテーマ連携など、システム全体との統合観点を含めて説明します。

## サブシステム図と境界（開発者向け）

簡易図（テキスト）:

```
 UI (Search dialog / SearchTab settings)
			|
			v
 [Search Subsystem]
	 - Search widgets (SearchTibanWidget, SearchOwnerWidget, SearchTextWidget)
	 - Search features (SearchTibanFeature, SearchOwnerFeature, SearchTextFeature)
			|
			+--> Theme Management (selectTheme)  <--> Theme Subsystem
			|
			v
	Result Presentation (per-layer tabs, ViewFields, paging)
```

境界関数／主要参照箇所（実装ファイル）:

- `geo_search/widget/searchwidget.py`
	- `SearchTibanWidget`, `SearchOwnerWidget`, `SearchTextWidget` (UI → Feature 呼び出し)
- `geo_search/searchfeature.py`
	- `SearchTextFeature.show_features()` — 結果取得 → 表示（タブ生成）境界
	- `SearchTibanFeature`, `SearchOwnerFeature` — 検索ロジックのコア
	- `normalize_search_value()` 等の正規化ユーティリティ
- `geo_search/plugin.py`
	- UI 起動/タブ設定保存の接点（Search dialog の登録箇所）

連携ポイント（テーマ管理）:

- `selectTheme`（SearchTab 設定）: 検索前に `SearchFeature` が `selectTheme` を読み取り、テーマ適用を依頼します。
- テーマ適用はテーマサブシステム（`THEMES.md` に記載の関数）へ委譲され、追加表示モード（additive）を通じて結果の表示が構成されます。

このセクションは開発者がどこを見ればシステムの境界が分かるかを示すことを目的としています。詳細な実装は下のセクションと参照ファイルを確認してください。

---

### Lot-number search / 地番検索

- English: Search cadastral lot ("tiban") by lot number. Supports exact, regex and fuzzy/neighbor searches, and shows results per layer in tabbed tables with pagination.
- 日本語: 地番（筆番号）で検索します。正規表現／完全一致／あいまい検索をサポートし、結果はレイヤごとにタブ化されたテーブルでページング表示されます。

![image](https://user-images.githubusercontent.com/86514652/183770100-a385fad3-bc25-47f8-919c-659554c1f7e3.png)

### General attribute search / 汎用的な検索

- English: Perform attribute-based searches on arbitrary fields. Displayed columns and paging behavior can be configured per-tab.
- 日本語: 任意の属性フィールドに対する検索です。表示するカラムやページングはタブごとの設定で制御できます。

![image](https://github.com/yamamoto-ryuzo/GEO-search-plugin/assets/86514652/4483e588-2c1d-4133-9cfe-fc33bb9a5068)

### Owner-name search / 所有者検索

- English: Search by owner name with normalization (kana conversion, whitespace handling). Multiple fields can be selected; supports prefix and substring matching depending on configuration.
- 日本語: 所有者名で検索します。全角カナ→半角化や空白処理など正規化を行い、複数フィールドの組合せ検索や前方一致／部分一致が設定により可能です。

![image](https://github.com/yamamoto-ryuzo/GEO-search-plugin/assets/86514652/4483e588-2c1d-4133-9cfe-fc33bb9a5068)

## 検索ロジック（実装概要）

### 通常検索（全文検索風） SearchTextFeature
- 実装ファイル: `geo_search/widget/searchwidget.py` (`SearchTextWidget`) と `geo_search/searchfeature.py` (`SearchTextFeature`).
- 動作: 検索ボックスに入力された最初の非空値を取得し、設定された検索フィールド（`SearchField` または `SearchFields`）に対して SQL の LIKE 相当の条件を組み立てます。複数フィールドは OR/AND（設定に依存）で結合され、QGIS の `QgsExpression` を用いて `QgsFeatureRequest` に渡して検索します。
- 正規化: `SearchFeature.normalize_search_value` により全角英数字を半角に変換します。

### 地番検索（地籍検索） SearchTibanFeature
- 実装ファイル: `geo_search/widget/searchwidget.py` (`SearchTibanWidget`) と `geo_search/searchfeature.py` (`SearchTibanFeature`).
- 動作: 地番用の入力を受け取り、地番属性（`TibanField`）に対する正規表現マッチや、個別フィールドに対する完全一致／あいまい（近傍番号）検索をサポートします。あいまい検索では数値幅（FUZZY）を用いた幅のあるヒットを生成します。地番フィールドは正規表現（`regexp_match`）でマッチングされます。
- 補助機能: 字コード（`AzaTable`）を読み込んで候補をテーブル表示し、選択で入力欄にセットします。

### 所有者検索 SearchOwnerFeature
- 実装ファイル: `geo_search/widget/searchwidget.py` (`SearchOwnerWidget`) と `geo_search/searchfeature.py` (`SearchOwnerFeature`).
- 動作: 複数フィールドをチェックボタンで選択して検索できます。全角カナ→半角カナや濁音／拗音の変換処理を行い、`replace(... ) LIKE '{value}'` のような式で空白除去やカナ正規化を行った比較を実行します。前方一致／部分一致の切替もサポートします。

### 表示レイヤ検索／全レイヤ検索
- `SearchTextFeature.show_features` ではタブタイトルが `表示レイヤ` または `全レイヤ` の場合、現在表示されているレイヤ／プロジェクト内全レイヤを横断して検索を行い、結果をレイヤごとのタブで表示します。

### 補助機能
- サジェスト（補完）機能: `unique_values` を使い `QCompleter` を生成して補完候補を表示します（`Suggest` フラグで有効化）。
- マップテーマ適用: 検索実行時に `selectTheme` に設定されたマップテーマを適用します（`検索前` という自動保存テーマも利用可能）。

---

詳細な使い方や設定例、診断手順については README に簡潔な案内を残しています。実際のコード読み替えやデバッグには上記実装ファイルを参照してください。

## UI settings / UI設定画面 (project-saved)

- English: Configure per-tab search settings (layers, search fields, display fields, and optional map themes). These settings are saved to the QGIS project file so project-specific search configurations can be reused.
- 日本語: 各検索タブごとの設定（対象レイヤ、検索フィールド、表示フィールド、マップテーマなど）をGUIで編集でき、設定はプロジェクトファイルに保存されます。

詳細なマップテーマの仕組み・設定方法は `THEMES.md` を参照してください。

<img width="686" height="740" alt="image" src="https://github.com/user-attachments/assets/27cad15f-890f-4bfc-9c61-3660531e7c32" />

### クイックスタート（日本語）

- インストール: `geo_search` フォルダを QGIS のユーザープラグインディレクトリにコピーするか、ZIP を `プラグインの管理とインストール` から導入してください。
- 起動: QGIS でプラグインを有効化し、ツールバーの起動ボタンから検索ダイアログを開きます。
- 検索: タブを選択または設定し、地番・所有者名・属性などを入力して `検索` を押します。
- 結果: レイヤごとのタブに結果が表示され、行をクリックすると地図上で選択・移動します。列幅が狭い場合はテーブルヘッダーから自動調整してください。
- トラブルシュート: 表示がおかしい場合はプラグインを無効化→上書き→有効化、または QGIS を再起動してから再実行してください。

最終的には https://github.com/NationalSecurityAgency/qgis-searchlayers-plugin と統合したい

## 設定項目 / Configuration

README から移行した設定例、`setting.json` のサンプルスニペット、`SearchTab` 設定の説明、`ViewFields` の動作、パンモードなどの詳細はこのセクションに含まれます。

以下は README から移行した設定例（そのままの形式）です。プロジェクト変数や `setting.json` に設定する場合の参考にしてください。

```json
{
	"SearchTabs": [
		{
			"Title": "サンプル",
			"Layer": {
				"LayerType": "Database",
				"DataType": "postgres",
				"Host": "Host名",
				"Port": "5432",
				"Database": "データベース名",
				"User": "ユーザー名",
				"Password": "パスワード",
				"Schema": "public",
				"Table": "kihonp",
				"Key": "ogc_fid",
				"Geometry": "wkb_geometry",
				"FormatSQL": "format.sql"
			},
			"TibanField": "地番属性",
			"AzaTable": {
				"DataType": "postgres",
				"Host": "あなたの情報",
				"Port": "5433",
				"Database": "あなたの情報",
				"User": "あなたの情報",
				"Password": "あなたの情報",
				"Schema": "public",
				"Table": "コード表_字",
				"Columns": [ { "Name": "表示する属性名", "View": "表示用名称" } ]
			},
			"SearchFields": [
				{ "FieldType": "Text", "ViewName": "検索ダイアログのラベル表示名", "Field": "検索に使用する属性", "KanaHankaku": true },
				{ "FieldType": "Text", "ViewName": "検索ダイアログのラベル表示名", "Field": "検索に使用する属性" }
			],
			"SampleFields": ["一時テーブルに表示する属性"],
			"ViewFields": ["結果に表示する属性"],
			"Message": "？ボタンで表示されるメッセージ",
			"SampleTableLimit": 100,
			"selectTheme": "テーマ名"
		}
	]
}
```

### SearchTab 設定（要点）
- `Title`: タブ表示名
- `Layer`: レイヤ読み込み情報（`LayerType` に `Name`/`File`/`Database` を指定）
- `SearchFields` / `SearchField`: 検索対象フィールドの指定
- `ViewFields`: 結果表示フィールド（空配列で全フィールド表示）
- `selectTheme`: 検索時に適用するマップテーマ名（`"検索前"` を指定するとプラグイン起動時に保存された表示状態が適用されます）

### ViewFields（表示フィールド）の振る舞い
- 未指定または空配列: レイヤの全フィールドを表示
- 存在するフィールドのみ指定: 指定されたフィールドのみ表示
- 存在しないフィールドが指定されていると空表になる（QGIS メッセージに警告）

### パンモード（選択後の地図移動）
- ズーム to 選択（デフォルト）: 選択地物に合わせて自動ズーム
- 中心パン（ズーム維持）: 縮尺を保ったままパン
- 固定スケール表示: 指定スケールでセンタリング
- アニメーションパン: アニメーションで移動してフィット
- 選択のみ: 表示変更なし


## 設定項目

```json
詳しいサンプルは，プラグインに添付されている「setting.json.sample」を参照ください


### タブ設定編集ダイアログ（ウィザード）について

本プラグインでは、各検索タブごとの設定（検索フィールド・表示フィールド・マップテーマ等）をGUIで編集できる「タブ設定編集ダイアログ（ウィザード）」を搭載しています。

**使い方例：**
- 検索ダイアログの「タブ設定編集」ボタンを押すと、現在のタブの設定内容（SearchField, ViewFields, selectTheme など）をGUIで編集できます。
- 「検索フィールド選択ウィザード（複数選択可 - OR検索）」ボタンで、対象フィールドを選択できます。
- 「表示フィールド選択ウィザード」ボタンで、検索結果に表示する属性を選択できます。
- 「selectTheme」欄で、QGISプロジェクト内の任意のマップテーマを選択できます：
	- 空欄の場合はテーマ切替なし
	- 「検索前」を選択すると、プラグイン起動時に自動保存された表示状態が適用されます
	- その他のテーマ名を指定すると、検索時に指定したテーマが適用されます
- 編集内容はプロジェクト変数「GEO-search-plugin」または `setting.json` に反映されます。

> 詳細な設定内容やフィールドの意味は下記「設定ファイル説明」も参照してください。
{
	"SearchTabs": [
 
ここ以下をプロジェクト変数「GEO-search-plugin」もしくはプラグイン内の設定ファイル「setting.json」に設定してください。
　・プロジェクト変数「GEO-search-plugin」　　　プロジェクトごとに変更したい検索  
　・プラグイン内の設定ファイル「setting.json」　プラグイン全体を通して利用する検索  
		{
			"Title": "サンプル",
			"Layer": {
				"LayerType": "Database", // レイヤの読み込みタイプ
				"DataType": "DBタイプ(現在はpostgresのみ)", // postgres
				"Host": "Host名", // localhost
				"Port": "Port番号", // 5432
				"Database": "データベース名", // sample_db
				"User": "ユーザー名", // postgres
				"Password": "パスワード", // postgres
				"Schema": "スキーマ", // public
				"Table": "テーブル名", // kihonp
				"Key": "主キー", // ogc_fid
				"Geometry": "座標属性", // wkb_geometry
				"FormatSQL": "format.sql" // 実行するSQL(soja_searchフォルダからの相対パス)
			},
			"TibanField": "地番属性", // 地番とする属性
			"AzaTable": {
				// 字コード表を表示するための情報
				"DataType": "postgres",
				"Host": "あなたの情報",
				"Port": "5433",
				"Database": "あなたの情報",
				"User": "あなたの情報",
				"Password": "あなたの情報",
				"Schema": "public",
				"Table": "コード表_字",
				"Columns": [
					// 表示する属性
					{
						"Name": "表示する属性名",
						"View": "表示用名称"
					}
				]
			},
			"SearchFields": [
				{
					"FieldType": "Text",
					"ViewName": "検索ダイアログのラベル表示名",
					"Field": "検索に使用する属性",
					"KanaHankaku": true // 全角カナの半角変換(所有者検索のみ設定)
				},
				{
					"FieldType": "Text",
					"ViewName": "検索ダイアログのラベル表示名",
					"Field": "検索に使用する属性"
				}
			],
	"SampleFields": ["一時テーブルに表示する属性"],
	"ViewFields": ["結果に表示する属性"], // 空配列なら全フィールド、存在しないフィールドなら何も表示しない
	"Message": "？ボタンで表示されるメッセージ",
	"SampleTableLimit": 100, // 一時テーブルに表示で表示される件数
	"selectTheme": "テーマ名" // 検索時に適用するQGISマップテーマ名（省略可）
		},
		{
			"Title": "地籍検索(地番)",
			"Layer": {
				"LayerType": "Name",
				"Name": "地籍",
				"Encoding": "cp932"
			},
			"SearchField": {
				"FieldType": "Text",
				"ViewName": "住所",
				"Field": "住所"
			},
			"ViewFields": [] // 空配列なので全フィールドを表示
		}
ここまでを設定してください。
   
	]
}
```

## 設定項目(プロジェクト変数「GEO-search-plugin」の設定例)  
		{
			"group": "ﾌﾟﾛｼﾞｪｸﾄ検索",
			"Title": "市区町村",
			"Layer": {
				"LayerType": "Name",
				"Name": "行政区域",
				"Encoding": "cp932"
			},
			"SearchField": {
				"FieldType": "Text",
				"ViewName": "市区町村名",
				"Field": "市区町村名"
			},
			"ViewFields": ["N03_001","N03_004","N03_007"], // 指定された3つのフィールドのみ表示
			"selectTheme": "行政区域テーマ" // 検索時に適用するQGISマップテーマ名（省略可）
		}

※ `selectTheme` を指定すると、検索時に該当のQGISマップテーマが自動で適用されます。省略した場合はテーマ切替は行われません。

## 課題

### 全体

- 元々検索・結果表示は DB 参照が基本のような記述が存在する
	- ~~表示項目のカスタマイズ~~ → **解決済み**: `ViewFields`で表示フィールドをカスタマイズ可能
- 一時テーブルにサンプルテーブルという表示

### 地番検索

- 結果テーブルで確認される属性[m2]と[筆状態]が不明

### 所有者検索

- 氏名の間にあるスペースの処遇

## 設定ファイル説明
### SearchTab
| Property | Description | Type |
| --- | --- | --- |
| Title | タブに表示されるタイトル。タイトルが地番検索・所有者検索の場合特殊検索になる。 | str |
| group | タブをまとめるタブグループ、グループ名となり同名グループでまとまる。 | str |
| Layer | 読み込むレイヤ情報 | dict |
| SearchField | 検索対象の属性情報 | dict |
| SearchFields | 検索対象の属性情報 | list[dict] |
| ViewFields | 検索結果で表示するレイヤ属性。空配列または未指定時は全フィールド表示。指定されたフィールドが存在しない場合は何も表示しない。（フィールド名：別名はNG） | list[str] |
| Message | 左下のヘルプボタンで表示されるテキスト | str |
| TibanField | 地番の属性名 | str |
| AzaTable | 地番検索用: 字コード設定 | dict |
| angle | タブごとに適用するマップ回転角度（度）。-360〜360 の数値を指定。未指定の場合は回転を変更しません。回転はパン／ズーム処理の後に適用されます。 | number (float) |
| scale | 検索時に適用する地図の縮尺（分母）。例: 5000。未指定の場合は縮尺を変更しません。固定スケール表示モードと組み合わせて使用できます。 | number (float) |
| selectTheme | 検索時に適用するQGISマップテーマ名。指定しない場合はテーマ切替なし | str (optional) |

### マップテーマ機能について

本プラグインでは、以下のマップテーマ関連機能を提供しています：

1. **プラグイン起動時のテーマ自動保存:**
	 - プラグイン起動時に現在の表示状態が「検索前」という名前でテーマとして自動保存されます
	 - これにより検索後でも簡単に元の表示状態に戻ることができます

2. **テーマドロップダウン:**
	 - ツールバーの起動ボタンの右側にテーマ選択用のドロップダウンリストが追加されました
	 - このドロップダウンから任意のマップテーマを選択して即時に適用できます
	 - 「テーマ選択」の項目を選んでも何も実行されません（デフォルト表示用）
	 - 同じテーマを再度選択した場合でも、テーマが再適用されます
	 - プロジェクトでテーマが追加・変更されると自動的にドロップダウンリストも更新されます

3. **検索時のテーマ適用機能:**
	 - 各検索タブごとに「selectTheme」パラメータで適用するテーマを指定できます
	 - 「検索前」を指定すると、起動時に保存された表示状態が適用されます
	 - その他のテーマ名を指定すると、該当するテーマが適用されます
	 - テーマ名を指定しない場合は表示状態は変更されません

4. **タブ設定編集ダイアログでのテーマ選択:**
	 - タブ設定編集ダイアログの「selectTheme」欄でテーマを選択できます
	 - 現在のプロジェクトに存在するマップテーマから選択できます

	5. **追加表示モード (Additive display mode):**
		- ツールバーにアイコンのみのトグルが追加されます。プラグインは `geo_search/icon/theme-additive.png` (ON) と `geo_search/icon/theme-switch.PNG` (OFF) を優先して使用します。これらが存在しない場合は既存の `qgis-icon.png` にフォールバックします。
		- ON の場合: テーマを適用しても現在表示中のレイヤは消えず、テーマで可視とされるレイヤが上に追加表示されます。内部的には「適用前に可視だったレイヤ」と「テーマ適用後に可視なレイヤ」の和集合が最終表示になります。
		- OFF (デフォルト) の場合: 従来通りテーマ適用により表示がテーマの設定で置き換わります。
		- 確認手順: QGIS でプラグインを再起動→検索ダイアログを開く→ツールバーの追加表示トグルで ON/OFF を切替→テーマを選択して検索を実行し、レイヤの可視状態が期待どおり（追加表示または置換）になることを確認してください。

**注記:**
「タブ設定編集ダイアログ（ウィザード）」を使うことで、これらの設定項目をGUI上で直感的に編集できます。

### 特殊検索
#### 地番検索

Title で `地番検索`として場合に表示される検索。

地番検索用の設定
| Property | Description | Type |
| --- | --- | --- |
| TibanField | 地番の属性名 | str |
| AzaTable | 地番検索用: 字コード設定 | dict |

**AzaTable**
字コード表を表示するための情報

| Property | Description | Type |
| --- | --- | --- |
| DataType | 接続するデータベース | Literal["postgres"] |
| Host | データベースのアドレス | str |
| Port | データベースのポート | str |
| Database | データベース名 | str |
| User | データベースのユーザー名 | str |
| Password | データベースのパスワード | str |
| Schema | 読み込むスキーマ名 | str |
| Table | テーブル名 | str |
| Columns | 字コード表 | dict |

**Columns**
字コード表の表示情報

| Property | Description | Type |
| --- | --- | --- |
| Name | テーブルのカラム名 | str |
| View | 表示するカラム名 | str |


#### 所有者検索

Title で `所有者検索`として場合に表示される検索。

### Layer: レイヤ読み込み設定

検索タブでは、使用するレイヤにより設定方法が違う

読み込めるタイプ

* レイヤ
* ファイル
* データベース

#### レイヤ

QGISで読み込んでいるレイヤを検索対象とする。

| Property | Description | Type |
| --- | --- | --- |
| LayerType | 読み込むレイヤの種類を選択 | Literal["Name", "File", "Database"] |
| Name | QGIS上のレイヤ名 | str |

#### ファイル

地図ファイルを検索対象とする。

| Property | Description | Type |
| --- | --- | --- |
| LayerType | 読み込むレイヤの種類を選択 | Literal["Name", "File", "Database"] |
| Path | 読み込むファイル名 | FilePath |
| Encoding | 読み込むファイルのエンコーディング | str |

#### データベース

データベースのテーブルを検索対象とする

| Property | Description | Type |
| --- | --- | --- |
| LayerType | 読み込むレイヤの種類を選択 | Literal["Name", "File", "Database"] |
| DataType | 接続するデータベース | Literal["postgres"] |
| Host | データベースのアドレス | str |
| Port | データベースのポート | str |
| Database | データベース名 | str |
| User | データベースのユーザー名 | str |
| Password | データベースのユーザー名 | str |
| Schema | 読み込むスキーマ名 | str |
| Table | テーブル名 | str |
| Key | テーブルのユニークキー | str |
| Geometry | テーブルのGeometryカラム名 | str |
| FormatSQL | Viewを作成するSQLなどを指定する | FilePath |

### SearchFieldとSearchFieldsの使い分け

検索に使用するレイヤの属性情報は、`SearchField`（単一）または`SearchFields`（複数）で設定できます。

#### SearchField

単一の検索フィールド設定です。一つの検索ボックスに対して、複数のフィールドを検索対象にする場合に使用します。

| Property | Description | Type |
| --- | --- | --- |
| FieldType | 検索属性名のタイプ。現在未使用。 | Literal["Text"] |
| ViewName | 表示する属性名 | str |
| Field | レイヤの属性名 | str |

**複数フィールド検索の例:**
```json
"SearchField": {
	"ViewName": "OR検索: 名称, 住所",
	"Field": "名称, 住所"
}
```

この場合、ユーザーが入力した一つの検索語（例: "東京"）で、名称フィールドと住所フィールドの両方をOR条件で検索します（"名称に東京を含む" OR "住所に東京を含む"）。

#### SearchFields

複数の検索フィールド設定です。複数の検索ボックスを作成し、それぞれに異なる検索条件を設定する場合に使用します。

| Property | Description | Type |
| --- | --- | --- |
| FieldType | 検索属性名のタイプ。現在未使用。 | Literal["Text"] |
| ViewName | 表示する属性名 | str |
| Field | レイヤの属性名 | str |

**複数検索ボックスの例:**
```json
"SearchFields": [
	{
		"FieldType": "Text",
		"ViewName": "名称",
		"Field": "名称"
	},
	{
		"FieldType": "Text",
		"ViewName": "住所",
		"Field": "住所"
	}
]
```

この場合、二つの検索ボックスが作成され、ユーザーは一方に"東京"、もう一方に"本社"というように別々の検索語を入力できます。複数の検索ボックスの条件は基本的にAND結合されます（"名称に東京を含む" AND "住所に本社を含む"）。

## その他

| Property | Description | Type |
| --- | --- | --- |
| SampleFields | 未使用 | list[str] |
| SampleTableLimit | 未使用 | list[str] |
| selectTheme | 検索時に適用するQGISマップテーマ名。指定しない場合はテーマ切替なし | str (optional) |

### ViewFields（表示フィールド）の動作詳細

`ViewFields`は検索結果テーブルに表示するフィールドを制御します。以下の動作パターンがあります：

#### 1. 未指定または空配列の場合
```json
"ViewFields": []
// または "ViewFields" キー自体が存在しない
```
→ **レイヤの全フィールドを表示**

#### 2. 存在するフィールドが指定された場合
```json
"ViewFields": ["N03_001", "N03_004", "N03_007"]
```
→ **指定されたフィールドのみ表示**

#### 3. 存在しないフィールドが指定された場合
```json
"ViewFields": ["存在しないフィールド1", "存在しないフィールド2"]
```
→ **何も表示しない**（空のテーブル）+ QGISメッセージログに警告出力

#### 4. 一部が存在し一部が存在しない場合
```json
"ViewFields": ["N03_001", "存在しないフィールド", "N03_007"]
```
→ **存在するフィールド（N03_001, N03_007）のみ表示**

**注意事項：**
- フィールド名はレイヤの実際のフィールド名を指定してください（別名は使用できません）
- 指定されたフィールドが存在しない場合、QGISメッセージログに警告が出力されます
- 大文字小文字やスペースの有無など、正確な名前を指定する必要があります

