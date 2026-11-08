"""ipchal admin init: 기준 뷰와 실험 테이블을 만든다 (이미 있으면 건너뜀)."""
from __future__ import annotations

import re
from pathlib import Path

from google.api_core.exceptions import NotFound

from .config import KEYS, Settings
from .guard import Permission

SQL_DIR = Path(__file__).parent / "sql"


def render_sql(name: str, settings: Settings) -> str:
    sql = (SQL_DIR / f"{name}.sql").read_text(encoding="utf-8")
    vals = {"project": settings.gcp_project, "dataset": settings.bq_dataset}
    vals.update({k: getattr(settings, k.lower()) for k in KEYS if k.startswith(("TABLE_", "VIEW_"))})
    for k, v in vals.items():
        sql = sql.replace("{" + k + "}", v)
    return sql


def _exists(bq, name: str) -> bool:
    try:
        bq.client.get_table(name)
        return True
    except NotFound:
        return False


def admin_init(bq, settings: Settings) -> list[str]:
    if settings.role != "admin":
        raise PermissionError("관리자만 초기 설정을 할 수 있습니다 (설정의 ROLE=admin)")
    todo = [("VIEW_MODEL_BASE", f"CREATE VIEW IF NOT EXISTS `{settings.table('VIEW_MODEL_BASE')}` AS\n"
             + render_sql("model_base", settings))]
    raw = (SQL_DIR / "tables.sql").read_text(encoding="utf-8")
    rendered = render_sql("tables", settings)
    for tmpl, stmt in zip(raw.split(";"), rendered.split(";")):
        m = re.search(r"\{(TABLE_\w+)\}", tmpl)
        if m:
            todo.append((m.group(1), stmt.strip()))
    created = []
    for key, sql in todo:
        name = settings.table(key)
        if _exists(bq, name):
            continue
        bq.execute(sql, perm=Permission.ADMIN)
        created.append(name)
    return created
