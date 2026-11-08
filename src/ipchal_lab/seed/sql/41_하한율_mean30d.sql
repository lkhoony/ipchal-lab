-- 하한율_mean30d: 같은 낙찰하한율 공고의 최근 30일 평균 (개찰 7일 전까지 결과)
WITH
h AS (
  SELECT CAST(`낙찰하한율` AS STRING) AS g, `개찰일시` AS ts, LEAST(GREATEST(y, -3.5), 6) AS v,
         ROW_NUMBER() OVER (PARTITION BY CAST(`낙찰하한율` AS STRING) ORDER BY `개찰일시`, `공고번호`, `차수`) - 1 AS rn
  FROM base WHERE y IS NOT NULL AND `학습범위_업종` AND `개찰일시` IS NOT NULL AND CAST(`낙찰하한율` AS STRING) IS NOT NULL),
s AS (SELECT g, rn, SUM(v) OVER (PARTITION BY g ORDER BY rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cs FROM h),
q AS (  -- 공고마다 t − lag일 전에 마지막으로 보이는 H 순번 (같은 시각의 H 는 종류 1 이라 공고 뒤 → 안 보임)
  SELECT pno, pord, g, MAX(IF(lag = 7, m, NULL)) AS m, MAX(IF(lag = 37, m, NULL)) AS m30
  FROM (
    SELECT pno, pord, g, lag, k,
           LAST_VALUE(rn IGNORE NULLS) OVER (PARTITION BY g ORDER BY ts, k, rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS m
    FROM (
      SELECT `공고번호` AS pno, `차수` AS pord, CAST(`낙찰하한율` AS STRING) AS g, lag, DATETIME_SUB(`개찰일시`, INTERVAL lag DAY) AS ts,
             0 AS k, CAST(NULL AS INT64) AS rn
      FROM targets, UNNEST([7, 37]) AS lag WHERE CAST(`낙찰하한율` AS STRING) IS NOT NULL AND `개찰일시` IS NOT NULL
      UNION ALL
      SELECT NULL, NULL, g, NULL, ts, 1, rn FROM h))
  WHERE k = 0
  GROUP BY pno, pord, g)
SELECT t.`공고번호`, t.`차수`, SAFE_DIVIDE(s.cs - IFNULL(s30.cs, 0), q.m - IFNULL(q.m30, -1)) AS value
FROM targets t LEFT JOIN q ON q.pno = t.`공고번호` AND q.pord = t.`차수`
LEFT JOIN s ON s.g = q.g AND s.rn = q.m
LEFT JOIN s AS s30 ON s30.g = q.g AND s30.rn = q.m30
