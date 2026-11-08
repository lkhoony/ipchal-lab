# 운영 워크플로: 데이터 → feature → 모델 → 서빙

이 문서는 실제 운영에서 데이터가 어떻게 쌓이는지 설명합니다. 이어서 feature가 모델에 어떻게 들어가고, 모델이 GCP 어디에 어떤 형태로 저장되며, 예측 서버가 그것을 어떻게 쓰는지를 다룹니다. 실제 이름(프로젝트, 테이블, 버킷)은 비공개 설정 파일의 **키 이름**으로만 적습니다.

> **지금 범위:** 데이터 수집 → feature 등록 → 실험 → 승인 → GCS 저장 → 되돌리기까지 만들어져 있습니다.
> **아직 없는 것:** 예측 REST 서버, 정기 자동 재학습. 아래 [6. 아직 없는 것](#6-아직-없는-것)을 보세요.

---

## 1. 한눈에 보기

```
                        (매일, 자동)
나라장터 Open API ──► 수집 Job (별도 저장소, Cloud Run + Scheduler)
                        │ 원본 테이블에 추가 (ipchal-lab은 읽기만)
                        ▼
BigQuery ─ 원본 수집 테이블들
         └ VIEW_MODEL_BASE (뷰)  : 공고 1건 = 1행, 공고 정보 + 결과(y). 조회할 때마다 최신 원본을 읽음
                        │
        ┌───────────────┴──────────────────┐
        ▼ (사람, 수시)                       ▼ (관리자 승인 때만)
TABLE_FEATURES (실험용 등록표)        TABLE_FEATURES_PROD (운영 feature 사본, 기록용)
TABLE_EXPERIMENTS (실험·요청·승인 기록)
                        │ 승인
                        ▼
GCS  gs://GCS_BUCKET/GCS_PREFIX/
       ├ v01/model.joblib, v01/manifest.json
       ├ v02/model.joblib, v02/manifest.json   (버전 폴더는 한 번 쓰면 덮어쓰지 않음)
       └ serving.json  → {"version": "v02", "previous": "v01", ...}  ← 지금 운영 버전
                        │
                        ▼
예측 REST 서버 (아직 없음): serving.json → manifest → feature SQL 실행 → model.joblib로 예측
```

---

## 2. 데이터: 매일 자동으로 쌓인다

- 수집 Job은 매일 나라장터 API를 호출해 BigQuery 원본 테이블에 공고·개찰 결과를 넣습니다. 이 Job은 별도 저장소에 있으며, ipchal-lab은 그 저장소와 Job을 건드리지 않습니다.
- `VIEW_MODEL_BASE`는 **뷰**(저장된 쿼리)입니다. 따로 갱신하지 않아도 조회할 때마다 그 시점의 원본을 읽습니다. 그래서 어제 수집된 공고도 오늘 feature 계산에 바로 쓰입니다.
- 뷰의 SQL은 `src/ipchal_lab/sql/model_base.sql`에 있고, 관리자가 `ipchal admin init`을 실행할 때 한 번 만들어집니다. 이미 있으면 다시 만들지 않습니다. 그래서 이 SQL 파일을 바꿔도 BigQuery의 뷰는 그대로입니다. 뷰를 바꾸려면 관리자가 따로 교체해야 하며, 이 절차는 아직 명령으로 제공하지 않습니다.

---

## 3. feature: 실험용과 운영용은 분리돼 있다

| | 실험용 `TABLE_FEATURES` | 운영 `manifest.json` (+ 사본 `TABLE_FEATURES_PROD`) |
|---|---|---|
| 누가 바꾸나 | 누구나 (`features add/update/retire`) | 관리자 승인·되돌리기 때만 |
| 내용 | feature 이름, 종류, SQL, 상태(검사통과·초안·폐기), 만든 사람 | 승인 시점 SQL을 **그대로 복사** |
| 운영에 영향 | 없음 | 운영 모델이 실제로 쓰는 정의 |

- 실험용 feature를 고치거나 폐기해도 **운영 모델은 바뀌지 않습니다.** 운영 모델은 자기 `manifest.json`에 복사해 둔 SQL만 씁니다.
- `TABLE_FEATURES_PROD`는 사람이 "운영에서 뭐 쓰지?"를 BigQuery에서 보기 위한 사본입니다. 예측 서버는 이 테이블이 아니라 **manifest**를 읽어야 합니다. manifest가 진짜 기준입니다.
- feature 하나는 SQL 조각입니다. 입력은 `base`(= 기준 뷰)와 `targets`(값을 계산할 공고들), 출력은 `공고번호, 차수, value`입니다. 학습할 때와 예측할 때 **같은 SQL**을 실행하므로, 학습 때와 예측 때 계산이 어긋나지 않습니다.
- 미래 정보 규칙(개찰 7일 전보다 앞선 결과만 사용)은 등록할 때 자동으로 검사합니다. 예측 시점에 최근 7일 결과가 아직 다 수집되지 않았을 수 있기 때문입니다 (manifest의 `known_lag_days: 7`).

---

## 4. 모델: 승인할 때 한 번 학습해서 GCS에 저장한다

### 4.1 실험 (사용자 PC)

`ipchal experiment run`은 사용자 PC에서 다음 순서로 진행됩니다.

1. BigQuery에서 feature를 계산해 받아 옵니다.
2. 학습/평가 기간(마지막 12개월 = 평가)으로 나눠 LightGBM 기반 모델을 학습합니다.
3. 경험 분포·운영 모델과 비교한 결과를 `TABLE_EXPERIMENTS`에 남깁니다.

이 단계에서는 모델 파일을 저장하지 않습니다. 기록만 남깁니다.

### 4.2 승인 (`ipchal serving approve`, 관리자 PC)

순서가 중요합니다. **운영 전환(serving.json)은 맨 마지막**입니다. 중간에 실패하면 운영은 이전 그대로 남습니다.

1. 요청 상태인지, 요청자와 승인자가 다른지 확인합니다.
2. 실험에 쓴 feature가 모두 **검사통과**이고, 등록표의 SQL이 실험 당시와 **같은지** 확인합니다. 그사이 고쳐졌으면 거부하고 실험을 다시 돌리라고 안내합니다.
3. 그 feature 조합으로 **전체 기간** 데이터를 다시 학습합니다.
4. 새 버전 번호를 GCS에서 정하고(`v01`, `v02` …), `vNN/model.joblib`을 업로드합니다. 이미 있으면 실패하므로 덮어쓰지 않습니다.
5. `vNN/manifest.json`을 업로드합니다 (역시 덮어쓰지 않음).
6. `serving.json`을 새 버전으로 바꿉니다. 읽었을 때와 세대(generation)가 같을 때만 쓰는 **조건부 쓰기**라서, 두 관리자가 동시에 승인해도 한쪽만 성공합니다.
7. `TABLE_FEATURES_PROD`에 이 버전의 feature 목록을 추가하고, 실험 상태를 `승인`으로 바꿉니다.

### 4.3 manifest.json에 들어 있는 것

| 항목 | 용도 |
|---|---|
| `version`, `created_at`, `experiment_id`, `requested_by`, `approved_by` | 누가 언제 어떤 실험을 올렸는지 |
| `train_end` | 학습에 쓴 마지막 개찰일 |
| `metrics` | 승인 근거가 된 평가 결과 (`eval_version` 포함) |
| `features[]` | 이름·종류·설명·**SQL** (예측 때 그대로 실행) |
| `categories` | 범주 feature의 학습 당시 값 목록 |
| `known_lag_days`, `target` | 7일 규칙, 타겟 정의 |
| `libs` | Python·ipchal-lab·lightgbm·scikit-learn·pandas·numpy 버전. 모델 파일은 pickle이라 **같은 버전으로 읽어야** 함 |
| `model_base_sha256` | 학습 당시 패키지에 들어 있던 기준 뷰 SQL의 지문 |

### 4.4 되돌리기

`ipchal serving rollback v01` 하나로 되돌립니다.

- `serving.json`이 v01을 가리키게 바뀌고, `TABLE_FEATURES_PROD`도 v01 manifest 기준으로 다시 채워집니다.
- 파일은 지우지 않으므로 언제든 다시 v02로 돌아갈 수 있습니다.
- 예측 서버가 serving.json을 다시 읽는 순간부터 예전 모델이 쓰입니다.

---

## 5. 예측 서버가 지켜야 할 계약 (서버를 만들 때)

모델이 바뀌어도 서버 코드를 고치지 않도록, 서버는 아래 순서만 따릅니다.

1. `gs://GCS_BUCKET/GCS_PREFIX/serving.json`을 읽어 현재 `version`을 얻습니다. 주기적으로, 또는 요청마다 generation을 비교해 바뀌었을 때만 다시 읽습니다.
2. `vNN/manifest.json`과 `vNN/model.joblib`을 내려받아 메모리에 둡니다.
3. 예측 요청(공고번호, 차수)이 오면 manifest의 feature SQL을 `targets` = 그 공고로 실행합니다. ipchal-lab의 `run_features`와 `targets_one`을 그대로 쓰면 됩니다.
4. `model.predict_proba(...)`, `model.report(...)`로 0.01·0.1 구간 top-5와 투찰 금액을 계산합니다.
5. 서버는 `manifest.libs`와 **같은 버전**의 ipchal-lab 패키지와 라이브러리로 실행합니다. 모델 클래스(`FeatureMaskedModel`) 자체가 바뀔 때만 서버의 패키지 버전을 올립니다.

---

## 6. 아직 없는 것

| 없는 것 | 지금은 | 만들려면 |
|---|---|---|
| 예측 REST 서버 | 서빙 결과물(GCS 파일) 형식만 정해져 있음 | 5장 계약대로 Cloud Run 서비스로 만들기 (별도 작업) |
| 정기 자동 재학습 | 모델은 **승인할 때만** 학습됨. 데이터가 매일 쌓여도 모델은 그대로 | 운영 manifest의 feature로 매월 다시 학습해 새 버전을 만드는 Job + 자동 비교 후 관리자 승인 |
| 기준 뷰 변경 절차 | `admin init`은 이미 있으면 건너뜀 | 뷰 교체 명령 + 지문 비교 경고 |
| 운영 모니터링 | 없음 | 예측과 실제 결과를 매일 비교해 적중률 추적 |

따라서 지금 "자동"인 것은 **데이터 수집**과 **뷰를 통한 최신 데이터 반영**뿐입니다. feature가 운영에 들어가는 일과 모델 학습·전환은 모두 **사람의 요청과 관리자 승인**으로만 일어납니다.

---

## 7. 안전장치 요약

공유 계정이 소유자 권한이라 GCP 권한으로는 막을 수 없습니다. 그래서 프로그램이 직접 막습니다.

- 일반 사용자 권한으로 쓸 수 있는 BigQuery 테이블은 `TABLE_FEATURES`, `TABLE_EXPERIMENTS`뿐입니다. `TABLE_FEATURES_PROD`는 관리자의 승인·되돌리기 명령만 씁니다. 관리자 권한은 초기 설정 때문에 쓰기 범위가 넓지만, 명령들은 정해진 테이블에만 씁니다. DELETE·DROP·TRUNCATE·ALTER·MERGE는 누구든 거부합니다.
- 모든 쿼리는 미리 조회량을 계산(dry-run)하고 상한(`maximum_bytes_billed`)을 겁니다. 상한을 넘으면 사람에게 묻습니다.
- GCS 쓰기는 `GCS_PREFIX/` 아래만 하고, 버전 폴더는 새로 만들기만 합니다. 삭제는 하지 않습니다.
- Cloud Run, Scheduler, IAM은 건드리지 않습니다.
- 추가로 BigQuery 하루 조회량 한도를 관리자가 콘솔에서 걸어 둡니다.
