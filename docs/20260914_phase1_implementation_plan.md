# Phase 1 実装計画・確定設計

対象仕様: `assessment_app_spec_v0.1.0.md` と2026-09-14の追加指示。
計画承認後の確定事項（再アセスメント、基本情報のスナップショット）を反映する。

## 作成ファイル

- `app/main.py`, `app/db.py`: FastAPI起動、SQLite初期化、接続ごとの外部キー制約、Session管理。
- `app/models.py`: Client、EmergencyContact、Assessment、AssessmentCheck。
- `app/schemas.py`, `app/choices.py`: 入力検証と内部値・表示ラベルの分離。
- `app/form_fields.py`, `app/views.py`: 帳票項目と画面共通処理。
- `app/routers/clients.py`, `app/routers/assessments.py`: HTMLのGET、保存用POST。
- `app/services/assessments.py`: 新規・再アセスメントの一括保存と既存編集。
- `app/templates/`: 共通レイアウト、利用者一覧・詳細・フォーム、Assessmentフォーム、Checkフォーム。
- `app/static/style.css`: 外部CDNを使わない画面スタイル。
- 各Pythonパッケージの `__init__.py`。
- `tests/`: 起動、利用者、Assessment、Check、再アセスメント、スナップショット、関係制約、入力検証。
- `pyproject.toml`, `.gitignore`, `README.md`。
- 実行環境: `.tools/python313`, `.venv313`。既存 `.venv` は保持。
- 実行時生成: `data/assessment.sqlite3`、テスト専用 `.test-tmp/`。

## モデル責務・関係

| モデル | 責務 | 関係 |
|---|---|---|
| Client | 現在の利用者基本情報 | Assessment、EmergencyContactそれぞれと1対多 |
| EmergencyContact | 利用者の緊急連絡先 | client_idでClientを参照。Phase 1はモデルのみ |
| Assessment | 各回の評価と作成時の基本情報 | client_id、任意のsource_assessment_id、Checkとの1対1 |
| AssessmentCheck | 14項目の自由記述 | assessment_idに外部キー・UNIQUE制約 |

Assessmentの `source_assessment_id` は自己参照外部キー。初回はNULL。
新規AssessmentとCheckは同じトランザクションでINSERTする。
利用者が異なる参照元は保存処理で拒否する。
`client_snapshot` は7項目のJSONとして新規保存時のClientから生成し、以後の通常編集では変更しない。
PDF出力は後工程でこのスナップショットを使用する。

## URL

正確な一覧は `README.md` の「URL」に記載する。
利用者の一覧・詳細・登録・編集、初回Assessment、再アセスメント、既存Assessment編集、Check編集を用意する。
再アセスメントはGET `/clients/{client_id}/reassessments/new` で初期表示、POST `/clients/{client_id}/reassessments` で保存する。
2回目以降に初回用画面へアクセスした場合は再アセスメント画面へ移動する。

## 実装順序

1. 構造・依存関係・FastAPI・DB初期化を作成。
2. 4モデル、基本情報スナップショット、入力検証を作成。
3. 利用者一覧・検索・登録・編集・履歴を作成。
4. Assessment・Checkの新規保存と編集を作成。
5. 最新created_atによる参照元選択、フォーム初期表示、再アセスメント新規保存を接続。
6. pytestで正常系・入力エラー・参照元保護・一括保存失敗を検証。
7. Uvicornのローカル起動と手順書を確認。

## 再アセスメントの確定動作

- 同一Clientの最新created_atを参照する。受付日は選定に使わない。同時刻のみID降順で確定する。
- 作成操作ではDBを書き換えず、Assessment内容とCheck全14項目をフォームへ初期表示する。
- 受付日は表示時の当日で変更可能。認定日・認定有効期間は前回値を引き継ぎ、変更可能。
- 基本情報は同じClientの現在値を参照し、新規保存時の値をスナップショットにする。
- 保存時の入力値で新規Assessment・Checkを作成する。削除された入力を前回値で補完しない。
- source_assessment_idにはフォームで実際に参照したIDを保存する。
- created_atとupdated_atは保存時に新規生成。既存Assessment編集ではupdated_atのみ更新する。
- 参照元Assessment・Check・スナップショットは変更しない。

## 想定テスト

- Clientの登録・更新、必須氏名、日付、任意項目、検索、HTMLエスケープ。
- Assessment初回保存、空のCheckの同時作成、再表示・編集。
- 履歴・最終日が利用者別のcreated_atに基づくこと。
- 再アセスメント表示時にDBが増えず、保存時に2件のINSERTのみを実行すること。
- 14項目を引き継ぎ、変更・削除・追記でき、元レコードに影響しないこと。
- 受付日の初期値と変更、認定日・有効期間の引き継ぎ、日時の新規生成。
- 3回目が2回目を参照し、画面表示後の別Assessment作成で参照元がすり替わらないこと。
- Client変更後も過去スナップショットが不変、新規Assessmentには現在情報が記録されること。
- 定義外分類・不正日付・逆転した認定期間を保存しないこと。
- 外部キー・Check一意制約・別利用者参照の拒否。
- Check保存失敗時は新規Assessmentもロールバックすること。
- 再起動後のデータ保持とHTTP起動。

## 対象外・実装上の取り決め

PDF関連、EmergencyContactの画面、削除機能、認証、外部APIは対象外。
必須は氏名のみ、未定義の選択項目は自由入力、空欄はNULL、身障手帳はnullable bool。
一覧はID降順、氏名検索は部分一致、日時はローカルPC時刻、DBは `data/assessment.sqlite3`。
これらの画面順・技術的設定は変更可能な実装上の取り決めとして明示する。
業務入力・再アセスメント・スナップショットに関する確認事項は回答済み。
