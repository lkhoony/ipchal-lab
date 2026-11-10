"""서빙 요청·승인·반려·되돌리기. GCS 는 GCS_PREFIX/ 아래에만 쓰고 지우지 않는다.

순서: model.joblib, manifest.json (새 버전 폴더, 덮어쓰기 금지) → serving.json (읽은 세대일 때만) → features_prod → 실험 상태.
serving.json 이 기준(서빙이 읽는 곳)이고 features_prod 는 사람이 보는 사본이라, serving.json 이 바뀐 뒤에만 바꾼다.
"""
from __future__ import annotations

import hashlib
import io
import json
import platform
import re
from datetime import datetime, timezone
from importlib.metadata import version as _libver
from pathlib import Path

import joblib
import pandas as pd
from google.api_core.exceptions import PreconditionFailed

from .evaluate import _DAY, _Y
from .experiments import get_experiment
from .guard import Permission
from .model import FeatureMaskedModel
from .registry import replace_prod
from .runner import TARGETS_TRAIN, FeatureDef, run_features

FORMULA = "(최종낙찰금액 / (기초금액 × 낙찰하한율/100) − 1) × 100"
KNOWN_LAG_DAYS = 7


def _exp(bq):
    return f"`{bq.s.table('TABLE_EXPERIMENTS')}`"


def _status(e) -> str:
    return e.get("serving_status") or "없음"


def _admin(settings, what):
    if settings.role != "admin":
        raise PermissionError(f"관리자만 {what}할 수 있습니다 (관리자 설정 파일에 ROLE=admin 이 있어야 합니다)")


def request_serving(bq, exp_id: str, user: str, reason: str) -> None:
    st = _status(get_experiment(bq, exp_id))
    if st not in ("없음", "반려"):
        raise ValueError(f"실험 '{exp_id}'은(는) 이미 서빙 상태가 '{st}'입니다. 새로 요청할 수 없습니다")
    bq.execute(f"""UPDATE {_exp(bq)} SET serving_status = '요청', requested_by = @by, requested_at = CURRENT_TIMESTAMP(),
request_reason = @reason WHERE experiment_id = @id""", {"id": exp_id, "by": user, "reason": reason}, perm=Permission.LAB)


def reject(bq, exp_id: str, approver: str, note: str) -> None:
    _admin(bq.s, "서빙 요청을 반려")
    st = _status(get_experiment(bq, exp_id))
    if st != "요청":
        raise ValueError(f"실험 '{exp_id}'은(는) 서빙 요청 상태가 아닙니다 (지금 '{st}')")
    bq.execute(f"""UPDATE {_exp(bq)} SET serving_status = '반려', decided_by = @by, decided_at = CURRENT_TIMESTAMP(),
decision_note = @note WHERE experiment_id = @id AND serving_status = '요청'""",
               {"id": exp_id, "by": approver, "note": note}, perm=Permission.LAB)


# ── GCS ────────────────────────────────────────────────
def _name(settings, *parts):
    return "/".join([settings.gcs_prefix.strip("/"), *parts])


def _read_json(gcs, name):
    """(내용, 세대) — 없으면 (None, 0)."""
    b = gcs.get_blob(name)
    return (None, 0) if b is None else (json.loads(b.download_as_bytes()), b.generation)


def _put(gcs, name, data, gen, content_type="application/json"):
    gcs.blob(name).upload_from_string(data, content_type=content_type, if_generation_match=gen)


def _write_serving(gcs, settings, version, user, previous, gen):
    body = {"version": version, "updated_at": _now(), "updated_by": user, "previous": previous}
    try:
        _put(gcs, _name(settings, "serving.json"), json.dumps(body, ensure_ascii=False), gen)
    except PreconditionFailed:
        raise RuntimeError("다른 관리자가 먼저 바꿨습니다. 서빙 상태를 다시 확인하세요 (지금 서빙은 바뀌지 않았습니다)") from None


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _upload_model(gcs, settings, data: bytes) -> str:
    """다음 vNN 폴더에 model.joblib 을 새로 만든다. 그사이 누가 그 번호를 쓰면 다음 번호로."""
    pat = re.compile(re.escape(_name(settings, "")) + r"v(\d+)/")
    n = max([int(m.group(1)) for b in gcs.list_blobs(prefix=_name(settings, "")) if (m := pat.match(b.name))],
            default=0)
    for _ in range(5):
        n += 1
        v = f"v{n:02d}"
        try:
            _put(gcs, _name(settings, v, "model.joblib"), data, 0, "application/octet-stream")
            return v
        except PreconditionFailed:
            continue
    raise RuntimeError("새 버전 번호를 정하지 못했습니다. 잠시 뒤 다시 승인하세요")


# ── 승인·되돌리기 ──────────────────────────────────────
def _frozen_features(bq, e) -> list[FeatureDef]:
    """SQL은 실험 때 기록한 그대로, 종류·설명은 등록표에서. 등록표가 '검사통과'이고 SQL이 같을 때만."""
    fs = e["feature_sql"]
    fs = json.loads(fs) if isinstance(fs, str) else dict(fs)
    names = list(e["features"])
    reg = bq.query_df(f"SELECT name, kind, sql, description, status FROM `{bq.s.table('TABLE_FEATURES')}` "
                      "WHERE name IN UNNEST(@names)", {"names": names}).set_index("name")
    out = []
    for name in names:
        if name not in reg.index:
            raise ValueError(f"feature '{name}'이(가) 등록표에 없습니다")
        r = reg.loc[name]
        if r["status"] != "검사통과":
            raise ValueError(f"feature '{name}'의 상태가 '{r['status']}'입니다. 검사를 통과한 feature만 서빙할 수 있습니다")
        if r["sql"] != fs[name]:
            raise ValueError(f"feature '{name}': feature SQL이 실험 이후 바뀌었습니다 — 실험을 다시 실행해 주세요")
        out.append(FeatureDef(name, r["kind"], fs[name], r["description"] or ""))
    return out


def approve(bq, gcs, settings, exp_id: str, approver: str, self_approve: bool = False, progress=print) -> str:
    _admin(settings, "서빙을 승인")
    e = get_experiment(bq, exp_id)
    if _status(e) != "요청":
        raise ValueError(f"실험 '{exp_id}'은(는) 서빙 요청 상태가 아닙니다 (지금 '{_status(e)}')")
    if e.get("requested_by") == approver and not self_approve:
        raise ValueError("요청자와 승인자가 같습니다. 다른 관리자가 승인하는 것이 원칙입니다. "
                         "관리자가 혼자라면 --self-approve 를 붙여 다시 실행하세요")
    current, gen = _read_json(gcs, _name(settings, "serving.json"))
    feats = _frozen_features(bq, e)
    names = [f.name for f in feats]

    progress(f"전체 기간 데이터로 다시 학습합니다 (feature {len(feats)}개, 몇 분 걸릴 수 있습니다)")
    df = run_features(bq, [_Y, _DAY, *feats], TARGETS_TRAIN)
    model = FeatureMaskedModel(names, [f.name for f in feats if f.kind == "범주"])
    model.fit(df[names].reset_index(drop=True), df["_y"].to_numpy())
    model.calibration = float(e["calibration"])
    buf = io.BytesIO()
    joblib.dump(model, buf)

    v = _upload_model(gcs, settings, buf.getvalue())
    manifest = {
        "version": v, "created_at": _now(), "experiment_id": exp_id, "requested_by": e.get("requested_by"),
        "approved_by": approver, "train_end": str(pd.to_datetime(df["_개찰일"]).max().date()),
        "metrics": {"hit01": float(e["hit01"]), "hit01_se": float(e["hit01_se"]), "hit10": float(e["hit10"]),
                    "calibration": float(e["calibration"]), "n_eval": int(e["n_eval"]),
                    "eval_version": e["eval_version"]},
        "known_lag_days": KNOWN_LAG_DAYS, "target": {"name": "y", "formula": FORMULA},
        "features": [{"name": f.name, "kind": f.kind, "description": f.description, "sql": f.sql} for f in feats],
        "categories": {c: [str(x) for x in vals] for c, vals in model.categories.items()},
        # 모델 파일은 ipchal_lab 클래스로 저장되므로 읽을 패키지 버전과 기준 뷰 SQL을 함께 남긴다
        "model_base_sha256": hashlib.sha256(
            (Path(__file__).parent / "sql" / "model_base.sql").read_text(encoding="utf-8").replace("\r\n", "\n").encode()).hexdigest(),
        "libs": {"python": platform.python_version(),
                 **{k: _libver(k) for k in ("ipchal-lab", "lightgbm", "scikit-learn", "pandas", "numpy")}},
    }
    _put(gcs, _name(settings, v, "manifest.json"), json.dumps(manifest, ensure_ascii=False, indent=1), 0)
    _write_serving(gcs, settings, v, approver, current and current.get("version"), gen)
    replace_prod(bq, feats, v)
    n = bq.execute(f"""UPDATE {_exp(bq)} SET serving_status = '승인', decided_by = @by, decided_at = CURRENT_TIMESTAMP(),
model_version = @mv WHERE experiment_id = @id AND serving_status = '요청'""",
                   {"id": exp_id, "by": approver, "mv": v}, perm=Permission.LAB)
    if n == 0:
        progress(f"주의: 서빙은 이제 {v}입니다. 그런데 학습하는 동안 실험 '{exp_id}'의 요청 상태가 바뀌어 "
                 "'승인'으로 기록하지 못했습니다. 실험 상태를 확인하세요")
    return v


def rollback(bq, gcs, settings, version: str, user: str) -> None:
    _admin(settings, "되돌리기를")
    if not re.fullmatch(r"v\d{2,}", version or ""):
        raise ValueError(f"버전 이름 '{version}'이(가) 올바르지 않습니다. v01 처럼 v와 두 자리 이상 숫자로 쓰세요")
    served = bq.query_df(f"SELECT COUNT(*) AS n FROM `{bq.s.table('TABLE_FEATURES_PROD')}` WHERE model_version = @v",
                         {"v": version})["n"].iloc[0]
    if not served:
        raise ValueError(f"버전 '{version}'은(는) 서빙된 적이 없습니다. 서빙했던 버전으로만 되돌릴 수 있습니다")
    manifest, _ = _read_json(gcs, _name(settings, version, "manifest.json"))
    if manifest is None:
        raise ValueError(f"버전 '{version}'이(가) 없습니다. 서빙 상태에서 버전 이름을 확인하세요")
    current, gen = _read_json(gcs, _name(settings, "serving.json"))
    _write_serving(gcs, settings, version, user, current and current.get("version"), gen)
    replace_prod(bq, [FeatureDef(f["name"], f["kind"], f["sql"], f.get("description", "")) for f in manifest["features"]],
                 version)


def current_manifest(gcs, settings) -> dict | None:
    sj, _ = _read_json(gcs, _name(settings, "serving.json"))
    return None if sj is None else _read_json(gcs, _name(settings, sj["version"], "manifest.json"))[0]


def serving_status(gcs, settings) -> dict:
    sj, _ = _read_json(gcs, _name(settings, "serving.json"))
    if sj is None:
        return {}
    m = _read_json(gcs, _name(settings, sj["version"], "manifest.json"))[0] or {}
    return {**sj, "experiment_id": m.get("experiment_id"), "approved_by": m.get("approved_by"),
            "train_end": m.get("train_end"), "metrics": m.get("metrics"),
            "features": [f["name"] for f in m.get("features", [])]}
