"""월 GCP 사용액 한도: 쿼리를 실행하기 전에 (이번 달 사용액 + 이번 쿼리 예상) 이 한도를 넘는지 본다.

이번 달 사용액 = BigQuery 조회 비용 (작업 기록 INFORMATION_SCHEMA.JOBS, 실시간)
              + 그 밖의 서비스 비용 (청구 내보내기 표, 몇 시간~하루 늦음. 설정했을 때만)
청구 내보내기에서는 BigQuery 조회(Analysis) 항목을 빼서 두 번 세지 않는다.
달의 경계는 Google 청구 기준(미국 태평양 시간)을 따른다.
"""
from __future__ import annotations

import sys

USD_PER_TIB = 6.25  # BigQuery 주문형 조회 단가 (서울 리전 포함, 2026-11 가격표)
FREE_TIB = 1.0      # 매달 처음 1 TiB 무료 (결제 계정 단위라 다른 프로젝트와 나눠 쓰면 실제 무료분은 더 적다)
TIB = 1024**4
_MONTH_START = "TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MONTH, 'America/Los_Angeles')"


class OverBudget(Exception):
    pass


def won(x: float) -> str:
    return f"{round(x):,}원"


class Budget:
    def __init__(self, settings, client, out=sys.stderr):
        self.s, self.client, self.out = settings, client, out
        self.month_bytes = None  # 이번 달 프로젝트 전체 조회 과금 바이트 (처음 확인할 때 한 번 읽음)
        self.other_krw = 0.0     # BigQuery 조회 외 서비스 비용
        self.other_note = ""
        self.used_bytes = 0      # 이 명령이 실행한 쿼리의 실제 과금 바이트

    def query_krw(self, nbytes: float) -> float:
        """이번 달 누적 조회량 nbytes 의 조회 비용 (무료 1 TiB 뺀 뒤)."""
        return max(0.0, nbytes / TIB - FREE_TIB) * USD_PER_TIB * self.s.krw_per_usd

    def _scalar(self, sql):
        rows = list(self.client.query(sql, location=self.s.bq_location).result())
        return rows[0][0] if rows and rows[0][0] is not None else 0

    def load(self):
        if self.month_bytes is not None:
            return
        loc = self.s.bq_location.lower()
        try:
            self.month_bytes = int(self._scalar(
                f"SELECT SUM(total_bytes_billed) FROM `{self.s.gcp_project}.region-{loc}`.INFORMATION_SCHEMA.JOBS_BY_PROJECT "
                f"WHERE creation_time >= {_MONTH_START} AND job_type = 'QUERY'"))
        except Exception as e:
            raise OverBudget("이번 달 GCP 사용액을 확인할 수 없어 실행하지 않았습니다. 담당자에게 이 계정에 "
                             f"'BigQuery 리소스 뷰어' 권한을 달라고 하세요 ({getattr(e, 'message', e)})") from None
        if not self.s.billing_export_table:
            self.other_note = "청구 내보내기 미설정: 저장·Cloud Run 등 다른 서비스 비용은 빠져 있음"
            return
        try:
            rows = list(self.client.query(f"""
SELECT currency, SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS krw, MAX(export_time) AS asof
FROM `{self.s.billing_export_table}`
WHERE invoice.month = FORMAT_TIMESTAMP('%Y%m', CURRENT_TIMESTAMP(), 'America/Los_Angeles')
  AND NOT (service.description = 'BigQuery' AND STARTS_WITH(sku.description, 'Analysis'))
GROUP BY currency""").result())
        except Exception as e:
            raise OverBudget(f"청구 내보내기 표를 읽을 수 없어 실행하지 않았습니다 ({getattr(e, 'message', e)})") from None
        for r in rows:
            if r["currency"] not in ("KRW", "USD"):
                raise OverBudget(f"청구 통화 {r['currency']}는 지원하지 않습니다 (KRW·USD만)")
            self.other_krw += float(r["krw"] or 0) * (self.s.krw_per_usd if r["currency"] == "USD" else 1)
        asof = max((r["asof"] for r in rows if r["asof"]), default=None)
        self.other_note = f"다른 서비스 비용은 {asof:%m-%d %H:%M} UTC 청구 기준" if asof else "다른 서비스 비용 기록 없음"

    def spent_krw(self, extra_bytes: int = 0) -> float:
        self.load()
        return self.other_krw + self.query_krw(self.month_bytes + self.used_bytes + extra_bytes)

    def check(self, nbytes: int) -> None:
        """nbytes 를 더 조회해도 한도 안인지. 처음 부를 때 이번 달 사용액을 한 줄로 알린다."""
        first = self.month_bytes is None
        now, after = self.spent_krw(), self.spent_krw(nbytes)
        limit = self.s.monthly_budget_krw
        if first:
            print(f"이번 달 GCP 사용액 약 {won(now)} / 한도 {won(limit)} (남은 금액 약 {won(max(0, limit - now))})",
                  file=self.out)
        if after > limit:
            raise OverBudget(f"월 한도를 넘어 실행하지 않았습니다: 이번 달 약 {won(now)} + 이번 조회 약 {won(after - now)} "
                             f"({nbytes / 1024**3:.1f} GB) > 한도 {won(limit)}")

    def add_used(self, nbytes: int | None) -> None:
        self.used_bytes += int(nbytes or 0)

    def summary(self) -> str:
        """이 명령이 쓴 양 (한 번이라도 조회했을 때만)."""
        if self.month_bytes is None or not self.used_bytes:
            return ""
        base = self.month_bytes
        return (f"이번 작업 조회 {self.used_bytes / 1024**3:.2f} GB, 약 "
                f"{won(self.query_krw(base + self.used_bytes) - self.query_krw(base))}")

    def report(self) -> str:
        """`ipchal cost` 출력."""
        self.load()
        q = self.query_krw(self.month_bytes)
        total, limit = self.other_krw + q, self.s.monthly_budget_krw
        return "\n".join([
            f"BigQuery 조회: 이번 달 {self.month_bytes / TIB:.3f} TiB (무료 {FREE_TIB:g} TiB) → 약 {won(q)}",
            f"다른 서비스: 약 {won(self.other_krw)} ({self.other_note})",
            f"합계 약 {won(total)} / 한도 {won(limit)} (남은 금액 약 {won(max(0, limit - total))})",
            f"환율 1달러 = {self.s.krw_per_usd:,.0f}원, 조회 단가 1 TiB = {USD_PER_TIB}달러로 계산했습니다",
        ])


if __name__ == "__main__":  # 자체 점검: python -m ipchal_lab.cost
    from types import SimpleNamespace as NS

    class _Fake:
        def __init__(self, nbytes):
            self.nbytes = nbytes

        def query(self, sql, location=None):
            return NS(result=lambda: [[self.nbytes]])

    s = NS(gcp_project="p", bq_location="asia-northeast3", billing_export_table="", krw_per_usd=1000.0,
           monthly_budget_krw=10_000)
    import io
    out = io.StringIO()
    b = Budget(s, _Fake(int(0.5 * TIB)), out)
    b.check(int(0.4 * TIB))                      # 0.9 TiB: 무료 안 → 0원
    assert "0원" in out.getvalue() and b.spent_krw() == 0
    b.add_used(int(0.6 * TIB))                   # 누적 1.1 TiB → 0.1 TiB 과금 = 625원
    assert round(b.spent_krw()) == 625, b.spent_krw()
    b.check(int(1.0 * TIB))                      # +1 TiB → 6,875원 ≤ 10,000원
    try:
        b.check(int(2.0 * TIB))                  # +2 TiB → 13,125원 > 10,000원
        raise AssertionError("한도를 넘었는데 막지 않았습니다")
    except OverBudget as e:
        assert "한도" in str(e)
    assert b.summary().startswith("이번 작업 조회 614.40 GB")
    print("ok")
