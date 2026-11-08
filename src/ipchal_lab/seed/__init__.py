"""기존 67개 feature (seed/sql/*.sql, generate.py 가 만든 결과)와 등록."""
from __future__ import annotations

from ..checks import check_feature
from ..registry import add_feature, list_features
from ..runner import FeatureDef
from .generate import CATS, SQL_DIR


def seed_features() -> list[FeatureDef]:
    """파일 이름 순서 = 레거시 FEATURES 순서. 첫 줄 `-- 이름: 설명`."""
    out = []
    for p in sorted(SQL_DIR.glob("*.sql")):
        sql = p.read_text(encoding="utf-8")
        name, desc = sql.split("\n", 1)[0].removeprefix("-- ").split(": ", 1)
        out.append(FeatureDef(name, "범주" if name in CATS else "숫자", sql, desc))
    return out


def seed_all(bq, user: str, base_override: str | None = None) -> list[str]:
    """등록 안 된 seed feature 마다 검사 후 등록 (검사 결과에 따라 상태 '검사통과' 또는 '초안'). 추가한 이름 목록."""
    names = set(list_features(bq, include_retired=True)["name"])
    added = []
    for f in seed_features():
        if f.name in names:
            continue
        add_feature(bq, f, user, check_feature(bq, f, names, base_override=base_override))
        names.add(f.name)
        added.append(f.name)
    return added
