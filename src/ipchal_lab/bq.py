"""안전한 BigQuery 실행: 가드 -> dry-run -> 한도 비교 -> maximum_bytes_billed 지정."""
from __future__ import annotations

from datetime import date, datetime

import sqlglot
from google.cloud import bigquery

from .auth import get_credentials
from .config import Settings
from .guard import Permission, check_sql

MIN_BILLED = 10 * 1024**2


class TooExpensive(Exception):
    def __init__(self, nbytes: int, limit: int):
        self.bytes, self.limit = nbytes, limit
        super().__init__(f"약 {nbytes / 1024**3:.1f} GB를 읽습니다 (한도 {limit / 1024**3:.1f} GB). 실행하지 않았습니다. "
                         "정말 필요하면 한도를 직접 올려 다시 실행하세요")


class Bq:
    def __init__(self, settings: Settings, client: bigquery.Client | None = None):
        self.s, self._client = settings, client

    @property
    def client(self):
        if self._client is None:
            self._client = bigquery.Client(
                project=self.s.gcp_project, credentials=get_credentials(self.s, interactive=False),
                location=self.s.bq_location)
        return self._client

    def _config(self, params, **kw):
        if isinstance(params, dict):  # {이름: 값} -> 스칼라 파라미터 (list -> ARRAY<STRING>, datetime/date 외에는 STRING; 공고번호·차수는 문자열)
            params = [bigquery.ArrayQueryParameter(k, "STRING", [str(x) for x in v]) if isinstance(v, list)
                      else bigquery.ScalarQueryParameter(k, "DATETIME", v) if isinstance(v, datetime)
                      else bigquery.ScalarQueryParameter(k, "DATE", v) if isinstance(v, date)
                      else bigquery.ScalarQueryParameter(k, "STRING", None if v is None else str(v))
                      for k, v in params.items()]
        return bigquery.QueryJobConfig(query_parameters=params or [], **kw)

    def dry_run_bytes(self, sql: str, params=None) -> int:
        job = self.client.query(sql, job_config=self._config(params, dry_run=True, use_query_cache=False),
                                location=self.s.bq_location)
        return int(job.total_bytes_processed or 0)

    def _run(self, sql, params, perm, max_bytes):
        check_sql(sql, self.s, perm)
        limit = max_bytes if max_bytes is not None else self.s.max_bytes_per_query
        dry = self.dry_run_bytes(sql, params)
        if dry > limit:
            raise TooExpensive(dry, limit)
        # 여러 문장 스크립트(임시 표 사용)는 dry-run이 0바이트로 나와 추정이 불가능 -> 한도를 그대로 상한으로 쓴다
        # (maximum_bytes_billed 는 스크립트 전체 합계에 적용된다)
        multi = len([x for x in sqlglot.parse(sql, read="bigquery") if x is not None]) > 1
        billed = limit if multi else min(limit, max(int(dry * 1.2), MIN_BILLED))
        job = self.client.query(sql, job_config=self._config(params, maximum_bytes_billed=billed),
                                location=self.s.bq_location)
        res = job.result()
        self.last_bytes_billed = getattr(job, "total_bytes_billed", None)
        self.last_dml_rows = getattr(job, "num_dml_affected_rows", None)
        return res  # 여러 문장 스크립트는 마지막 문장의 결과

    def query_df(self, sql, params=None, perm=Permission.READ, max_bytes: int | None = None):
        return self._run(sql, params, perm, max_bytes).to_dataframe()

    def execute(self, sql, params=None, perm=Permission.READ, max_bytes: int | None = None) -> int | None:
        """바뀐 행 수 (DML일 때, 모르면 None)."""
        self._run(sql, params, perm, max_bytes)
        return self.last_dml_rows
