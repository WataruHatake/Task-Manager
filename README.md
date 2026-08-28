# DANDORI

Windows向けの、完全ローカルで動作するタスク管理アプリです。

## 現在実装されている機能

- タスクの登録、編集、完了
- タスク名、メモ、状態、重要度、期限、カテゴリの保存
- タスク一覧
- 月カレンダーの「日付 → 当日タスク → 詳細」表示
- 約180pxの右端タスク表示とタスク追加
- ダーク/ライトテーマ
- `D:\TaskManager\Data\tasks.db` へのローカル保存

Windows通知、グローバルショートカット、自動起動、繰り返し、サブタスク、添付は今後追加予定です。

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
4. 「DANDORIのセットアップが完了しました」と表示されるまで待つ。
5. `scripts\run_windows.cmd` をダブルクリックする。

仮想環境はアプリフォルダー内の `.venv` へ自動作成されます。DBはアプリ本体と分けて `D:\TaskManager\Data` へ保存されます。

## 起動できない場合

`scripts\run_debug_windows.cmd` を実行し、表示されたエラー文を確認します。画面を閉じるまでコンソールは消えません。

## 開発環境でのテスト

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```
