<p align="center"><a href="./README.md">English</a></p>


# Dynmap / LiveAtlas 公開イベントコレクター

本ツールは、公開されている Dynmap または LiveAtlas のアップデート用 JSON エンドポイントを定期的にポーリングし、サーバーのイベントログ（チャットメッセージ、プレイヤーの参加・退出など）を構造化された JSONL および CSV 形式で保存する、軽量かつ自己完結型の Python スクリプトです。

このコレクターは、Web マップインターフェースが読み込んでいる公開 JSON を読み取るだけで動作します。認証をバイパスしたり、管理者権限を要求したりすることはありません。

---

## 主な機能

- ⚙️ **自己完結型 & 依存ライブラリなし**: 標準の Python 3 のみで動作します（`pip install` は不要です）。デフォルトの設定はローカルの JSON 設定ファイルから読み込まれます。
- 📁 **設定ファイルの自動生成**: 起動時に設定ファイル (`config.json`) が見つからない場合、自動的にデフォルトのテンプレートを生成します。
- 📡 **コマンドライン引数による上書き**: コマンドライン引数を指定することで、設定ファイルの値よりも優先して実行パラメータを指定できます（優先度：CLI引数 > 設定ファイル > プログラム既定値）。
- 📍 **現在座標およびステータスの自動補完**: 最新の公開プレイヤー情報をキャッシュし、イベントへ座標・体力・防具値を補完します。
- 🔌 **入退出イベントの推論モード**: プラグインがネイティブの参加/退出イベントを配信しない場合、オンラインプレイヤーリストの差分を比較して参加/退出（`inferred`）を推論してログに記録できます。
- 🖥️ **詳細表示 (Verbose) モード**: 収集したイベントをリアルタイムにフォーマットし、標準エラー出力 (`sys.stderr`) へ出力します。
- 🔗 **Discord Bridge など source="plugin" を出力するプラグインに対応**: `source` が `"plugin"` のイベントを検知し、`source` を `discord` にマッピングし、`author_name`、`author.username`、`displayName` 等からプレイヤー名を取得します。
- 🎯 **プレイヤー名抽出**: 複数フィールド（`player`、`playerName`、`account`、`author_name`、`author.username`、`displayName` 等）から名前を取得し、様々なソースに対応します。
- 📸 **スナップショット機能**: `--snapshot` オプションで初回取得時のプレイヤー一覧と完全なアップデートペイロードを `JSONL` に保存します（CSV には保存しません）。
- 🛑 **Ctrl+C による安全な終了**: `Ctrl+C` でスクリプトが停止します。状態ファイルは各ポーリング成功時に更新されるため、次回起動時は最後に取得できた更新位置から再開されます。
- 🔄 **自動リトライ**: ネットワークや JSON パースエラーが発生した場合、指数バックオフで自動的に再試行します。

---
## 動作環境

- Python **3.9 以上**
- 標準ライブラリのみ（追加の依存ライブラリ不要）

## クイックスタート

1. **スクリプトを初回起動する**:
   ```bash
   python dynmap_collector.py
   ```
   初回起動時、設定ファイル `config.json` が見つからない場合は自動的にテンプレートが生成されます：
   ```text
   Created a default configuration file template at config.json
   ```
***
**Note:** 初回の `config.json` 作成後、`base` URL が設定されていない場合、スクリプトはエラーで終了します。`base` を設定してから再度実行してください。
***

2. **接続先 Dynmap/LiveAtlas サーバーを設定する**:

   生成された `config.json` を開き、対象サーバーの公開 URL（例: `https://dynmap.example.com`）を `base` に設定します。

   初回生成時は `base` は `null` に設定されています。

   Dynmap / LiveAtlas の公開 URL を設定する際は、JSON の文字列としてダブルクォーテーション (`"`) で囲んでください。

   ```json
   {
     "base": "https://dynmap.example.com"
   }
   ```

   あるいは、コマンドラインから直接指定して起動することも可能です。

   ```bash
   python dynmap_collector.py --base https://dynmap.example.com --verbose --duration 10
   ```
   ---
## プロジェクト構成

```text
dynmap-public-collector/
├── dynmap_collector.py
├── config.json
├── outputs/
│   ├── dynmap_events.jsonl
│   ├── dynmap_events.csv
│   └── dynmap_state.json
└── README.md
```

## 設定ファイル項目定義 (`config.json`)

デフォルトで生成される設定ファイルの内容は以下の通りです：
```json
{
  "base": null,
  "world": null,
  "interval": null,
  "duration": 0.0,
  "timeout": 15.0,
  "jsonl_output": "outputs/dynmap_events.jsonl",
  "csv_output": "outputs/dynmap_events.csv",
  "state_file": "outputs/dynmap_state.json",
  "snapshot": false,
  "infer_player_events": false,
  "verbose": false,
  "user_agent": "dynmap-public-collector/1.0"
}
```

### 各項目の詳細
* `base` (string): Dynmap/LiveAtlas の公開アップデートベース URL。
* `world` (string): 取得対象のワールド名 (例: `world`, `world_nether`)。`null` の場合はサーバー既定のデフォルトワールドが自動設定されます。
* `interval` (float): ポーリング間隔（秒）。`null` の場合はサーバー設定の `updaterate` から自動計算されます（最小値は `1.0` 秒）。
* `duration` (float): 指定された時間（秒）が経過するとスクリプトを終了します。0 または未指定の場合は継続して実行します。
* `timeout` (float): HTTP リクエストの接続タイムアウト時間。
* `jsonl_output` (string/Path): JSONL ログの出力パス。
* `csv_output` (string/Path): CSV ログの出力パス。
* `state_file` (string/Path): ポーリング再開時のタイムスタンプを保存する状態ファイルのパス。
* `snapshot` (boolean): 起動時のオンラインプレイヤー一覧をスナップショットイベントとして保存するかどうか。
* `infer_player_events` (boolean): `true` に設定すると、マップアップデートのプレイヤーリストの差分から参加/退出イベントを推論して記録します。
* `verbose` (boolean): 収集したイベントを読みやすい形式に整形して標準エラー出力へリアルタイムに印刷します。
* `user_agent` (string): 送信される HTTP リクエストのカスタム `User-Agent` ヘッダー。

---

## コマンドライン引数 (CLI Usage)

```text
usage: dynmap_collector.py [-h] [--config CONFIG] [--base BASE]
                                    [--world WORLD] [--since SINCE]
                                    [--interval INTERVAL]
                                    [--duration DURATION] [--timeout TIMEOUT]
                                    [--jsonl-output JSONL_OUTPUT]
                                    [--csv-output CSV_OUTPUT]
                                    [--state-file STATE_FILE] [--snapshot]
                                    [--infer-player-events] [--verbose]
                                    [--user-agent USER_AGENT]
```

### 引数で上書きする例:
`config.json` の設定値を利用しつつ、ポーリング間隔だけを上書きし、リアルタイム出力を有効にする場合：
```bash
python dynmap_collector.py --interval 2.5 --verbose
```

---

## 出力形式

### CSV ヘッダー一覧
出力される CSVファイルのフィールド構成は以下の通りです：
* `collected_at`: イベントがローカルに保存された時刻（UTC ISO 形式）。
* `event_time`: サーバー上でイベントが発生した時刻（UTC ISO 形式）。
* `timestamp`: ミリ秒単位のエポックタイムスタンプ。
* `type`: イベントタイプ (`chat`, `webchat`, `playerjoin`, `playerquit`, `playerjoin_inferred`, `playerquit_inferred`)。
* `source`: イベントソース (`dynmap-update`, `discord`, `player-list-diff`)。
* `player`: プレイヤーの Minecraft アカウント名、または Discord 送信者名。
* `message`: 発言内容。
* `world`, `x`, `y`, `z`: 座標および次元情報 (キャッシュから自動補完)。
* `health`, `armor`: イベント発生時のプレイヤーの体力と防具値。
collected_at,event_time,timestamp,type,source,player,message,world,x,y,z,health,armor

### JSONL スキーマ
JSONL ファイルに保存されるデータ構造も同様のフラットな構造です。`"raw"` キーにノーマライズされる前の元の生の JSON オブジェクトがそのまま保存されています。


