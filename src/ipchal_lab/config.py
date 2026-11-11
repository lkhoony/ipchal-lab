"""설정 읽기: 환경변수 -> 설정 폴더(CONFIG_DIR)의 ipchal-lab.env. 사용자 이름은 같은 폴더 user.env."""
from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path

KEYS = ("GCP_PROJECT BQ_DATASET BQ_LOCATION TABLE_BID_LIST TABLE_BSIS_AMOUNT TABLE_OPN_STD_BID "
        "TABLE_OPN_STD_SCSBID TABLE_SCSBID_STTUS TABLE_TARGET_INDSTRYTY TABLE_INDSTRYTY_BASE "
        "VIEW_MODEL_BASE TABLE_FEATURES TABLE_FEATURES_PROD TABLE_EXPERIMENTS GCS_BUCKET GCS_PREFIX "
        "MAX_BYTES_PER_QUERY").split()


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    gcp_project: str
    bq_dataset: str
    bq_location: str
    table_bid_list: str
    table_bsis_amount: str
    table_opn_std_bid: str
    table_opn_std_scsbid: str
    table_scsbid_sttus: str
    table_target_indstryty: str
    table_indstryty_base: str
    view_model_base: str
    table_features: str
    table_features_prod: str
    table_experiments: str
    gcs_bucket: str
    gcs_prefix: str
    max_bytes_per_query: int
    user_name: str | None = None

    def table(self, key: str) -> str:
        """'TABLE_FEATURES' -> '프로젝트.데이터셋.이름' (VIEW_* 도 가능)."""
        return f"{self.gcp_project}.{self.bq_dataset}.{getattr(self, key.lower())}"


def CONFIG_DIR(home: Path | None = None) -> Path:
    """설정·로그인 폴더. 플러그인 데이터 폴더(<데이터>/tools/ipchal-lab)에 설치됐으면 <데이터>/config
    (플러그인을 지우면 같이 지워진다), 아니면 ~/.ipchal-lab."""
    p = Path(sys.prefix)
    if home is None and p.parent.name == "tools" and p.parents[1].parent.name == "data":
        return p.parents[1] / "config"
    return (home or Path.home()) / ".ipchal-lab"


def _parse(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if v and v[0] in "\"'" and v.count(v[0]) >= 2:
            v = v[1:v.index(v[0], 1)]
        else:
            v = v.split(" #", 1)[0].split("\t#", 1)[0].strip()
        out[k.strip()] = v
    return out


def load_settings(env: Mapping[str, str] | None = None, home: Path | None = None) -> Settings:
    if env is None:
        import os
        env = os.environ
    d = CONFIG_DIR(home)
    vals = {**_parse(d / "ipchal-lab.env"), **_parse(d / "user.env")}
    vals.update({k: v for k, v in env.items() if k in KEYS + ["USER_NAME"] and v != ""})
    missing = [k for k in KEYS if not vals.get(k)]
    if missing:
        raise ConfigError("설정에 없는 항목: " + ", ".join(missing)
                          + f" (담당자에게 설정 파일을 받아 {d} 폴더에 넣으세요)")
    kw = {f.name: vals[f.name.upper()] for f in fields(Settings) if f.name.upper() in vals}
    try:
        kw["max_bytes_per_query"] = int(kw["max_bytes_per_query"])
    except ValueError:
        raise ConfigError("MAX_BYTES_PER_QUERY 는 숫자여야 합니다") from None
    return Settings(**kw)
