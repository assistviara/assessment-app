# Assessment App — Phase 1 / Phase 2

ローカルPCで利用者情報、Assessment、AssessmentCheckを入力・保存・再編集するアプリです。
Phase 2では1枚目の帳票へ保存済み基本情報・アセスメント内容を重ねます。外部API、クラウド連携は含みません。

## 起動

このワークスペースでは、Python 3.13用の `.venv313` を使用します。
既存の `.venv` はPython 3.12のため使用しません。

```powershell
.\.venv313\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

ブラウザで `http://127.0.0.1:8000/clients` を開きます。停止はターミナルで `Ctrl+C`。
開発中にコードを更新した場合は、このサーバーを停止して同じコマンドで再起動してください。
`--reload`を付けない起動では、ファイルを更新しても実行中サーバーのルート定義は変わりません。
初回起動時に `data/assessment.sqlite3` とテーブルを作成します。
通常起動では既存データを保持します。既存DBのスキーマ移行機能は含みません。

## 環境の準備

別の環境ではPython 3.13を用意し、ワークスペース内で実行してください。

```powershell
python -m venv .venv313
.\.venv313\Scripts\python.exe -m pip install -e ".[test]"
```

このワークスペースのPython本体は `.tools/python313` にあります。
[Python公式配布](https://www.python.org/downloads/release/python-31315/)のWindows用アーカイブを取得し、公式manifestのSHA-256と照合して展開しています。
環境再作成には `.\.tools\python313\python.exe -m venv .venv313` を使用できます。

## テスト

```powershell
.\.venv313\Scripts\python.exe -m pytest -q
```

各テストは `.test-tmp/` 配下の実行ごとの一時SQLiteファイルを使用し、運用DBには接続しません。

## 再アセスメント

1. 利用者詳細で「再アセスメント作成」を選びます。
2. 同一利用者の `created_at` が最新のAssessmentと、そのCheckの14項目を初期表示します。
3. 内容を確認し、変更・削除・追記して「新規保存」を押します。
4. 新しいAssessmentと新しいCheckを一括保存します。参照元は更新しません。

フォームを表示しただけではDBには保存しません。キャンセル時も新規レコードは作成しません。
受付日は表示時の当日が初期値で変更可能です。認定日・認定有効期間は引き継ぎ、変更できます。
作成・更新日時は保存時に生成します。参照元IDは `source_assessment_id` に記録します。
フォーム表示後に別のAssessmentが作られても、そのフォームが実際に参照したIDを保存します。
`created_at` が同一の場合のみ、IDが大きいものを選びます。

履歴の「内容を表示・編集」は、その既存Assessmentを更新する操作です。
再アセスメントを作成する場合は、利用者詳細の専用リンクを使ってください。

## 基本情報の保存と入力ルール

Clientは現在の基本情報を保持します。Assessmentには、新規保存時点のClientの7項目を
`client_snapshot`（JSON、生年月日はISO日付文字列）として別に記録します。
後日Clientを変更しても、過去Assessmentのスナップショットは変わりません。
再アセスメントの基本情報には現在のClientを表示し、新規保存時の値を記録します。
既存Assessmentの編集画面では、作成時のスナップショットを表示します。

氏名のみ必須です。任意項目の空欄はNULLとして保存します。
定義済みの3分類は選択式、未定義の項目は自由入力です。
身障手帳は未入力（NULL）・有（true）・無（false）を保持します。
EmergencyContactはモデルのみで、操作画面はありません。

氏名検索は部分一致、利用者一覧は登録ID降順、履歴は作成日時降順です。
日時はローカルPCの時刻で記録します。受付日などの日付入力はYYYY-MM-DD形式です。

## 主な構成

- `app/models.py`: SQLModelの4モデルとリレーション
- `app/schemas.py`: フォーム入力検証
- `app/services/assessments.py`: 新規・再アセスメントの保存
- `app/routers/`: HTML画面とフォーム受付
- `app/templates/`, `app/static/`: Jinja2とCSS（外部CDNは使用しません）
- `tests/`: pytestによるDB・HTTP・再アセスメント検証
- `docs/assessment_app_spec_v0.1.0.md`: 業務仕様

## URL

| メソッド | URL | 操作 |
|---|---|---|
| GET | `/` | 利用者一覧へ移動 |
| GET | `/clients` | 一覧・氏名検索（`q`） |
| GET | `/clients/new` | 登録画面 |
| POST | `/clients` | 利用者登録 |
| GET | `/clients/{client_id}` | 利用者詳細・履歴 |
| GET | `/clients/{client_id}/edit` | 利用者編集画面 |
| POST | `/clients/{client_id}` | 利用者更新 |
| GET | `/clients/{client_id}/assessments/new` | 初回入力（2回目以降は再アセスメント画面へ移動） |
| POST | `/clients/{client_id}/assessments` | 新規Assessment・Check保存 |
| GET | `/clients/{client_id}/reassessments/new` | 前回内容から新規入力（DB書き込みなし） |
| POST | `/clients/{client_id}/reassessments` | 再アセスメント・Check新規保存 |
| GET | `/assessments/{assessment_id}/edit` | 既存Assessment編集画面 |
| POST | `/assessments/{assessment_id}` | 既存Assessment更新 |
| GET | `/assessments/{assessment_id}/check/edit` | Check入力・編集画面 |
| POST | `/assessments/{assessment_id}/check` | Check保存 |
| GET | `/assessments/{assessment_id}/pdf/assessment` | 保存済み内容を重ねた1枚目PDF |

## Phase 2：1枚目PDFの印刷

保存済みAssessmentの編集画面から「1枚目PDFを開く」を選びます。
ブラウザのPDFビューアから印刷し、A4・縦・実際のサイズ（100%）を指定してください。
フォームで未保存の変更はPDFに含まれません。

- 元帳票: `assets/pdf_templates/assessment_form.pdf`（元ファイルを変更・上書きしません）。
- データ: `Assessment.client_snapshot` と保存済みAssessmentの各項目。現在のClient情報では置き換えません。
- 座標: `app/pdf/coordinates.py` の各欄・選択肢・日付・白塗り領域の定義。
  左上を原点としたmm単位で位置・枠サイズを指定します。文字サイズはptです。
- 方式: ReportLabで文字・選択肢の○印のoverlayを生成し、pypdfで元帳票へ合成します。
  完成PDFはメモリ上で生成し、ブラウザへinlineで返します。
- 日本語フォント: ユーザー承認済みのIPAexゴシック Ver.004.01を埋め込みます。
  `assets/fonts/` に原本フォントとIPAフォントライセンスv1.0を同梱しています。
- 長文は改行・縮小します。枠に収まらない場合や未対応文字がある場合は、切り捨て・置換をせず項目名付きエラーを表示します。
- 固定文字・選択肢・罫線を保持します。白塗りは元帳票の記入済み事業所・受付者の領域だけです。
- 受付日は令和で表示し、令和より前の日付は元号に取消線を付けて西暦表示します。認定情報は旧元号Hに取消線を付け、西暦の年月日を記入します。
- 緊急連絡先は保存時点の履歴がないため空欄です。現在のEmergencyContactを参照しません。
- 2枚目はチェックシート14項目に対応しています。Check編集画面の「2枚目PDFを開く（チェックシート）」から、対象Assessmentに紐づく保存済みAssessmentCheckだけを出力します（`GET /assessments/{assessment_id}/pdf/check`）。未入力は空欄、Check欠落・収まらない長文・未対応文字はエラーになります。
- 2ページ結合、家族構成図の自動作図は未対応です。

項目別の取得元と将来の連絡先履歴案は [PDF項目対応](docs/20260914_pdf_field_mapping.md) を参照してください。

氏名欄は、用紙左上からx=38.5 mm、y=36.0 mm、幅38.0 mm、高さ4.5 mmに設定しています。
標準12 pt、最小8 ptです。元帳票の用紙寸法595.44 × 842.4 pt（A4縦相当）を保持します。
異なる帳票へ差し替える場合は座標の再確認が必要です。

PDFリンクはFastAPIの名前付きルート`assessment_pdf`から生成し、表示中のAssessmentのIDを渡します。
PDF出力で404になる場合は、`http://127.0.0.1:8000/openapi.json` に
`/assessments/{assessment_id}/pdf/assessment` があるか確認してください。
ルートがなければ、旧コードのサーバーが動作していないか確認して再起動します。
ルートがあって応答が「対象のデータが見つかりません。」の場合は、そのIDのAssessmentが保存されているか確認します。

## 検証環境

Python 3.13.15でpytestを実行しています。依存パッケージ内の非推奨警告
（StarletteのHTTPX利用、AnyIOのBlockingPortal別名）が2件出ますが、テストは通過しています。
アプリから外部通信を行う機能はありません。インストール時のみPyPIへの接続が必要です。
