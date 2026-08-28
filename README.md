# DANDORI

Windows向けの、完全ローカルで動作するタスク管理アプリです。

## 現在実装されている機能

- タスクの登録、編集、完了
- タスク名、メモ、状態、重要度、期限、カテゴリの保存
- タスク一覧
- 月カレンダーの「日付 → 当日タスク → 詳細」表示
- `Ctrl + Alt + N` で右端タスク追加を直接開閉
- `Ctrl + Alt + T` で右端タスク表示を直接開閉
- 約180px・全高・タイトルバーなしの右端パネル
- 右端パネル内のタスク表示／追加／全表示の切り替え
- カテゴリの追加、名称変更、色変更、削除
- 30分単位の期限時刻プルダウンと直接入力
- Windowsログイン時の自動常駐と二重起動防止
- デスクトップショートカット
- ダーク/ライトテーマ
- `D:\TaskManager\Data\tasks.db` へのローカル保存

Windows通知、繰り返し、サブタスク、添付は今後追加予定です。

## Windowsでの初回セットアップ

### 前提

- Windows 11
- Python 3.12.2
- `D:` ドライブを利用できること
- pipからPythonパッケージを導入できる

### 手順

1. Gitでリポジトリを取得するか、ZIPをダウンロードして展開する。
2. プロジェクトフォルダーを `D:\TaskManager\App\DANDORI` へ配置する。
3. `scripts\setup_windows.cmd` をダブルクリックする。
4. `DANDORI setup completed.` と表示されるまで待つ。
5. `scripts\run_windows.cmd` をダブルクリックする。

仮想環境はアプリフォルダー内の `.venv` へ自動作成されます。DBはアプリ本体と分けて `D:\TaskManager\Data` へ保存されます。セットアップ時にデスクトップへ `DANDORI`、`DANDORI Add`、`DANDORI Tasks` のショートカットが作成されます。

## 普段の使い方

DANDORIはWindowsログイン時に画面を出さず、通知領域へ常駐します。

- タスクを追加する: `Ctrl + Alt + N`
- タスクを確認する: `Ctrl + Alt + T`
- 同じショートカットをもう一度押す: 右端パネルを閉じる
- 全表示を開く: デスクトップの `DANDORI`、または通知領域のDANDORIアイコン
- 完全に終了する: 通知領域のDANDORIを右クリックし、「完全終了」

右端パネルの `×` や全表示画面の `×` ではアプリは終了せず、通知領域へ戻ります。

## 起動できない場合

`scripts\run_debug_windows.cmd` を実行し、表示されたエラー文を確認します。画面を閉じるまでコンソールは消えません。

## 開発環境でのテスト

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```
