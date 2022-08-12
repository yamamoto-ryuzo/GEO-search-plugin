# 地図検索  
最終的には https://github.com/NationalSecurityAgency/qgis-searchlayers-plugin と統合したい  
　地番検索  
![image](https://user-images.githubusercontent.com/86514652/183770100-a385fad3-bc25-47f8-919c-659554c1f7e3.png)  
　地番の所有者検索  
![image](https://user-images.githubusercontent.com/86514652/183770143-61080ecd-7f55-4647-965a-206bc79191d1.png)  
　汎用的な検索  
![image](https://user-images.githubusercontent.com/86514652/183770212-813b8b44-e19f-4c50-a5ec-5df970539e17.png)  
## 設定項目

```json
詳しいサンプルは，プラグインに添付されている「setting.json.sample」を参照ください
そのうち，環境設定ようの画面も作成予定ですが，日本のベースレジストリ対応が先かな？
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
      "SampleTableLimit": 100 // 一時テーブルに表示で表示される件数
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

## 課題

### 全体

- 元々検索・結果表示は DB 参照が基本のような記述が存在する
  - 表示項目のカスタマイズ
- 一時テーブルにサンプルテーブルという表示

### 地番検索

- 結果テーブルで確認される属性[m2]と[筆状態]が不明

### 所有者検索

- 氏名の間にあるスペースの処遇
