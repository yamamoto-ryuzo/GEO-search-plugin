
# GEO Search System / 地図検索システム

## 目次 / Table of Contents

- [GEO Search System / 地図検索システム](#geo-search-system--地図検索システム)
  - [目次 / Table of Contents](#目次--table-of-contents)
  - [About (English)](#about-english)
  - [概要（日本語）](#概要日本語)
  - [主要機能 / Key Features](#主要機能--key-features)
    - [検索機能](#検索機能)
    - [テーマ追加表示モードと管理](#テーマ追加表示モードと管理)
    - [Quick Start (English)](#quick-start-english)
    - [Core search features (details in SEARCH.md)](#core-search-features-details-in-searchmd)
    - [Search details and per-tab configuration](#search-details-and-per-tab-configuration)
  - [Qt6/QGIS (3.44+) 対応について](#qt6qgis-344-対応について)
  - [トラブルシュート: 画面が空白／属性列が非常に狭い場合](#トラブルシュート-画面が空白属性列が非常に狭い場合)
      - [一部が存在し一部が存在しない場合](#一部が存在し一部が存在しない場合)
  - [検索ロジック（実装概要）](#検索ロジック実装概要)
  - [パンモード（地図表示の移動挙動）](#パンモード地図表示の移動挙動)
  - [更新履歴](#更新履歴)


## About (English)

This repository implements the GEO Search System — a modular map-search system for QGIS. The system is centered on a search subsystem (lot-number, owner-name and attribute searches) and complementary subsystems such as theme/visualization management. It provides configurable per-tab search definitions, per-layer result presentation, and optional map-theme application during searches. The system targets QGIS 3.x and includes compatibility support for both Qt5 and Qt6 (`supportsQt6=True`).

## 概要（日本語）

本リポジトリは `GEO Search System` を構成するモジュール群（検索サブシステム、テーマ／表示管理サブシステムなど）を含む、QGIS 上で動作する大規模な地図検索システムの実装です。地番検索、所有者検索、汎用属性検索を中心とした検索機能と、検索時に表示・復元するためのテーマ管理機能（追加表示モード等）を組み合わせて、既存プロジェクト上で柔軟に検索結果を可視化できます。Qt5・Qt6 両対応を目指しており、QGIS 3.x 上での利用を想定しています。

## 主要機能 / Key Features

### 検索機能

- **検索タイプ:** 地番検索（地籍筆番）、所有者名検索、汎用属性検索。
- **結果表示:** レイヤごとにタブ表示し、表示フィールドを設定可能。大きな結果もページングで扱う。
- **操作:** 結果行のクリックで地図上の該当フィーチャへズーム／選択。ビュー設定はユーザ設定に従う。
- **目的:** 既存の QGIS プロジェクトに対し、土地情報検索を簡単に実行・参照できることを主眼とする。

### テーマ追加表示モードと管理

- **追加表示モード:** 検索結果を既存プロジェクトの表示に「追加」するモード（既存レイヤや凡例を保持しつつ検索結果を追加表示）。
- **テーマ/スタイル:** 検索時に表示レイヤのスナップショットを取り、凡例表示状態とレイヤごとのスタイル名（ID）を保存。復元時には（非可視から復元する場合など）保存したスタイル名をベストエフォートで適用する。
- **利点:** 既存プロジェクトの視覚的な設定を尊重しつつ、検索ワークフローでスタイル切替や表示の復元を行える。

### Quick Start (English)

- Install: copy the `geo_search` folder into your QGIS user plugins directory or install the ZIP via `Plugins → Manage and Install Plugins → Install from ZIP`.
- Start: enable the plugin in QGIS and click the toolbar button to open the Search dialog.
- Search: select or configure a search tab, enter a query (lot number / owner name / attribute) and click `Search`.
- View results: results appear in per-layer tabs; click a row to zoom/select on the map. Use the table header to auto-resize columns if needed.
- Troubleshooting: if columns appear collapsed or empty, try reloading the plugin or restarting QGIS; run the diagnostic snippet in the README to collect console logs.

### Core search features (details in [SEARCH.md](./SEARCH.md))

The plugin's core search features (lot-number search, owner-name search, and general attribute search) and implementation details have been moved to [SEARCH.md](./SEARCH.md).

日本語: プラグインの基本検索機能（地番検索・所有者検索・汎用属性検索）および実装概要は [SEARCH.md](./SEARCH.md) に分離しました。詳しくは [SEARCH.md](./SEARCH.md) をご確認ください。
　<img width="213" height="35" alt="image" src="https://github.com/user-attachments/assets/8010fdf0-5e57-4215-8b3a-6dcd3e61fc9f" />

### Search details and per-tab configuration

Search-related detailed settings and usage (UI settings, search types, configuration examples) have been moved to [SEARCH.md](./SEARCH.md). See `SEARCH.md` for per-tab settings, examples, and quick-start usage in Japanese.

## Qt6/QGIS (3.44+) 対応について

このリポジトリは Qt5 と Qt6 の両方で動作するよう互換性対応を行っています（QGIS 3.44 以降の Qt6 ビルド上でも動作することを目標としています）。主な対応点:

- `metadata.txt` に `supportsQt6 = True` を追加済み
- PyQt の import を `from qgis.PyQt import ...` に正規化
- `geo_search/qt_compat.py` に Qt5/6 の差分（enum/flags、exec_/exec のラッパー、QDockWidget フラグ等）と小さな monkey-patch を追加
- Qt6 固有の描画タイミング差に対する UI の安定化（ヘッダーのリサイズ方法や最終列のストレッチ、最小幅の設定）を導入

注意: QGIS 本体のビルドや環境（QGIS のバージョン、OS、ディスプレイ環境）により振る舞いが変わる場合があります。下の「既知の問題と対処」をご確認ください。

## トラブルシュート: 画面が空白／属性列が非常に狭い場合

Qt6 環境で検索結果ダイアログの属性列が極端に狭くなったり、テーブルが一見空に見えることが報告されています。対処法:

- プラグイン無効化→上書き→有効化、または QGIS を再起動してから再実行する
- 結果ダイアログで列を右クリック→「列を自動調整」やウィンドウをリサイズして表示を試す
- それでもダメな場合、Python コンソールで以下の診断スニペットを実行して内部状態を出力し、出力をここに貼ってください（fields_count / features_count、column widths を確認します）:

```python
# qgis Python コンソールで実行
plg = qgis.utils.plugins.get('geo_search')
dlg = getattr(plg, 'dialog', None)
if not dlg:
  print("dialog not found on plugin instance")
else:
  print("tab count:", dlg.tabWidget.count())
  for i, tab in enumerate(dlg._tabs):
    layer = tab.get('layer')
    fields = tab.get('fields') or []
    features = tab.get('features') or []
    tbl = tab.get('table')
    print(f"TAB {i}: name={(dlg.tabWidget.tabText(i) if i < dlg.tabWidget.count() else 'n/a')}")
    print("  layer:", getattr(layer, 'name', lambda: layer)())
    print("  fields_count:", len(fields))
    print("  features_count:", len(features))
    if fields:
      labels = []
      for f in fields[:5]:
        try:
          labels.append(f.displayName())
        except Exception:
          ## 設定／設定ファイルの詳細

          検索に関する設定項目（タブ設定編集、`setting.json` のフォーマット、`ViewFields` の動作、パンモードなど）の詳細は `SEARCH.md` に移動しました。設定例や構成の詳細は次を参照してください:

          - [SEARCH.md](./SEARCH.md)

          ## 更新履歴
```json
"ViewFields": ["存在しないフィールド1", "存在しないフィールド2"]
```
→ **何も表示しない**（空のテーブル）+ QGISメッセージログに警告出力

#### 一部が存在し一部が存在しない場合
```json
"ViewFields": ["N03_001", "存在しないフィールド", "N03_007"]
```
→ **存在するフィールド（N03_001, N03_007）のみ表示**

**注意事項：**
- フィールド名はレイヤの実際のフィールド名を指定してください（別名は使用できません）
- 指定されたフィールドが存在しない場合、QGISメッセージログに警告が出力されます
- 大文字小文字やスペースの有無など、正確な名前を指定する必要があります


## 検索ロジック（実装概要）

検索ロジックの詳細は `SEARCH.md` に移動しました。実装ファイルや動作の詳細はそちらをご参照ください。


## パンモード（地図表示の移動挙動）

検索結果を選択した後に地図がどのように移動するかを制御する「パンモード」機能があります。設定は検索ダイアログの `panModeComboBox`（UI）から選択でき、プラグイン起動時に選択値がすべての検索タブへ伝搬されます。主なモード:

- ズーム to 選択（デフォルト） — 選択された地物に合わせて自動的にズーム。
- 中心パン（ズーム維持） — 現在の縮尺を保ったまま選択地物の中心へパン。
- 固定スケール表示 — 指定したスケール（`scaleComboBox` で選択）で中心を合わせて表示。未指定時は中心パンと同等の振る舞い。
- アニメーションパン — 滑らかなアニメーションで中心位置へ移動し、最終的に選択地物を含む範囲へフィット。
- 選択のみ（ビュー変更なし） — 地物を選択するが地図表示は変更しない。

## 更新履歴

- **V1.0.0** — 基本検索機能の実装: 地番検索、所有者検索、汎用属性検索などのコアな検索機能。
- **V2.0.0** — 設定・UI・互換性の改善（タブ設定編集、テーマドロップダウン、テーマ選択の追加、Qt5/6互換など）。
- **V3.0.0** — テーマ選択の本格導入、追加表示モードと凡例/スタイルの改善（スナップショットにスタイル名を保存し、復元時に適用）。


