# Assessment App MVP Specification
Version: 0.1.0-draft

## 1. Purpose

介護支援専門員が使用する既存のアセスメント帳票を、
ブラウザUIから入力・保存・再編集できるローカルPythonアプリとして実装する。

データはSQLiteに保存する。

既存PDFを帳票テンプレートとして使用し、
保存されたデータを所定位置へ重ねて印刷可能なPDFを生成する。

画面UIは既存帳票をそのまま再現せず、
入力しやすさを優先する。

---

## 2. Technology

- Python 3.13
- FastAPI
- Jinja2
- SQLModel
- SQLite
- ReportLab
- pypdf
- pytest
- HTML/CSS
- 必要最小限のJavaScript

MVPではSPAフレームワークは使用しない。

MVPでは外部クラウドサービスを使用しない。

---

## 3. Domain Model

### Client

利用者そのものを表す。

一人のClientは複数のAssessmentを持つ。

Fields:

- id
- name
- gender
- birth_date
- postal_code
- address
- phone
- mobile_phone
- created_at
- updated_at

### EmergencyContact

- id
- client_id
- name
- relationship
- phone
- mobile
- address
- priority

一人のClientが複数の緊急連絡先を持てる構造とする。

### Assessment

- id
- client_id
- source_assessment_id（初回はNULL、再アセスメント時は参照元AssessmentのID）
- client_snapshot（Assessment作成時点の利用者基本情報）
- received_date
- assessor_name
- office_name
- family_request
- family_structure_text
- living_status
- medical_history
- primary_doctor
- medication_status
- adl_independence_level
- dementia_independence_level
- care_application_status
- care_level
- certification_date
- certification_valid_from
- certification_valid_to
- assessment_reason
- assessment_analysis_result
- disability_certificate_present
- disability_certificate_type
- disability_certificate_grade
- current_services
- created_at
- updated_at

ClientとAssessmentを分離する。

既存Assessmentを更新して履歴を失うのではなく、
状態変化・更新時には新しいAssessmentを作成できる構造とする。

### AssessmentCheck

Assessmentと1対1。

Fields:

- id
- assessment_id
- health_status
- adl
- iadl
- cognition
- communication
- social_relationship
- elimination
- skin
- oral_hygiene
- nutrition
- behavior
- caregiving_capacity
- home_environment
- special_conditions

---

## 4. UI

### Client List

- 利用者一覧
- 氏名検索
- 新規利用者登録
- 利用者詳細
- 最終アセスメント日表示

### Client Form

- 氏名
- 性別
- 生年月日
- 郵便番号
- 住所
- 電話
- 携帯

### Assessment Form

セクション分割する。

#### 受付情報
- 受付日
- 受付者
- 事業所

#### 本人・家族
- 本人・家族の要望
- 家族構成

#### 生活状況
- 生活状況

#### 医療
- 経過・病歴
- 主治医
- 服薬状況

#### ADL・認知
- 障害高齢者の日常生活自立度
- 認知症高齢者の日常生活自立度

#### 認定
- 申請状況
- 要介護度
- 認定日
- 認定有効期間

#### 課題分析
- アセスメント理由
- アセスメント分析結果

#### その他
- 身障手帳
- 種類
- 等級
- 現在利用しているサービス

### Assessment Check Form

以下の14項目をtextareaとして入力する。

- 健康状態
- ADL
- IADL
- 認知
- コミュニケーション能力
- 社会との関わり
- 排尿・排便
- 褥瘡・皮膚の問題
- 口腔衛生
- 食事摂取
- 問題行動
- 介護力
- 居住環境
- 特別な状況

---

## 5. Select Values

### ADL independence

- 正常
- J1
- J2
- A1
- A2
- B1
- B2
- C1
- C2

### Dementia independence

- 正常
- I
- IIa
- IIb
- IIIa
- IIIb
- IV
- M

### Care level

- 要支援1
- 要支援2
- 要介護1
- 要介護2
- 要介護3
- 要介護4
- 要介護5

値はDB内部値と表示ラベルを分離できる設計にする。

---

## 6. PDF

既存PDFを背景テンプレートとして使用する。

PDFサイズはA4 portrait。

PDFをプログラムで再描画しない。

ReportLabで透明なoverlay PDFを生成し、
pypdfで既存PDFへmergeする。

帳票座標はrenderer内へハードコードせず、

app/pdf/coordinates.py

へ集約する。

Example:

FIELD_POSITIONS = {
    "client_name": {
        "x": 0,
        "y": 0,
        "width": 0,
        "height": 0
    }
}

座標値は後工程で調整する。

---

## 7. Text rendering

共通のdraw_text_box()関数を実装する。

Requirements:

- 日本語対応
- 自動改行
- 複数行表示
- 指定width/height内への描画
- font size縮小
- minimum font sizeを下回っても収まらない場合は切り捨てない
- overflowとして検出できる
- PDF生成前にoverflow warningを返せる

---

## 8. PDF output

以下を実装する。

- PDFプレビュー
- PDF生成
- 2帳票を個別生成
- 将来的に2ページPDFとして結合可能な構造

ファイル名例:

assessment_123_20260914.pdf

---

## 9. Assessment history

利用者詳細画面にAssessment履歴を表示する。

Example:

2026-09-14 初回
2027-03-15 更新
2027-07-01 状態変化

過去Assessmentを編集することは可能とするが、
「前回を複製して新規Assessment作成」機能を設ける。

複製時も元レコードは変更しない。

---

## 10. Validation

最低限以下を検証する。

- 利用者氏名必須
- 日付形式
- 認定開始日 <= 認定終了日
- 不正なADL区分を保存しない
- 不正な認知症自立度を保存しない
- 不正な要介護度を保存しない

---

## 11. Security / Privacy

MVPはローカルPC上で使用する。

外部通信を前提としない。

患者・利用者情報を外部APIへ送信する機能は実装しない。

---

## 12. Tests

最低限以下をpytestで実装する。

- Client create
- Client update
- Assessment create
- Assessment update
- Assessment history
- Assessment duplication
- AssessmentCheck create/update
- DB relationship
- validation
- PDF overlay generation
- missing template PDF handling

---

## 13. Not included in MVP

- AIによるアセスメント判断
- AI文章生成
- 外部API
- クラウドDB
- 複数ユーザー認証
- 権限管理
- 家族構成図自動描画
- ケアプラン自動生成

## Assessment Revision / Reassessment Behavior

2回目以降のアセスメントでは、直前のAssessmentを参照元として利用できること。

再アセスメント作成時は、直前のAssessmentの内容を新規Assessment作成画面の初期値として表示する。

利用者は、その内容を確認し、変更・削除・追記した上で保存する。

保存時は既存AssessmentをUPDATEしてはならない。

必ず新しいAssessmentレコードとしてINSERTすること。

参照元となったAssessmentは変更しない。

新しいAssessmentには、どのAssessmentを参照して作成されたかを記録できる構造とする。

例：

Assessment 1
2026-09-14 初回

Assessment 2
2027-03-10 再アセスメント
source_assessment_id = Assessment 1

Assessment 3
2027-09-05 再アセスメント
source_assessment_id = Assessment 2

### Confirmed reassessment rules

- 「直前のアセスメント」は、同一利用者のAssessmentのうち `created_at` が最新のものとする。受付日は判定基準にしない。
- 「再アセスメント作成」操作時点ではDBへ保存しない。前回の内容を初期値としてフォームに表示し、ユーザーが保存した時点で新規Assessmentを作成する。
- 利用者基本情報、アセスメント内容、AssessmentCheckは原則引き継ぐ。
- AssessmentCheckの14項目もすべて引き継ぐ。既存Checkを更新せず、新しいAssessmentに対応する新規Checkレコードとして保存する。
- 受付日、作成日時、更新日時など、今回のアセスメント固有の日付情報は引き継がず、新規値とする。
- 初回Assessmentの `source_assessment_id` はNULLとする。再アセスメントでは、フォームの参照元となったAssessmentのIDを記録する。
- 再アセスメント保存時は必ずINSERTする。参照元のAssessmentおよびAssessmentCheckは変更しない。
- 第9章の過去Assessmentの編集と、再アセスメント作成は別操作として扱う。
- 受付日は再アセスメントフォーム表示時の当日を初期値とし、ユーザーが変更できる。
- `created_at` と `updated_at` は新しいAssessmentの保存時に生成する。以後、そのAssessmentの編集・保存時には `updated_at` を更新する。
- 認定日、認定有効期間は前回の値を初期値として引き継ぎ、ユーザーが変更できる。

### Confirmed Phase 1 input and persistence rules

- 必須入力はClientの氏名のみとし、その他の入力項目は任意とする。
- ADL自立度、認知症自立度、要介護度は第5章の定義済み選択肢を使用する。未入力を許可するが、定義外の値は保存しない。
- 選択肢が未定義の項目は、Phase 1では自由入力を許可する。
- 身障手帳は未入力・有・無の3状態を保持する。モデルはnullable boolとする。
- EmergencyContactはモデルのみ作成する。UI・登録画面・PDF連携はPhase 1に含めない。
- Assessment新規保存時に、対応するAssessmentCheckを必ず1件作成する。未入力項目は空の状態でよい。
- 同一人物のAssessmentは同じClientを参照する。Clientは現在の利用者基本情報を表す。
- Assessment作成時のClient基本情報（氏名、性別、生年月日、郵便番号、住所、電話、携帯）を `client_snapshot` として保持する。新規保存時の現在のClientの値を記録する。
- Client情報の後日変更や過去Assessmentの編集時に、既存の `client_snapshot` を変更しない。将来の帳票出力にはそのAssessmentのスナップショットを使用する。
- 2回目以降は前回Assessmentを参照して新規作成する。前回Assessmentを上書きしない。
- 一覧の最終アセスメント日は、同一Clientに紐づくAssessmentの最新 `created_at` の日付を表示する。既存Assessmentの編集で `created_at` は変更せず、`updated_at` のみ更新する。
- PDF生成はPhase 1では実装しない。
