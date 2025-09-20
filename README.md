
# 地図検索

> **2025/09 更新:**
>
> 各検索タブごとに「QGISマップテーマ（selectTheme）」を選択できるようになりました。タブ設定編集ダイアログでテーマを指定すると、検索時に自動でそのテーマが適用されます。

最終的には https://github.com/NationalSecurityAgency/qgis-searchlayers-plugin と統合したい  
### UI設定画面(プロジェクトファイルに設定されます)  
<img width="698" height="741" alt="image" src="https://github.com/user-attachments/assets/a942f8ae-09b7-49b2-a4e3-53d9e712b877" />

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
- 「selectTheme」欄で、QGISプロジェクト内の任意のマップテーマを選択できます（空欄の場合はテーマ切替なし）。
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




