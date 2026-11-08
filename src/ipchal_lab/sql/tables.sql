-- 실험 환경 테이블. 문장은 세미콜론으로 끝낸다 (admin init 이 문장별로 있는지 보고 없으면 만든다). 주석에 세미콜론 금지.
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.{TABLE_FEATURES}` (
  name STRING, description STRING, kind STRING, sql STRING, status STRING,
  created_by STRING, created_at TIMESTAMP, updated_at TIMESTAMP, check_report JSON
);
-- 서빙 feature: 승인·되돌리기마다 전체 세트를 새로 INSERT (지우지 않음). 읽을 때는 MAX(prod_since) 세트.
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.{TABLE_FEATURES_PROD}` (
  name STRING, description STRING, kind STRING, sql STRING, status STRING,
  created_by STRING, created_at TIMESTAMP, updated_at TIMESTAMP, check_report JSON,
  model_version STRING, prod_since TIMESTAMP
);
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.{TABLE_EXPERIMENTS}` (
  experiment_id STRING, created_at TIMESTAMP, user STRING, features ARRAY<STRING>, feature_sql JSON,
  eval_version STRING, train_end DATE, eval_start DATE, eval_end DATE, n_eval INT64,
  hit01 FLOAT64, hit01_se FLOAT64, hit10 FLOAT64, calibration FLOAT64,
  baseline_emp_hit01 FLOAT64, baseline_serving_hit01 FLOAT64, serving_version STRING, note STRING,
  serving_status STRING, requested_by STRING, requested_at TIMESTAMP, request_reason STRING,
  decided_by STRING, decided_at TIMESTAMP, decision_note STRING, model_version STRING
);
