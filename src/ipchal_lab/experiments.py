"""실험 기록 (experiments 표): 추가와 읽기. 값은 항상 쿼리 파라미터로 넘긴다."""
from __future__ import annotations

import json
import secrets
from datetime import datetime

import pandas as pd

from .evaluate import EVAL_VERSION, EvalResult
from .guard import Permission
from .runner import FeatureDef


def _t(bq):
    return f"`{bq.s.table('TABLE_EXPERIMENTS')}`"


def record_experiment(bq, user: str, features: list[FeatureDef], result: EvalResult, note: str,
                      serving_version: str | None = None) -> str:
    eid = f"exp-{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
    r, s = result, result.split
    # 숫자는 문자열 파라미터로 넘기고 SQL에서 CAST (bq.py 는 dict 값을 STRING/DATE/DATETIME/ARRAY<STRING> 로만 보냄)
    bq.execute(f"""INSERT INTO {_t(bq)} (experiment_id, created_at, user, features, feature_sql, eval_version,
train_end, eval_start, eval_end, n_eval, hit01, hit01_se, hit10, calibration, baseline_emp_hit01,
baseline_serving_hit01, serving_version, note, serving_status) VALUES
(@id, CURRENT_TIMESTAMP(), @user, @features, PARSE_JSON(@feature_sql), @ev, @train_end, @eval_start, @eval_end,
CAST(@n_eval AS INT64), CAST(@hit01 AS FLOAT64), CAST(@se AS FLOAT64), CAST(@hit10 AS FLOAT64), CAST(@cal AS FLOAT64),
CAST(@emp AS FLOAT64), CAST(@baseline_serving AS FLOAT64), @sv, @note, @serving_status)""",
               {"id": eid, "user": user, "features": [f.name for f in features],
                "feature_sql": json.dumps({f.name: f.sql for f in features}, ensure_ascii=False), "ev": EVAL_VERSION,
                "train_end": s.train_end, "eval_start": s.eval_start, "eval_end": s.eval_end, "n_eval": r.n_eval,
                "hit01": r.hit01, "se": r.hit01_se, "hit10": r.hit10, "cal": r.calibration,
                "emp": r.baseline_emp_hit01, "baseline_serving": r.baseline_serving_hit01, "sv": serving_version,
                "note": note, "serving_status": "없음"}, perm=Permission.LAB)
    return eid


def list_experiments(bq, limit: int = 20) -> pd.DataFrame:
    return bq.query_df(f"""SELECT experiment_id, created_at, user, features, n_eval, hit01, hit01_se, hit10,
baseline_emp_hit01, baseline_serving_hit01, serving_status, note FROM {_t(bq)} ORDER BY created_at DESC LIMIT {int(limit)}""")


def get_experiment(bq, experiment_id: str) -> dict:
    df = bq.query_df(f"SELECT * FROM {_t(bq)} WHERE experiment_id = @id", {"id": experiment_id})
    if df.empty:
        raise ValueError(f"실험 '{experiment_id}'이(가) 없습니다. ipchal experiment list 로 번호를 확인하세요")
    return df.iloc[0].to_dict()
