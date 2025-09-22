
# 地図検索
　<img width="213" height="35" alt="image" src="https://github.com/user-attachments/assets/8010fdf0-5e57-4215-8b3a-6dcd3e61fc9f" />

最終的には https://github.com/NationalSecurityAgency/qgis-searchlayers-plugin と統合したい  
### UI設定画面(プロジェクトファイルに設定されます)  
<img width="686" height="740" alt="image" src="https://github.com/user-attachments/assets/27cad15f-890f-4bfc-9c61-3660531e7c32" />

### 地番検索  
![image](https://user-images.githubusercontent.com/86514652/183770100-a385fad3-bc25-47f8-919c-659554c1f7e3.png)  

### 地番の所有者検索  
![image](https://user-images.githubusercontent.com/86514652/183770143-61080ecd-7f55-4647-965a-206bc79191d1.png)  

### 汎用的な検索  
![image](https://github.com/yamamoto-ryuzo/GEO-search-plugin/assets/86514652/4483e588-2c1d-4133-9cfe-fc33bb9a5068)  

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
  "ViewFields": ["結果に表示する属性"],
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
      "ViewFields": []
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
      "ViewFields": ["N03_001","N03_004","N03_007"],
      "selectTheme": "行政区域テーマ" // 検索時に適用するQGISマップテーマ名（省略可）
    }

※ `selectTheme` を指定すると、検索時に該当のQGISマップテーマが自動で適用されます。省略した場合はテーマ切替は行われません。



## 課題

### 全体

- 元々検索・結果表示は DB 参照が基本のような記述が存在する
  - 表示項目のカスタマイズ
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
| ViewFields | 検索結果で表示するレイヤ属性（名前：別名はNG） | list[str] |
| Message | 左下のヘルプボタンで表示するテキスト | str |
| TibanField | 地番の属性名 | str |
| AzaTable | 地番検索用: 字コード設定 | dict |
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
| Password | データベースのパスワード | str |
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
  "名称": "",
  "住所": ""
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


## 検索ロジック（実装概要）

### 通常検索（全文検索風）
  - 実装ファイル: `GEO_search/widget/searchwidget.py` (`SearchTextWidget`) と `GEO_search/searchfeature.py` (`SearchTextFeature`).
  - 動作: 検索ボックスに入力された最初の非空値を取得し、設定された検索フィールド（`SearchField` または `SearchFields`）に対して SQL の LIKE 相当の条件を組み立てます。複数フィールドは OR/AND（設定に依存）で結合され、QGIS の `QgsExpression` を用いて `QgsFeatureRequest` に渡して検索します。
  - 正規化: `SearchFeature.normalize_search_value` により全角英数字を半角に変換します。

### 地番検索（地籍検索）
  - 実装ファイル: `GEO_search/widget/searchwidget.py` (`SearchTibanWidget`) と `GEO_search/searchfeature.py` (`SearchTibanFeature`).
  - 動作: 地番用の入力を受け取り、地番属性（`TibanField`）に対する正規表現マッチや、個別フィールドに対する完全一致／あいまい（近傍番号）検索をサポートします。あいまい検索では数値幅（FUZZY）を用いた幅のあるヒットを生成します。地番フィールドは正規表現（`regexp_match`）でマッチングされます。
  - 補助機能: 字コード（`AzaTable`）を読み込んで候補をテーブル表示し、選択で入力欄にセットします。

### 所有者検索（氏名検索）
  - 実装ファイル: `GEO_search/widget/searchwidget.py` (`SearchOwnerWidget`) と `GEO_search/searchfeature.py` (`SearchOwnerFeature`).
  - 動作: 複数フィールドをチェックボタンで選択して検索できます。全角カナ→半角カナや濁音／拗音の変換処理を行い、`replace(... ) LIKE '{value}'` のような式で空白除去やカナ正規化を行った比較を実行します。前方一致／部分一致の切替もサポートします。

### 表示レイヤ検索／全レイヤ検索
  - `SearchTextFeature.show_features` ではタブタイトルが `表示レイヤ` または `全レイヤ` の場合、現在表示されているレイヤ／プロジェクト内全レイヤを横断して検索を行い、結果をレイヤごとのタブで表示します。

### 補助機能
  - サジェスト（補完）機能: `unique_values` を使い `QCompleter` を生成して補完候補を表示します（`Suggest` フラグで有効化）。
  - マップテーマ適用: 検索実行時に `selectTheme` に設定されたマップテーマを適用します（`検索前` という自動保存テーマも利用可能）。