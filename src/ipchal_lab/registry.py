"""features(실험용 등록표) / features_prod(서빙 세트, 추가만) 읽기·쓰기. 값은 항상 쿼리 파라미터로 넘긴다."""
from __future__ import annotations

import pandas as pd

from .guard import Permission
from .runner import FeatureDef

COLS = "name, description, kind, sql, status, created_by, created_at, updated_at, check_report"


def _t(bq, key="TABLE_FEATURES"):
    return f"`{bq.s.table(key)}`"


def _status(report) -> str:
    return "검사통과" if report.ok else "초안"


def list_features(bq, include_retired: bool = False) -> pd.DataFrame:
    where = "" if include_retired else " WHERE status != '폐기'"
    return bq.query_df(f"SELECT {COLS} FROM {_t(bq)}{where} ORDER BY name")


def get_feature(bq, name: str) -> FeatureDef:
    df = bq.query_df(f"SELECT name, kind, sql, description FROM {_t(bq)} WHERE name = @name", {"name": name})
    if df.empty:
        raise KeyError(f"등록된 feature '{name}'이(가) 없습니다")
    r = df.iloc[0]
    return FeatureDef(r["name"], r["kind"], r["sql"], r["description"] or "")


def add_feature(bq, f: FeatureDef, user: str, report) -> None:
    n = bq.query_df(f"SELECT COUNT(*) AS n FROM {_t(bq)} WHERE name = @name", {"name": f.name})["n"].iloc[0]
    if n:
        raise ValueError(f"이름 '{f.name}'은(는) 이미 등록되어 있습니다 (폐기한 것 포함). 다른 이름을 쓰세요")
    bq.execute(f"""INSERT INTO {_t(bq)} ({COLS}) VALUES
(@name, @description, @kind, @sql, @status, @user, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), PARSE_JSON(@report))""",
               {"name": f.name, "description": f.description, "kind": f.kind, "sql": f.sql,
                "status": _status(report), "user": user, "report": report.to_json()}, perm=Permission.LAB)


def update_feature(bq, f: FeatureDef, user: str, report) -> None:
    st = bq.query_df(f"SELECT status FROM {_t(bq)} WHERE name = @name", {"name": f.name})["status"]
    if st.empty:
        raise ValueError(f"등록된 feature '{f.name}'이(가) 없습니다. 먼저 등록(add)하세요")
    if (st == "폐기").any():
        raise ValueError(f"feature '{f.name}'은(는) 폐기되었습니다. 새 이름으로 등록하세요")
    # ponytail: 표에 수정자 열이 없어 user 는 기록하지 않는다. 필요하면 updated_by 열 추가
    bq.execute(f"""UPDATE {_t(bq)} SET sql = @sql, description = @description, kind = @kind,
check_report = PARSE_JSON(@report), status = @status, updated_at = CURRENT_TIMESTAMP() WHERE name = @name""",
               {"name": f.name, "description": f.description, "kind": f.kind, "sql": f.sql,
                "status": _status(report), "report": report.to_json()}, perm=Permission.LAB)


def retire_feature(bq, name: str, user: str) -> None:
    """지우지 않고 상태만 '폐기'로 바꾼다."""
    bq.execute(f"UPDATE {_t(bq)} SET status = '폐기', updated_at = CURRENT_TIMESTAMP() WHERE name = @name",
               {"name": name}, perm=Permission.LAB)


def list_prod(bq) -> pd.DataFrame:
    t = _t(bq, "TABLE_FEATURES_PROD")
    return bq.query_df(f"SELECT * FROM {t} WHERE prod_since = (SELECT MAX(prod_since) FROM {t}) ORDER BY name")


def replace_prod(bq, features: list[FeatureDef], model_version: str) -> None:
    """서빙 세트 전체를 같은 prod_since 로 새로 추가한다 (지우지 않음, 읽을 때 MAX(prod_since))."""
    if not features:
        raise ValueError("서빙 feature 목록이 비어 있습니다")
    params = {"mv": model_version}
    rows = []
    for i, f in enumerate(features):
        params.update({f"n{i}": f.name, f"d{i}": f.description, f"k{i}": f.kind, f"s{i}": f.sql})
        rows.append(f"STRUCT(@n{i} AS name, @d{i} AS description, @k{i} AS kind, @s{i} AS sql)")
    bq.execute(f"""INSERT INTO {_t(bq, "TABLE_FEATURES_PROD")} ({COLS}, model_version, prod_since)
SELECT name, description, kind, sql, '검사통과', NULL, NULL, NULL, NULL, @mv, now
FROM UNNEST([{", ".join(rows)}]) CROSS JOIN (SELECT CURRENT_TIMESTAMP() AS now)""", params, perm=Permission.PROD)
