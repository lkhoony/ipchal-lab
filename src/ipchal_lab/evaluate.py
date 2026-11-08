"""표준 평가 E1: 마지막 결과가 있는 달까지 12개월로 평가, 그 이전 전부로 학습. 비교 대상(경험 분포, 현재 서빙)도 같은 나눔."""
from __future__ import annotations

import calendar
import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from .model import NB, FeatureMaskedModel, empirical, hit_top5
from .runner import TARGETS_TRAIN, FeatureDef, run_features

EVAL_VERSION = "E1"
_Y = FeatureDef("_y", "숫자", "SELECT `공고번호`, `차수`, y AS value FROM targets")
_DAY = FeatureDef("_개찰일", "범주", "SELECT `공고번호`, `차수`, CAST(DATE(`개찰일시`) AS STRING) AS value FROM targets")


@dataclass(frozen=True)
class Split:
    train_end: date
    eval_start: date
    eval_end: date


@dataclass
class EvalResult:
    n_eval: int
    hit01: float
    hit01_se: float
    hit10: float
    calibration: float
    baseline_emp_hit01: float
    baseline_serving_hit01: float | None
    split: Split


def split_dates(last_result: date) -> Split:
    end = last_result.replace(day=calendar.monthrange(last_result.year, last_result.month)[1])
    start = date(end.year, 1, 1) if end.month == 12 else date(end.year - 1, end.month + 1, 1)
    return Split(date.fromordinal(start.toordinal() - 1), start, end)


def hit_se(p: float, n: int) -> float:
    return math.sqrt(p * (1 - p) / n)


def calibration(p: np.ndarray, y: np.ndarray) -> float:
    """평가 적중률 ÷ 모델이 말한 top-5 확률합의 평균."""
    top = np.argpartition(-p, 5, axis=1)[:, :5]
    return float(hit_top5(p, y).mean() / np.take_along_axis(p, top, 1).sum(1).mean())


def emp_hits(ytr, yev) -> np.ndarray:
    """학습 기간 y의 경험 분포 하나로 모든 평가 공고를 맞힌 결과."""
    return hit_top5(np.tile(empirical(ytr), (len(yev), 1)), np.asarray(yev, dtype=float))


def _fit_predict(features, df, tr, ev):
    names = [f.name for f in features]
    m = FeatureMaskedModel(names, [f.name for f in features if f.kind == "범주"])
    m.fit(df.loc[tr, names].reset_index(drop=True), df.loc[tr, "_y"].to_numpy())
    return m.predict_proba(df.loc[ev, names].reset_index(drop=True))


def evaluate_features(bq, features: list[FeatureDef], progress=print, serving_features: list[FeatureDef] | None = None,
                      base_override: str | None = None) -> EvalResult:
    # 서빙 feature가 실험 feature와 이름은 같은데 SQL이 다르면 따로 받는다
    mine = {f.name: f for f in features}
    serving = None if serving_features is None else [
        f if mine.get(f.name, f).sql == f.sql else FeatureDef(f"서빙__{f.name}", f.kind, f.sql) for f in serving_features]
    fetch = {f.name: f for f in [_Y, _DAY, *features, *(serving or [])]}
    progress(f"데이터 받는 중 (feature {len(fetch) - 2}개, 한 번만 받습니다)")
    df = run_features(bq, list(fetch.values()), TARGETS_TRAIN, base_override=base_override)
    day = pd.to_datetime(df["_개찰일"]).dt.date
    split = split_dates(day.max())
    tr, ev = (day <= split.train_end).to_numpy(), ((day >= split.eval_start) & (day <= split.eval_end)).to_numpy()
    yev = df.loc[ev, "_y"].to_numpy()
    progress(f"학습 중: {split.train_end}까지 {tr.sum():,}건으로 학습합니다 (몇 분 걸릴 수 있습니다)")
    p = _fit_predict(features, df, tr, ev)
    serving_hit = None
    if serving:
        progress("학습 중: 현재 서빙 feature로 같은 방식 학습")
        serving_hit = float(hit_top5(_fit_predict(serving, df, tr, ev), yev).mean())
    progress(f"평가 중: {split.eval_start} ~ {split.eval_end} 공고 {ev.sum():,}건")
    h = float(hit_top5(p, yev).mean())
    return EvalResult(int(ev.sum()), h, hit_se(h, int(ev.sum())), float(hit_top5(p, yev, 0.1).mean()),
                      calibration(p, yev), float(emp_hits(df.loc[tr, "_y"].to_numpy(), yev).mean()), serving_hit, split)


def format_comparison(r: EvalResult) -> str:
    pct = lambda v: "—" if v is None else f"{v * 100:.2f}%"  # noqa: E731
    se = lambda v: "" if v is None else f" ± {hit_se(v, r.n_eval) * 100:.2f}"  # noqa: E731
    s = r.split
    lines = [
        f"평가 {EVAL_VERSION}: 학습 ~{s.train_end}, 평가 {s.eval_start} ~ {s.eval_end}, 평가 공고 {r.n_eval:,}건",
        "",
        "| 비교 | 0.01 적중률 ± 표준오차 | 0.1 적중률 |",
        "|---|---|---|",
        f"| 실험 | {pct(r.hit01)} ± {r.hit01_se * 100:.2f} | {pct(r.hit10)} |",
        f"| 경험 분포 | {pct(r.baseline_emp_hit01)}{se(r.baseline_emp_hit01)} | |",
        f"| 현재 서빙 | {pct(r.baseline_serving_hit01)}{se(r.baseline_serving_hit01)} | |",
        "",
        f"확률 보정 계수 {r.calibration:.3f} (실제 적중률 ÷ 모델이 말한 확률. 1보다 작으면 모델이 자신을 과대평가)",
        "",
        "용어:",
        "- 0.01 적중률: 0.01%p 단위 구간 중 확률이 가장 높은 5개 안에 실제 결과가 들어간 공고의 비율",
        "- 0.1 적중률: 같은 방식을 0.1%p 단위 구간으로 잰 값",
        "- 표준오차(±): 평가 공고 수가 한정되어 생기는 흔들림의 크기",
        "- 경험 분포: feature 없이 학습 기간 결과가 자주 나온 구간 5개를 그대로 고르는 기준",
        "- 현재 서빙: 지금 쓰는 모델의 feature로 같은 기간 학습·평가한 결과",
        "",
        "차이가 표준오차 2배보다 작으면 우연 범위일 수 있음",
    ]
    return "\n".join(lines)
