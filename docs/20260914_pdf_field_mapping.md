# 1枚目アセスメント表のPDF項目対応

PDF生成は保存済みデータの読み取りだけを行い、DB、元PDF、client_snapshotを更新しない。
基本情報を現在のClientから補完しない。欄に収まらない値や未対応文字は、項目名付きエラーとして通知し、黙って切り捨てない。

| PDF項目 | 取得元 | 表示方法 |
|---|---|---|
| 利用者名 | `Assessment.client_snapshot["name"]` | 保存時の氏名 |
| 性別 | `client_snapshot["gender"]` | 男・女の対応位置に○印 |
| 生年月日 | `client_snapshot["birth_date"]` | 保存された日付 |
| 住所 | `client_snapshot["postal_code"]`, `["address"]` | 郵便番号と住所を併記 |
| 電話番号 | `client_snapshot["phone"]`, `["mobile_phone"]` | 電話・携帯を併記。どちらかだけの場合も表示 |
| 受付日 | `Assessment.received_date` | 令和の年月日と曜日。令和より前は元号を取消線で残して西暦表示 |
| 受付者 | `Assessment.assessor_name` | 保存値 |
| 事業所名 | `Assessment.office_name` | 保存値 |
| 緊急連絡先 | 参照しない | Assessment保存時点の履歴がないため空欄。現在のEmergencyContactが存在しても転記しない |
| 本人・家族の要望 | `Assessment.family_request` | 自動改行・縮小 |
| 家族構成 | `Assessment.family_structure_text` | 家族構成欄へ文章を表示。図は自動生成しない |
| 生活状況 | `Assessment.living_status` | 自動改行・縮小 |
| 経過・病歴 | `Assessment.medical_history` | 自動改行・縮小 |
| 主治医 | `Assessment.primary_doctor` | 自動改行・縮小 |
| 服薬状況 | `Assessment.medication_status` | 自動改行・縮小 |
| 障害高齢者の日常生活自立度 | `Assessment.adl_independence_level` | 正常、分類文字、区分番号に○印 |
| 認知症高齢者の日常生活自立度 | `Assessment.dementia_independence_level` | 正常、ローマ数字、a/b/Mに○印 |
| 申請状況 | `Assessment.care_application_status` | 保存された自由入力値 |
| 要介護度 | `Assessment.care_level` | 要介護と1～5に○印。要支援は○印と区分番号を余白に補記 |
| 認定日 | `Assessment.certification_date` | 固定Hを取消線で残し、西暦の年月日を記入 |
| 認定有効期間 | `Assessment.certification_valid_from`, `certification_valid_to` | 開始・終了を同様の西暦年月日で表示 |
| 課題分析（アセスメント理由） | `Assessment.assessment_reason` | 自動改行・縮小 |
| アセスメント分析結果 | `Assessment.assessment_analysis_result` | 自動改行・縮小 |
| 身体障害者手帳の有無 | `Assessment.disability_certificate_present` | True=有に○、False=無に○、NULL=印なし |
| 手帳種類 | `Assessment.disability_certificate_type` | 保存値 |
| 手帳等級 | `Assessment.disability_certificate_grade` | 保存値 |
| 現在利用しているサービス | `Assessment.current_services` | 自動改行・縮小 |

## 関連情報と対象範囲

`AssessmentCheck`の14項目は2枚目チェックシート用であり、1枚目へ別の意味で転記しない。
緊急連絡先はClientとの1対多の関連テーブルであり、現在のDBにはAssessment別のスナップショットはない。
現在のレコードの有無にかかわらず空欄とし、推測で連絡先を作成しない。
一部フィールドがNULLの場合も、存在する他の値は出力する。

## 確定した表示方針

元PDFには事業所・受付者の既存記入、性別・自立度・認定等の印刷済み選択肢がある。
記入済み事業所名と受付者の領域だけ生成PDF上で白く覆う。元PDFファイルは変更しない。
罫線・項目名・固定文字・選択肢は消さない。○印と必要な補記で選択値を表す。
申請状況は自由入力なので、印刷済み選択肢へ推測で分類せず、同じ行の右余白へ保存値を表示する。
身体障害者手帳の種類・等級は固定の「種級」「種」「級」を残し、右の記入欄に順に表示する。
長文は改行・縮小し、最小サイズでも収まらなければ生成前にエラーを返す。
性別の自由入力値が元帳票の男・女に対応しない場合も、推測で丸を付けずエラーを返す。

## 今後の緊急連絡先スナップショット案（未実装・要事前承認）

- Assessmentへnullable JSONの `emergency_contacts_snapshot` を追加する案とする。
- 1件ごとに `name`, `relationship`, `phone`, `mobile`, `address`, `priority` を保存する配列とする。モデルの携帯番号フィールドは `mobile`。
- `NULL` は「当時の情報を保存していない」、空配列は「保存時点で連絡先なし」と区別する。既存AssessmentはNULLとし、現在値で遡及補完しない。
- 初回のAssessment保存時に確認済み連絡先をコピーし、Assessmentと同じトランザクションで保存する。フォーム表示だけではDBへ保存しない。
- 再アセスメントでは参照元のスナップショットを初期値として表示し、確認・修正後の値を新規Assessmentへ保存する。現在のClient連絡先を採用する場合は明示的な取込み操作にする。
- 過去AssessmentのPDFはこの配列だけを参照する。現在のEmergencyContactの更新・削除では変化させない。
- 元帳票は2行のため、3件以上の扱い（別紙等）はDB変更前に仕様を確定する。切り捨てない。
- 実装前に列追加のマイグレーション、バックアップ・復旧手順、入力UI、既存NULLの扱い、保存・再保存・再アセスメントのテストを提示し、承認を得る。

今回、モデル・DB構造・保存処理は変更していない。

## 検証結果（2026-09-14）

- pytest: 113件成功。依存ライブラリの既存非推奨警告2件。
- Uvicornの `/assessments/1/pdf/assessment` がHTTP 200・application/pdf・inlineで応答。
- 保存済みAssessmentと架空の長文・複数行・別選択値のPDFを画像化し、全ページを目視確認。
- 受付日・受付者・事業所・氏名・住所・電話・要望・家族構成・生活状況・病歴・主治医・服薬・自立度・認定情報・課題分析・分析結果・手帳・サービスの位置を確認。
- 文字の重なり、はみ出し、日本語文字化け、追加された罫線欠損なし。元画像に由来する線のかすれは保持。
- 元背景と生成PDFの画像比較テストで、指定した記入済み2領域以外の背景文字・罫線が消えていないことを確認。
- 現在のEmergencyContactを追加・変更しても過去AssessmentのPDF内容が変わらないことをテスト。
- 実DBの論理ダンプと元PDFのSHA256が生成前後で同一。原本・DB・スナップショットを変更しない。
- ブラウザUIの直接操作と紙への試し刷りは未実施。PDF実体の画像確認とHTTP応答まで確認済み。

## 2枚目：元帳票の確認とDB対応候補（実装保留）

配置済みの `assets/pdf_templates/assessment_checksheet.pdf` を画像化して確認したが、
内容は「ApeosPortシリーズ アドレス帳を登録する」という操作手順書であり、アセスメント帳票ではなかった。
1ページ、595.44 × 842.4 pt。確認時のSHA256は
`2d3c98e6130b44f748d5fd02c2d69c48c5aec1f50391f997d482aed9cff8c057`。
このファイルは変更・上書きしていない。

以下はDB・既存入力画面から確認した対応候補であり、帳票上の項目名や位置を確認済みとするものではない。
座標・表示領域・帳票側の選択肢は、正しい2枚目の提供後に確定する。

| 既存入力画面の項目名 | 帳票上の項目名 | DB取得元候補 | 描画座標 | 表示形式案 | 現DBの入力形式 |
|---|---|---|---|---|---|
| 健康状態 | 未確認 | `AssessmentCheck.health_status` | 未確定 | 保存文字列を折り返し・縮小 | 自由記述 |
| ADL | 未確認 | `AssessmentCheck.adl` | 未確定 | 同上 | 自由記述 |
| IADL | 未確認 | `AssessmentCheck.iadl` | 未確定 | 同上 | 自由記述 |
| 認知 | 未確認 | `AssessmentCheck.cognition` | 未確定 | 同上 | 自由記述 |
| コミュニケーション能力 | 未確認 | `AssessmentCheck.communication` | 未確定 | 同上 | 自由記述 |
| 社会との関わり | 未確認 | `AssessmentCheck.social_relationship` | 未確定 | 同上 | 自由記述 |
| 排尿・排便 | 未確認 | `AssessmentCheck.elimination` | 未確定 | 同上 | 自由記述 |
| 褥瘡・皮膚の問題 | 未確認 | `AssessmentCheck.skin` | 未確定 | 同上 | 自由記述 |
| 口腔衛生 | 未確認 | `AssessmentCheck.oral_hygiene` | 未確定 | 同上 | 自由記述 |
| 食事摂取 | 未確認 | `AssessmentCheck.nutrition` | 未確定 | 同上 | 自由記述 |
| 問題行動 | 未確認 | `AssessmentCheck.behavior` | 未確定 | 同上 | 自由記述 |
| 介護力 | 未確認 | `AssessmentCheck.caregiving_capacity` | 未確定 | 同上 | 自由記述 |
| 居住環境 | 未確認 | `AssessmentCheck.home_environment` | 未確定 | 同上 | 自由記述 |
| 特別な状況 | 未確認 | `AssessmentCheck.special_conditions` | 未確定 | 同上 | 自由記述 |

### 履歴・関連モデルの扱い

- `AssessmentCheck.assessment_id` は一意で、対象Assessmentと1対1。PDFは指定Assessmentに紐づくCheckだけを読む方針。
- 再アセスメントでは別のAssessmentCheckが新規保存される。最新の別Assessmentや現在のClientから値を補完しない。
- 現在の14項目はいずれもnullableな文字列で、構造化された選択値を持たない。文章の意味を推測して○印へ変換しない。
- 2枚目に氏名等の欄がある場合は、帳票確認後にAssessmentのclient_snapshotとの対応を検討する。現在のClient・EmergencyContactは参照しない。
- 現行Check編集はそのAssessmentのCheckを更新する構造であり、編集前の版を遡って再現する機能はない。今回、保存仕様・DB構造は変更しない。

### 未対応の理由と再開後の実装案

- 各欄の描画・座標・選択肢の○印・白塗り範囲：正しい元帳票がないため未対応。
- 正しい帳票を確認後、14項目との対応を確定し、座標を `app/pdf/coordinates.py` に定義する。選択欄の対応する保存値がない場合は未対応として明記し、必要な構造化フィールドと履歴保持案を別途提示する。
- ルートは `GET /assessments/{assessment_id}/pdf/check`、名前は `assessment_check_pdf` を予定。`url_for` で「2枚目PDFを開く」を追加する。現段階ではルート・ボタンを追加していない。
- 正しい帳票を用いて、保存内容・空欄・日本語・複数行・overflow・履歴の分離・DB非更新・背景保持のテストと画像による目視確認を行う。選択式テストは保存値との対応を確認できた項目について追加する。
- 今回の変更は本対応表のみ。1枚目のコード、DB、元PDFは変更していない。2枚目の出力テストは未追加。
