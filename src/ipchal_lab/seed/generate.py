"""기존 67개 feature(ingest-bids predictor.py)를 BigQuery SQL 파일로 만든다. 실행: uv run python -m ipchal_lab.seed.generate

주식식 통계 규칙 (레거시 series_stats 와 같음):
- 과거 결과 H = base 에서 y 있고 학습범위_업종 인 행, 값 v = y 를 [-3.5, 6] 로 자른 값, 순서 (개찰일시, 공고번호, 차수).
  그룹 키가 NULL 인 행은 H 에서 빼고, 키가 NULL 인 공고는 값이 NULL.
- 공고(개찰일시 t)에서 보이는 과거 = 개찰일시 < t − 7일. 최근 N건 통계는 보이는 것 중 마지막 N건.
- 계산 방법: H 행마다 창 함수로 통계를 미리 구하고, H 행(시각, 종류 1)과 공고(t − 7일, 종류 0)를 한 시간축에 놓고
  LAST_VALUE(순번 IGNORE NULLS)로 공고마다 마지막으로 보이는 H 순번 m 을 찾아 그 행의 통계를 붙인다.
"""
from __future__ import annotations

from pathlib import Path

SQL_DIR = Path(__file__).parent / "sql"
LAG = 7

STATIC = {  # 이름: (SQL 식, 설명)
    "log_기초금액": ("`log_기초금액`", "기초금액의 log10"),
    "낙찰하한율": ("`낙찰하한율`", "낙찰하한율 (87.745, 88, 90 등)"),
    "차수_n": ("SAFE_CAST(`차수` AS INT64)", "공고 차수 (재공고면 1 이상)"),
    "업종수": ("`업종수`", "투찰 가능 업종 수"),
    "지역수": ("`지역수`", "참가 가능 지역 수"),
    "시군구있음": ("`시군구있음`", "시군구까지 지역을 제한했는지 (1/0)"),
    "연도": ("EXTRACT(YEAR FROM `개찰일시`)", "개찰 연도"),
    "월": ("EXTRACT(MONTH FROM `개찰일시`)", "개찰 월"),
    "요일": ("MOD(EXTRACT(DAYOFWEEK FROM `개찰일시`) + 5, 7)", "개찰 요일 (0=월)"),
    "시각": ("EXTRACT(HOUR FROM `개찰일시`)", "개찰 시각 (시)"),
    "pubPrcrmntLrgClsfcNm": ("pubPrcrmntLrgClsfcNm", "대분류 (예: 기술용역)"),
    "pubPrcrmntMidClsfcNm": ("pubPrcrmntMidClsfcNm", "중분류"),
    "pubPrcrmntClsfcNm": ("pubPrcrmntClsfcNm", "세부분류 (예: 소방설계용역)"),
    "시도": ("`시도`", "참가 가능 지역 첫 번째의 시도"),
    "업종_정리": ("`업종_정리`", "투찰 가능 업종 조합 (반복 제거 후 정렬)"),
}
CATS = ["pubPrcrmntLrgClsfcNm", "pubPrcrmntMidClsfcNm", "pubPrcrmntClsfcNm", "시도", "업종_정리"]
# 그룹 이름: (그룹 키 식, 설명). 실수 키는 창 함수 PARTITION BY 에 못 써서 문자열로 바꾼다
GROUPS = {"전체": ("'전체'", "전체 공고"), "하한율": ("CAST(`낙찰하한율` AS STRING)", "같은 낙찰하한율 공고"),
          "대분류": ("pubPrcrmntLrgClsfcNm", "같은 대분류 공고"), "시도": ("`시도`", "같은 시도 공고"),
          "세부분류": ("pubPrcrmntClsfcNm", "같은 세부분류 공고")}
STAT_DESC = {
    "sma20": "최근 20건 단순 이동평균", "sma60": "최근 60건 단순 이동평균", "sma250": "최근 250건 단순 이동평균",
    "std20": "최근 20건 표준편차", "std60": "최근 60건 표준편차", "std250": "최근 250건 표준편차",
    "slope20": "최근 20건 추세선 기울기 (20건 동안 변화량)", "slope60": "최근 60건 추세선 기울기 (60건 동안 변화량)",
    "slope250": "최근 250건 추세선 기울기 (250건 동안 변화량)",
    "pos20": "최근 20건 중 양수 비율", "pos60": "최근 60건 중 양수 비율", "pos250": "최근 250건 중 양수 비율",
    "ema20": "지수 이동평균 (span 20)", "ema100": "지수 이동평균 (span 100)", "macd": "ema20 - ema100",
    "boll_b": "볼린저 위치 = (ema20 - sma60) / (2 × std60)", "streak": "양(+)/음(-) 연속 길이 (+3 = 3건 연속 양수)",
    "last": "직전 공고 값", "mean30d": "최근 30일 평균",
}
GROUP_STATS = ("sma20", "sma60", "ema20", "std60", "slope60", "streak", "pos60", "mean30d")
EMA_K = {20: 220, 100: 1100}  # 최근 K건만 합산 (잘린 무게 r^K < 1e-9)

H_WHERE = "y IS NOT NULL AND `학습범위_업종` AND `개찰일시` IS NOT NULL"


def _row_stat(stat: str) -> str:
    """H 행마다 계산하는 통계 (창 wN = 그 행까지 최근 N건)."""
    for p in ("sma", "std", "slope", "pos"):
        if stat.startswith(p):
            n = int(stat[len(p):])
            w = f"(PARTITION BY g ORDER BY rn ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW)"
            return {"sma": f"AVG(v) OVER {w}",
                    "std": f"STDDEV_POP(v) OVER {w}",
                    "pos": f"AVG(IF(v > 0, 1, 0)) OVER {w}",
                    # 기울기 = 공분산(순번, v) / 분산(순번) × N, 연속 순번 c건의 분산 = (c²−1)/12
                    "slope": f"SAFE_DIVIDE(COVAR_POP(rn, v) OVER {w}, (POW(COUNT(*) OVER {w}, 2) - 1) / 12) * {n}"}[p]
    return {"last": "v", "streak": "streak",
            "cs": "SUM(v) OVER (PARTITION BY g ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)"}[stat]


def _ema(span: int) -> str:
    """adjust=False 지수 이동평균: 마지막 보이는 순번 m 에서 Σ w_i·v_i, w_0 = r^m, w_i = α·r^(m−i)."""
    a, k = f"2 / {span + 1}", EMA_K[span]
    return (f"e{span} AS (\n  SELECT q.pno, q.pord, SUM(POW(1 - {a}, q.m - h.rn) * IF(h.rn = 0, 1, {a}) * h.v) AS ema{span}\n"
            f"  FROM q JOIN h ON h.g = q.g AND h.rn BETWEEN q.m - {k - 1} AND q.m\n  GROUP BY q.pno, q.pord)")


def stat_sql(group: str, stat: str) -> str:
    g = GROUPS[group][0]
    rows = {"sma60", "std60"} if stat == "boll_b" else {"cs"} if stat == "mean30d" else set() if stat.startswith(("ema", "macd")) else {stat}
    spans = [20, 100] if stat == "macd" else [20] if stat == "boll_b" else [int(stat[3:])] if stat.startswith("ema") else []
    lags = [LAG, LAG + 30] if stat == "mean30d" else [LAG]
    value = {"macd": "e20.ema20 - e100.ema100", "boll_b": "SAFE_DIVIDE(e20.ema20 - s.sma60, 2 * s.std60)",
             "mean30d": "SAFE_DIVIDE(s.cs - IFNULL(s30.cs, 0), q.m - IFNULL(q.m30, -1))"}.get(
        stat, f"e{stat[3:]}.{stat}" if spans else f"s.{stat}")
    v = "LEAST(GREATEST(y, -3.5), 6)"
    ctes = [f"""h AS (
  SELECT {g} AS g, `개찰일시` AS ts, {v} AS v,
         ROW_NUMBER() OVER (PARTITION BY {g} ORDER BY `개찰일시`, `공고번호`, `차수`) - 1 AS rn
  FROM base WHERE {H_WHERE} AND {g} IS NOT NULL)"""]
    src = "h"
    if stat == "streak":  # 부호가 같은 연속 구간 길이 × 부호 (0 은 연속을 끊고 0)
        ctes.append("""hz AS (
  SELECT *, CAST(SIGN(v) AS INT64) AS sg,
         rn - ROW_NUMBER() OVER (PARTITION BY g, CAST(SIGN(v) AS INT64) ORDER BY rn) AS isl
  FROM h),
hs AS (SELECT *, sg * ROW_NUMBER() OVER (PARTITION BY g, sg, isl ORDER BY rn) AS streak FROM hz)""")
        src = "hs"
    if rows:
        cols = ", ".join(f"{_row_stat(r)} AS {r}" for r in sorted(rows))
        ctes.append(f"s AS (SELECT g, rn, {cols} FROM {src})")
    m30 = f", MAX(IF(lag = {LAG + 30}, m, NULL)) AS m30" if stat == "mean30d" else ""
    ctes.append(f"""q AS (  -- 공고마다 t − lag일 전에 마지막으로 보이는 H 순번 (같은 시각의 H 는 종류 1 이라 공고 뒤 → 안 보임)
  SELECT pno, pord, g, MAX(IF(lag = {LAG}, m, NULL)) AS m{m30}
  FROM (
    SELECT pno, pord, g, lag, k,
           LAST_VALUE(rn IGNORE NULLS) OVER (PARTITION BY g ORDER BY ts, k, rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS m
    FROM (
      SELECT `공고번호` AS pno, `차수` AS pord, {g} AS g, lag, DATETIME_SUB(`개찰일시`, INTERVAL lag DAY) AS ts,
             0 AS k, CAST(NULL AS INT64) AS rn
      FROM targets, UNNEST([{", ".join(map(str, lags))}]) AS lag WHERE {g} IS NOT NULL AND `개찰일시` IS NOT NULL
      UNION ALL
      SELECT NULL, NULL, g, NULL, ts, 1, rn FROM h))
  WHERE k = 0
  GROUP BY pno, pord, g)""")
    ctes += [_ema(s) for s in spans]
    joins = " LEFT JOIN q ON q.pno = t.`공고번호` AND q.pord = t.`차수`"
    if rows:
        joins += "\nLEFT JOIN s ON s.g = q.g AND s.rn = q.m"
    if stat == "mean30d":
        joins += "\nLEFT JOIN s AS s30 ON s30.g = q.g AND s30.rn = q.m30"
    joins += "".join(f"\nLEFT JOIN e{s} ON e{s}.pno = t.`공고번호` AND e{s}.pord = t.`차수`" for s in spans)
    return f"WITH\n{',\n'.join(ctes)}\nSELECT t.`공고번호`, t.`차수`, {value} AS value\nFROM targets t{joins}\n"


def prev_year_sql() -> str:
    return f"""WITH ym AS (
  SELECT EXTRACT(YEAR FROM `개찰일시`) AS yy, EXTRACT(MONTH FROM `개찰일시`) AS mm, AVG(LEAST(GREATEST(y, -3.5), 6)) AS v
  FROM base WHERE {H_WHERE}
  GROUP BY yy, mm)
SELECT t.`공고번호`, t.`차수`, ym.v AS value
FROM targets t LEFT JOIN ym ON ym.yy = EXTRACT(YEAR FROM t.`개찰일시`) - 1 AND ym.mm = EXTRACT(MONTH FROM t.`개찰일시`)
"""


def specs() -> list[tuple[str, str, str, str]]:
    """(이름, 종류, 설명, SQL) — 레거시 FEATURES 순서."""
    out = [(n, "범주" if n in CATS else "숫자", d, f"SELECT `공고번호`, `차수`, {e} AS value FROM targets\n")
           for n, (e, d) in STATIC.items()]
    for gname, stats in [("전체", list(STAT_DESC))] + [(g, GROUP_STATS) for g in GROUPS if g != "전체"]:
        out += [(f"{gname}_{s}", "숫자", f"{GROUPS[gname][1]}의 {STAT_DESC[s]} (개찰 7일 전까지 결과)", stat_sql(gname, s))
                for s in stats]
    out.append(("전년동월_평균", "숫자", "작년 같은 달 전체 공고 평균", prev_year_sql()))
    return out


def render() -> dict[str, str]:
    """{파일 이름: 내용}. 첫 줄 주석 `-- 이름: 설명`."""
    return {f"{i:02d}_{n}.sql": f"-- {n}: {d}\n{sql}" for i, (n, _, d, sql) in enumerate(specs())}


def main() -> None:
    SQL_DIR.mkdir(exist_ok=True)
    files = render()
    for p in SQL_DIR.glob("*.sql"):
        if p.name not in files:
            p.unlink()
    for name, text in files.items():
        with open(SQL_DIR / name, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    print(f"{len(files)}개 SQL 파일을 {SQL_DIR} 에 썼습니다")


if __name__ == "__main__":
    main()
