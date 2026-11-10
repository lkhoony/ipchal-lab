"""SQL 쓰기 가드: 허용 목록에 없는 쓰기·삭제·DDL·EXECUTE IMMEDIATE 는 실행 전에 거부."""
from __future__ import annotations

from enum import Enum

import sqlglot
from sqlglot import exp

from .config import Settings


class GuardError(Exception):
    pass


class Permission(Enum):
    READ = 0
    LAB = 1
    PROD = 2


_DML = (exp.Insert, exp.Update, exp.Merge, exp.Delete, exp.Create, exp.Drop, exp.Command, exp.TruncateTable)


def _name(node: exp.Expression) -> str:
    t = node.this if isinstance(node, exp.Schema) else node
    return ".".join(p.name for p in t.parts)


def _allowed(s: Settings, perm: Permission) -> set[str]:
    keys = ["TABLE_FEATURES", "TABLE_EXPERIMENTS"] if perm.value >= 1 else []
    if perm.value >= 2:
        keys.append("TABLE_FEATURES_PROD")
    return {s.table(k) for k in keys}


def check_sql(sql: str, settings: Settings, perm: Permission) -> None:
    try:
        stmts = [x for x in sqlglot.parse(sql, read="bigquery") if x is not None]
    except sqlglot.errors.SqlglotError as e:
        raise GuardError(f"SQL을 해석할 수 없어 실행하지 않습니다: {e}") from None
    if not stmts:
        raise GuardError("실행할 SQL이 비어 있습니다")
    ok = _allowed(settings, perm)
    for st in stmts:
        if isinstance(st, exp.Command):
            raise GuardError("해석할 수 없는 문장(EXECUTE IMMEDIATE 등)은 실행하지 않습니다")
        if isinstance(st, exp.Query):
            if st.find(*_DML):
                raise GuardError("조회 안에 쓰기·삭제 문장이 숨어 있어 실행하지 않습니다")
            continue
        inner = [n for n in st.walk() if isinstance(n, _DML) and n is not st]
        if inner:
            raise GuardError("문장 안에 다른 쓰기·삭제 문장이 숨어 있어 실행하지 않습니다")
        if isinstance(st, exp.Create):
            props = st.args.get("properties")
            kind = (st.args.get("kind") or "").upper()
            if kind == "TABLE" and props and props.find(exp.TemporaryProperty):
                t = st.this.this if isinstance(st.this, exp.Schema) else st.this
                if t.args.get("db") or t.args.get("catalog"):
                    raise GuardError("임시 테이블 이름에는 데이터셋을 붙일 수 없습니다")
                continue
            raise GuardError("테이블·뷰는 만들 수 없습니다 (임시 테이블만 가능)")
        if isinstance(st, exp.Merge):
            raise GuardError("MERGE 문은 지원하지 않습니다 (INSERT 또는 UPDATE를 쓰세요)")
        if isinstance(st, (exp.Insert, exp.Update)):
            name = _name(st.this)
            if name not in ok:
                raise GuardError(f"이 권한({perm.name})으로는 {name} 테이블에 쓸 수 없습니다")
            continue
        raise GuardError(f"허용되지 않는 문장입니다: {type(st).__name__} (삭제·DROP·ALTER 등은 막혀 있습니다)")
