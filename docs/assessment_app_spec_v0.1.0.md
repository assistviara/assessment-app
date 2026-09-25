# Assessment App MVP Specification
Version: 0.1.1-draft

## 1. Purpose

介護支援専門員が使用する既存のアセスメント帳票を、
ブラウザUIから入力・保存・再編集できるローカルPythonアプリとして実装する。

データはSQLiteに保存する。

既存PDFを帳票テンプレートとして使用し、
保存されたデータを所定位置へ重ねて印刷可能なPDFを生成する。

画面UIは既存帳票をそのまま再現せず、
入力しやすさを優先する。

最終的には、事業所内のケアマネジャーがWindows PCで利用できる、
デスクトップ配布可能なアプリケーションとする。
Pythonは内部実装・開発用の技術であり、最終利用者に開発環境やコマンド操作の知識を要求しない。

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

最終的なWindows配布・起動・データ保存方針は第14章に定める。
現段階ではPyInstaller等の具体的なパッケージング方式は固定しない。

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

既存の紙帳票PDFを背景テンプレートとして使用し、SQLiteに保存済みのAssessmentデータを重ねる。

元のPDFテンプレートは変更・上書きしない。
PDFテンプレートは `assets/pdf_templates/` 配下で個別に管理する。
日本語フォント等のPDF生成に必要なリソースもアプリ側で管理し、
フォントは `assets/fonts/` 配下に、必要なライセンス文書と共に配置する。
フォントの採用・取得・同梱は、候補・ライセンス・配置方法を提示して確認を得てから行う。

PDFサイズはA4 portrait。

PDFをプログラムで再描画しない。

ReportLabで透明なoverlay PDFを生成し、
pypdfで既存PDFへmergeする。

過去のAssessmentからPDFを再生成する場合は、そのAssessmentに保存された評価内容と
`client_snapshot` 等の履歴情報を使用する。
Client基本情報にはAssessment新規保存時点のスナップショットを使用し、
現在のClient情報で過去帳票の内容を置き換えない。
これは、第9章および後述の再アセスメント・スナップショット保持仕様を変更するものではない。

帳票が複数PDFに分かれている場合は、テンプレートを個別に管理し、
将来的に必要に応じて複数ページPDFへ結合できる構成とする。

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

PDFテンプレート・フォントの参照は、通常のPython実行時と将来のexe配布時の両方を考慮する。
開発PC固有の絶対パスや起動時のカレントディレクトリに依存せず、
第14章のリソース参照・ユーザーデータ保存の分離方針に従う。

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

長文は自動改行・フォント縮小等で対応し、黙って文字を切り捨てない。
最小文字サイズでも収まらない場合は、生成前に利用者へ通知する。
現Phase 2では1枚目の各入力欄を対象とし、収まらない場合は文字を切り捨てず生成を中止して項目名付きエラーを表示する。

---

## 8. PDF output

### PDF表示・印刷の基本方針

出力PDFはブラウザ上で表示し、利用者が通常の印刷操作でA4縦に印刷できるようにする。
ブラウザから「実際のサイズ / 100%」で印刷する際に元帳票のレイアウトを維持できる構成とし、
生成時に帳票を意図せず拡大・縮小しない。
ブラウザやプリンターによる倍率・余白の差異については、表示確認と試し刷りで確認する。

### 最終的なPDF機能の範囲

以下は段階的に実装する。現Phase 2で全てを実装するものではない。

- PDFプレビュー
- PDF生成
- 2帳票を個別生成
- 将来的に2ページPDFとして結合可能な構造

ファイル名例:

assessment_123_20260914.pdf

### 現Phase 2の対象

- 1枚目のアセスメント表のみを対象とする。
- 元帳票は `assets/pdf_templates/assessment_form.pdf` とする。元ファイルは変更・上書きしない。
- 保存済み `Assessment.client_snapshot` の基本情報とAssessmentの内容を、1枚目の対応欄へ重ねる。取得元は `20260914_pdf_field_mapping.md` に定義する。
- 固定文字・選択肢・罫線を維持し、選択式項目は対応する選択肢へ○印を付ける。記入済み事業所名・受付者だけ生成PDFで必要範囲を白く覆う。
- 緊急連絡先は保存時点のスナップショットがないため空欄とし、現在のEmergencyContactを動的に参照しない。履歴追加は別途設計提示・承認後に行う。
- ReportLabでoverlayを生成し、pypdfで元帳票と合成する。
- 各欄、選択肢、日付の座標と白塗り領域は `app/pdf/coordinates.py` に定義する。
- 採用確認済みのIPAexゴシック Ver.004.01を `assets/fonts/ipaexg.ttf` に配置し、IPAフォントライセンスv1.0の文書を同梱する。PDFには日本語フォントを埋め込む。
- `GET /assessments/{assessment_id}/pdf/assessment` でPDFをブラウザ表示する。
- PDFには保存済みデータを使用し、フォーム上の未保存の変更は反映しない。
- スナップショット氏名が欠落している場合は、現在のClient氏名で補完せず、生成できないことを通知する。
- 生成PDFはメモリ上で組み立てて返却する。将来、アプリが生成PDFをファイル保存する機能を追加する場合は、第14章のユーザーデータ保存方針に従う。
- 2026-09-25追加: 2枚目は指定Assessmentに紐づくAssessmentCheckの14項目を、対応する各行の状態欄へ描画する。健康状態の承認済み配置は維持する。対応と座標は `20260914_pdf_field_mapping.md` に定義する。`GET /assessments/{assessment_id}/pdf/check` で単独1ページをinline応答する。未入力は空欄、Check欠落は明示的エラーとする。既存の折り返し・縮小・切り捨て禁止方針を適用する。他Assessmentや現在のClientから補完しない。複数ページ結合、DB・履歴仕様変更、exe化・配布機能・SQLite保存先変更は対象外。

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

PDFのテストは現Phase 2の範囲に合わせ、保存時点の基本情報・Assessment各項目の使用、日本語フォントの埋め込み、
元テンプレート・DBの不変性、各枠内への描画、選択肢の○印、固定文字の保持、現在の緊急連絡先が混入しないこと、長文・未対応文字・リソース欠落の通知、
ブラウザ表示用のHTTP応答を確認する。実帳票の合成結果を画像化して目視確認する。
ブラウザでの表示とA4・100%での試し刷りは、実施状況と未確認事項を区別して報告する。

将来のWindows配布フェーズでは、開発環境のないPCでのダブルクリック起動、
コンソール非表示、コマンド不要の終了、同梱リソースの読込、書込可能なユーザーデータ保存先、
アプリ更新後の既存データ保持を検証する。exe化やこれらの配布検証は現Phase 2では実施しない。

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

## 14. Windows配布・実行環境

### 利用者と起動・終了

- 最終的に事業所内のケアマネジャーがWindows PCで使用できるexeとして配布する。
- 利用者はPython、Git、コマンドプロンプト、PowerShell等の知識を持たないことを前提とし、配布先PCにPython等の開発環境を要求しない。
- 配布フォルダ内のアプリ起動用exeをダブルクリックするだけで起動できること。
- FastAPI等のローカルWebサーバーをアプリ内部で起動し、必要に応じて既定ブラウザを自動的に開く構成を想定する。
- 起動時・利用中・終了時のいずれも、コマンドプロンプト、PowerShell、ターミナル等のコンソール画面を利用者へ表示しない。
- 起動・利用・終了のために利用者へコマンド操作を要求しない。終了操作とサーバー停止の具体的なUIは配布フェーズで決定する。

### 配布物とリソース

- exe化によって複数ファイルが必要になる場合でも、配布物は1つのフォルダ内にまとめる。
- 利用者が基本的に操作するのは、そのフォルダ内のアプリ起動用exeだけとする。
- PDFテンプレート、フォント、ライセンス文書、画面テンプレート、静的ファイル等の必要なリソースは、配布フォルダ内で完結する構成とする。
- `assets/pdf_templates/`、`assets/fonts/` 等のリソース参照は、Python実行時だけでなくexe化された場合にも対応できる構造を意識する。
- リソース位置の解決を集約できる構造とし、開発PC固有の絶対パス、起動時のカレントディレクトリ、開発環境の仮想環境の存在に依存しない。
- 読込用の配布リソースと、書込用のユーザーデータでは保存先・参照先を分離する。具体的な配布方式に依存するパス処理は配布方式決定時に実装する。

### ユーザーデータと更新

- SQLiteデータベースや、アプリがファイル保存する生成PDF等のユーザーデータは、アプリ本体・配布リソースと分離して保存する。
- アプリの更新・配布フォルダの差し替えによって、既存の利用者データを失わない構造とする。
- ユーザーデータ保存先は、書込権限と更新時の保持を考慮して配布フェーズで決定する。現時点では具体的なフォルダを固定しない。
- 保存先を変更する際は既存DBの保全・引継ぎを前提とし、新しい空DBへ黙って切り替えることで既存データを見失うことがないようにする。
- Phase 1のDBモデル、Assessment履歴、source_assessment_id、client_snapshotの保持仕様は変更しない。

### 実施時期

- 現段階ではPyInstaller等の具体的なパッケージング方式を仕様として固定しない。
- exe化、コンソール非表示の起動・終了制御、ブラウザ自動起動、配布物の作成、保存先移行・更新方法の実装は将来の配布フェーズで行う。
- 今後の実装では、exe化を困難にするパス依存・開発環境依存を可能な限り避ける。
- 今回の仕様改訂では要件の統合と現在の実装への影響確認を行い、exe化や既存DBの移動・仕様変更は実施しない。
