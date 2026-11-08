"""체크한 feature만으로 0.01 구간 확률을 내는 마스킹 학습 모델 (레거시 predictor.py와 같은 계산, feature 목록만 인스턴스가 가짐)."""

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.model_selection import GroupKFold, cross_val_predict

W, LO, HI = 0.01, -350, 800  # 0.01 구간 번호 범위: y ∈ [-3.50, 8.00)
NB = HI - LO
EDGES = np.arange(LO, HI + 1) * W
LGB_PARAMS = dict(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=200,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1)

# ── 모델 ────────────────────────────────────────────────
def _bin(y):
    return np.floor(np.round(np.asarray(y) / W, 6)).astype(np.int64) - LO


def empirical(y) -> np.ndarray:
    """0.01 구간별 빈도 (전체 경험 분포, 분모는 범위 밖 포함 전체 건수)."""
    b = _bin(y)
    return np.bincount(b[(b >= 0) & (b < NB)], minlength=NB) / len(b)


def _kde_cdf(z):
    # ponytail: 표본 5천 개로 근사, Silverman 대역폭의 절반 (봉우리 보존)
    zs = np.random.default_rng(0).choice(z, size=min(5000, len(z)), replace=False)
    h = 1.06 * zs.std() * len(zs) ** -0.2 * 0.5
    grid = np.linspace(-15, 15, 6001)
    return grid, np.concatenate([norm.cdf((grid[i:i + 500, None] - zs) / h).mean(1) for i in range(0, len(grid), 500)])


def _ls(mu, sd, grid, cdf):
    return np.diff(np.interp((EDGES[None, :] - mu[:, None]) / sd[:, None], grid, cdf), axis=1)


class FeatureMaskedModel:
    def __init__(self, features: list[str], cats: list[str], copies: int = 4, seed: int = 0):
        self.features, self.cats, self.copies, self.seed = list(features), list(cats), copies, seed
        self.calibration = 1.0  # 화면 확률 = 모델 확률 × calibration (평가 기간 실제 적중률 ÷ 모델이 말한 확률)

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "FeatureMaskedModel":
        y = np.asarray(y, dtype=float)
        self.emp = empirical(y)
        keep = (y > -3.5) & (y < 8)  # 분포 모델은 범위 안 공고로 (긴 꼬리가 폭 모델을 흔들지 않게)
        X, y = X[keep].reset_index(drop=True), y[keep]
        self.categories = {c: sorted(X[c].dropna().unique()) for c in self.cats}
        X = self._prep(X)
        rng = np.random.default_rng(self.seed)
        # 행마다 가리는 비율 q ~ U(0, 1), feature마다 확률 q로 가림
        parts = []
        for _ in range(self.copies):
            q = rng.random((len(X), 1))
            parts.append(self._mask(X, rng.random((len(X), len(self.features))) >= q))
        Xa = pd.concat(parts, ignore_index=True)
        ya = np.tile(y, self.copies)
        cv = list(GroupKFold(5).split(Xa, ya, np.tile(np.arange(len(y)), self.copies)))  # 같은 공고 사본은 같은 fold
        # lightgbm은 학습할 때만 불러온다: 로드에 실패해도 setup·login·doctor는 동작하게.
        # Windows에서는 위의 sklearn import가 먼저 OpenMP DLL(vcomp140)을 올려 둔다.
        import lightgbm as lgb
        self.mu_model = lgb.LGBMRegressor(**LGB_PARAMS).fit(Xa, ya)
        mu = cross_val_predict(lgb.LGBMRegressor(**LGB_PARAMS), Xa, ya, cv=cv)
        r = np.abs(ya - mu)
        self.sd_model = lgb.LGBMRegressor(**LGB_PARAMS).fit(Xa, r)
        sd = np.clip(cross_val_predict(lgb.LGBMRegressor(**LGB_PARAMS), Xa, r, cv=cv), 0.05, None)
        self.grid, self.cdf = _kde_cdf((ya - mu) / sd)
        m0, s0 = y.mean(), np.abs(y - y.mean()).mean()
        self.p0 = _ls(np.array([m0]), np.array([s0]), *_kde_cdf((y - m0) / s0))[0]  # 조건 없는 매끈한 분포
        return self

    def _prep(self, X):
        X = X[self.features].copy()
        for c in self.cats:
            v = X[c].astype(object)
            X[c] = pd.Categorical(v.where(v.isin(self.categories[c])), categories=self.categories[c])  # 처음 보는 값은 NaN
        return X

    def _mask(self, X, keep):
        X = X.copy()
        for j, c in enumerate(self.features):
            X.loc[~keep[:, j], c] = np.nan
        return X

    def predict_proba(self, X: pd.DataFrame, checked: list[str] | None = None) -> np.ndarray:
        """(n, NB) 0.01 구간 확률 (합 1, 보정 전). checked=None이면 전부 체크, []이면 모든 공고가 같은 답 (전체 경험 분포에 가까움)."""
        checked = self.features if checked is None else checked
        unknown = set(checked) - set(self.features)
        if unknown:
            raise ValueError(f"없는 feature: {sorted(unknown)}")
        X = self._prep(X)
        X = self._mask(X, np.tile([c in checked for c in self.features], (len(X), 1)))
        mu, sd = self.mu_model.predict(X), np.clip(self.sd_model.predict(X), 0.05, None)
        p = self.emp[None, :] * np.clip(_ls(mu, sd, self.grid, self.cdf) / np.clip(self.p0, 1e-12, None), 1 / 3, 3)
        return p / p.sum(1, keepdims=True)

    def report(self, p: np.ndarray, 기초금액: float, 하한율: float) -> dict:
        """한 공고의 확률 벡터 → B안 화면에 쓸 값. 투찰 금액 = 기초금액 × 하한율 × (1 + y/100), 1원 미만 절사."""
        base = 기초금액 * 하한율 / 100
        won = lambda y: int(np.floor(base * (1 + y / 100) + 1e-6))  # noqa: E731

        def top(prob, w):
            out = []
            for i in np.argsort(-prob)[:5]:
                lo = float(round((i * round(w / W) + LO) * W, 2))
                out.append({"구간": (lo, round(lo + w, 2)), "투찰금액": (won(lo), won(lo + w) - 1),
                            "확률%": round(float(prob[i]) * 100 * self.calibration, 2)})
            return out

        cdf = np.cumsum(p)
        q = lambda a: round(float(EDGES[np.searchsorted(cdf, a)]), 2)  # noqa: E731
        return {"기준하한가": won(0), "중심": (q(0.5), won(q(0.5))), "절반범위": ((q(0.25), q(0.75)),
                                                                        (won(q(0.25)), won(q(0.75)))),
                "top5_0.1": top(p.reshape(NB // 10, 10).sum(1), 0.1), "top5_0.01": top(p, W)}


def hit_top5(p: np.ndarray, y: np.ndarray, width: float = 0.01) -> np.ndarray:
    """공고별 확률 p (n, NB)의 상위 5개 구간(width 0.01 또는 0.1)에 실제 y가 들어 있는지. 범위 밖 y는 False."""
    tb = _bin(y)
    inr = (tb >= 0) & (tb < NB)
    if width == 0.1:
        p, tb = p.reshape(len(p), NB // 10, 10).sum(2), tb // 10
    top = np.argpartition(-p, 5, axis=1)[:, :5]
    return (top == tb[:, None]).any(1) & inr
