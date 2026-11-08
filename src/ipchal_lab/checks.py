"""feature 검사: 이름 규칙, 비용(조회량), 형식(공고당 1행·빠짐·전부 NULL), 미래 정보 누설."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd
import sqlglot
from google.api_core.exceptions import GoogleAPICallError

from .bq import TooExpensive
from .guard import GuardError, Permission
from .runner import KEYS, TARGETS_TRAIN, FeatureDef, _base_sql, _check_tables

RESERVED = {"공고번호", "차수", "value", "y"}
RESULT_COLS = ["y", "`최종낙찰금액`", "`예정가격`", "`참여업체수`"]
LEAK_DAYS = 10
SHAPE_TARGETS = ("DATE(`개찰일시`) BETWEEN DATE_SUB(CURRENT_DATE('Asia/Seoul'), INTERVAL 1 MONTH) "
                 "AND CURRENT_DATE('Asia/Seoul')")


@dataclass
class CheckReport:
    ok: bool
    problems: list[str] = field(default_factory=list)
    bytes_train: int = 0
    null_rate: float = 0.0
    leak_days_checked: int = 0
    bytes_billed_check: int | None = None  # 검사 스크립트가 실제로 청구된 바이트

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def name_problems(f: FeatureDef, existing_names: set[str]) -> list[str]:
    out = []
    if not f.name or re.search(r"[\s`]", f.name):
        out.append(f"이름 '{f.name}'은(는) 비어 있거나 공백·백틱(`)이 있어 쓸 수 없습니다")
    if f.name in RESERVED:
        out.append(f"이름 '{f.name}'은(는) 예약어라 쓸 수 없습니다 ({', '.join(sorted(RESERVED))})")
    if f.name in existing_names:
        out.append(f"이름 '{f.name}'은(는) 이미 등록되어 있습니다")
    if f.kind not in ("숫자", "범주"):
        out.append(f"종류는 '숫자' 또는 '범주'여야 합니다 (지금: '{f.kind}')")
    return out


def check_shape(df_raw: pd.DataFrame, n_targets: int) -> list[str]:
    """feature SQL 원시 결과(LEFT JOIN 전) 검사. 대상 공고마다 정확히 1행, 값이 전부 NULL이면 안 됨."""
    if any(c not in df_raw.columns for c in KEYS + ["value"]):
        return ["결과에 공고번호, 차수, value 열이 모두 있어야 합니다"]
    out = []
    dup = int(df_raw.duplicated(KEYS).sum())
    if dup:
        out.append(f"공고 하나에 2행 이상이 나옵니다 (겹친 행 {dup}개). 공고번호·차수마다 1행이 되게 GROUP BY 하세요")
    n = len(df_raw.drop_duplicates(KEYS))
    if n < n_targets:
        out.append(f"빠진 공고가 있습니다: 대상 {n_targets}건 중 {n}건만 나옵니다. "
                   "targets 에서 LEFT JOIN 해서 과거가 없는 공고도 NULL로 남기세요")
    if len(df_raw) and df_raw["value"].isna().all():
        out.append("값이 모두 비어 있습니다(NULL). SQL 조건을 확인하세요")
    return out


def leak_override_sql(view: str, cutoff_param: str = "cut") -> str:
    """결과 열(y 등)을 개찰일시 >= @cut 이면 NULL로 지운 base. view 는 테이블 이름 또는 (부분 쿼리)."""
    rep = ", ".join(f"IF(`개찰일시` >= @{cutoff_param}, NULL, {c}) AS {c}" for c in RESULT_COLS)
    return f"SELECT * REPLACE ({rep}) FROM {view}"


def build_check_script(f: FeatureDef, dates: list[str], settings, base_override: str | None = None):
    """기준 데이터를 한 번만 읽어 형식 검사(최근 1개월) + 날짜별 원래/결과 지운 base 실행을 한 스크립트로.
    결과 지우기는 늦은 날짜부터 base 위에 차례로 덮어쓴다 (cut이 작아지므로 원본에 바로 적용한 것과 같다)."""
    _check_tables(f, settings)
    sql = f.sql.strip().rstrip(";")
    proj = "`공고번호`, `차수`, value"
    day = "DATE(`개찰일시`)"
    parts = [f"CREATE TEMP TABLE base AS {_base_sql(settings, base_override)}\n;",
             f"CREATE TEMP TABLE targets AS SELECT * FROM base WHERE {SHAPE_TARGETS};",
             "CREATE TEMP TABLE n_targets AS SELECT COUNT(*) AS n FROM targets;",
             f"CREATE TEMP TABLE r_s AS SELECT 's' AS d, 's' AS v, {proj} FROM ({sql}\n);",
             f"CREATE TEMP TABLE t0 AS SELECT * FROM base WHERE {day} IN ({', '.join(f"DATE '{d}'" for d in dates) or 'NULL'});"]
    # 원래 base 실행은 10개 날짜를 한 번에 (targets = t0), 날짜는 t0와 이어 붙여 찾는다
    parts += ["CREATE OR REPLACE TEMP TABLE targets AS SELECT * FROM t0;",
              f"CREATE TEMP TABLE r_o AS SELECT CAST({day} AS STRING) AS d, 'o' AS v, r.`공고번호`, r.`차수`, r.value "
              f"FROM ({sql}\n) r JOIN t0 USING (`공고번호`, `차수`);"]
    runs = ["r_s", "r_o"]
    for i, d in sorted(enumerate(dates), key=lambda x: x[1], reverse=True):
        parts += [f"CREATE OR REPLACE TEMP TABLE base AS {leak_override_sql('base', f'cut{i}')};",
                  f"CREATE OR REPLACE TEMP TABLE targets AS {leak_override_sql('t0', f'cut{i}')} WHERE {day} = DATE '{d}';",
                  f"CREATE TEMP TABLE r_c{i} AS SELECT '{d}' AS d, 'c' AS v, {proj} FROM ({sql}\n);"]
        runs.append(f"r_c{i}")
    parts.append(" UNION ALL ".join(f"SELECT *, CAST(NULL AS INT64) AS n FROM {r}" for r in runs)
                 + " UNION ALL SELECT 'n', 'n', NULL, NULL, NULL, n FROM n_targets;")
    params = {f"cut{i}": datetime.fromisoformat(d) - timedelta(days=6) for i, d in enumerate(dates)}
    return "\n".join(parts), params


def leak_problems(rows: pd.DataFrame, kind: str) -> list[str]:
    """rows: d, v('o' 원래 / 'c' 결과 지움), 공고번호, 차수, value. 같은 공고의 값이 바뀌면 미래 정보."""
    k = ["d"] + KEYS
    o = rows[rows.v == "o"].drop_duplicates(k).set_index(k)["value"]
    c = rows[rows.v == "c"].drop_duplicates(k).set_index(k)["value"]
    o, c = o.align(c, join="outer")
    if kind == "숫자":
        a, b = (pd.to_numeric(x, errors="coerce").astype("float64").to_numpy() for x in (o, c))
        same = np.isclose(a, b, atol=1e-9, equal_nan=True)
    else:
        same = np.array([(x is None or x is pd.NA or x != x) and (y is None or y is pd.NA or y != y) or x == y
                         for x, y in zip(o.astype(object), c.astype(object))], dtype=bool)
    if same.all():
        return []
    bad_days = o.index[~same].get_level_values("d").nunique()
    return [f"미래 정보를 쓰는 것 같습니다: 개찰 6일 전부터의 결과(y, 최종낙찰금액, 예정가격, 참여업체수)를 지우면 "
            f"값이 바뀝니다 ({(~same).sum()}건, {bad_days}일). 과거 통계는 개찰일시 < t − 7일 결과만 쓰세요. "
            "미래 정보를 안 써도 ORDER BY 에 동률이 있으면 실행마다 값이 달라질 수 있습니다: "
            "ORDER BY 끝에 `공고번호`, `차수` 를 붙이세요"]


def cost_sql(f: FeatureDef, settings, base_override: str | None = None) -> str:
    """학습 대상 전체로 feature 하나를 계산하는 한 문장 (dry-run 으로 조회량 추정용)."""
    return (f"WITH base AS ({_base_sql(settings, base_override)}\n), targets AS (SELECT * FROM base WHERE {TARGETS_TRAIN}) "
            f"SELECT * FROM ({f.sql.strip().rstrip(';')}\n)")


@lru_cache(maxsize=8)  # ponytail: 프로세스 동안 날짜 후보 캐시 (feature와 무관). 데이터가 바뀌면 프로세스 재시작
def _candidate_dates(bq, base_override: str | None) -> tuple[str, ...]:
    df = bq.query_df(f"""SELECT CAST(DATE(`개찰일시`) AS STRING) AS d FROM ({_base_sql(bq.s, base_override)})
WHERE y IS NOT NULL AND `학습범위_업종` GROUP BY d HAVING COUNT(*) >= 5 ORDER BY d""")
    return tuple(df["d"])


def check_feature(bq, f: FeatureDef, existing_names: set[str], seed: int = 0,
                  base_override: str | None = None) -> CheckReport:
    problems = name_problems(f, existing_names)
    if problems:
        return CheckReport(False, problems)
    try:
        _check_tables(f, bq.s)
        est = bq.dry_run_bytes(cost_sql(f, bq.s, base_override))
        if est > bq.s.max_bytes_per_query:
            return CheckReport(False, [str(TooExpensive(est, bq.s.max_bytes_per_query))], est)
        cand = _candidate_dates(bq, base_override)
        dates = sorted(np.random.RandomState(seed).choice(cand, min(LEAK_DAYS, len(cand)), replace=False))
        sql, params = build_check_script(f, dates, bq.s, base_override)
        rows = bq.query_df(sql, params, perm=Permission.READ)
    except sqlglot.errors.SqlglotError as e:
        return CheckReport(False, [f"SQL 문법 오류: {e}"])
    except (ValueError, GuardError, TooExpensive, GoogleAPICallError) as e:
        msg = getattr(e, "message", None) or str(e)
        return CheckReport(False, [f"SQL을 실행하지 못했습니다: {msg}"])
    n_targets = int(rows.loc[rows.v == "n", "n"].iloc[0])
    raw = rows[rows.v == "s"]
    problems = check_shape(raw, n_targets) if n_targets else ["최근 1개월 대상 공고가 없습니다 (데이터가 최신인지 확인하세요)"]
    filled = raw.drop_duplicates(KEYS)["value"].notna().sum()
    null_rate = float(1 - filled / n_targets) if n_targets else 1.0
    problems += leak_problems(rows[rows.v.isin(["o", "c"])], f.kind)
    return CheckReport(not problems, problems, est, null_rate, len(dates), getattr(bq, "last_bytes_billed", None))
