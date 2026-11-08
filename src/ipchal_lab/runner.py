"""feature SQL 실행기 (BigQuery는 한글 열 이름을 `백틱`으로 감싸야 한다): base/targets 임시 테이블을 만들고 feature마다 한 번씩 계산해 한 표로 묶는다."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import sqlglot
from sqlglot import exp

from .bq import TooExpensive
from .guard import Permission

TARGETS_TRAIN = "y IS NOT NULL AND `학습범위_업종`"
KEYS = ["공고번호", "차수"]


@dataclass
class FeatureDef:
    name: str
    kind: Literal["숫자", "범주"]
    sql: str
    description: str = ""


def targets_one(공고번호, 차수):
    return "`공고번호` = @no AND `차수` = @ord", {"no": 공고번호, "ord": 차수}


def _check_tables(f: FeatureDef, settings) -> None:
    if settings.gcp_project in f.sql:
        raise ValueError(f"feature '{f.name}': SQL에 프로젝트 이름을 쓸 수 없습니다. base, targets 만 사용하세요")
    tree = sqlglot.parse_one(f.sql, read="bigquery")
    ctes = {c.alias for c in tree.find_all(exp.CTE)}
    used = {t.name for t in tree.find_all(exp.Table)} - ctes
    bad = used - {"base", "targets"}
    if bad:
        raise ValueError(f"feature '{f.name}': SQL에 테이블 이름 {sorted(bad)} 을(를) 쓸 수 없습니다. base, targets 만 사용하세요")


def _base_sql(settings, base_override):
    return (base_override or f"SELECT * FROM `{settings.table('VIEW_MODEL_BASE')}`").strip().rstrip(";")


def estimate_script_bytes(bq, base_override: str | None = None) -> int:
    """스크립트는 dry-run이 0바이트라 추정이 안 된다. base를 읽는 양(가장 큰 비용)을 대신 본다."""
    return bq.dry_run_bytes(_base_sql(bq.s, base_override))


def build_script(features: list[FeatureDef], targets_where: str, settings, base_override: str | None = None) -> str:
    for f in features:
        _check_tables(f, settings)
    base = _base_sql(settings, base_override)
    # 끝에 "\n;" — SQL이 -- 주석으로 끝나도 세미콜론이 주석에 먹히지 않는다
    parts = [f"CREATE TEMP TABLE base AS {base}\n;",
             f"CREATE TEMP TABLE targets AS SELECT * FROM base WHERE {targets_where}\n;"]
    parts += [f"CREATE TEMP TABLE f_{i} AS {f.sql.strip().rstrip(';')}\n;" for i, f in enumerate(features)]
    cols = "".join(f", f_{i}.value AS `{f.name}`" for i, f in enumerate(features))
    joins = "".join(f" LEFT JOIN f_{i} USING (`공고번호`, `차수`)" for i in range(len(features)))
    parts.append(f"SELECT t.`공고번호`, t.`차수`{cols} FROM targets t{joins};")
    return "\n".join(parts)


def run_features(bq, features, targets_where: str, params: dict | None = None, base_override: str | None = None,
                 max_bytes: int | None = None) -> pd.DataFrame:
    """index=(공고번호, 차수). 숫자는 float64(NULL=NaN), 범주는 object(NULL=None)."""
    sql = build_script(features, targets_where, bq.s, base_override)
    limit = max_bytes if max_bytes is not None else bq.s.max_bytes_per_query
    est = estimate_script_bytes(bq, base_override)
    if est > limit:
        raise TooExpensive(est, limit)
    df = bq.query_df(sql, params, perm=Permission.READ, max_bytes=max_bytes).set_index(KEYS)
    for f in features:
        s = df[f.name]
        df[f.name] = pd.to_numeric(s, errors="coerce").astype("float64") if f.kind == "숫자" else s.astype(object).where(s.notna(), None)
    return df
