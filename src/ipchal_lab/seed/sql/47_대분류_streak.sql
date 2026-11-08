-- 대분류_streak: 같은 대분류 공고의 양(+)/음(-) 연속 길이 (+3 = 3건 연속 양수) (개찰 7일 전까지 결과)
WITH
h AS (
  SELECT pubPrcrmntLrgClsfcNm AS g, `개찰일시` AS ts, LEAST(GREATEST(y, -3.5), 6) AS v,
         ROW_NUMBER() OVER (PARTITION BY pubPrcrmntLrgClsfcNm ORDER BY `개찰일시`, `공고번호`, `차수`) - 1 AS rn
  FROM base WHERE y IS NOT NULL AND `학습범위_업종` AND `개찰일시` IS NOT NULL AND pubPrcrmntLrgClsfcNm IS NOT NULL),
hz AS (
  SELECT *, CAST(SIGN(v) AS INT64) AS sg,
         rn - ROW_NUMBER() OVER (PARTITION BY g, CAST(SIGN(v) AS INT64) ORDER BY rn) AS isl
  FROM h),
hs AS (SELECT *, sg * ROW_NUMBER() OVER (PARTITION BY g, sg, isl ORDER BY rn) AS streak FROM hz),
s AS (SELECT g, rn, streak AS streak FROM hs),
q AS (  -- 공고마다 t − lag일 전에 마지막으로 보이는 H 순번 (같은 시각의 H 는 종류 1 이라 공고 뒤 → 안 보임)
  SELECT pno, pord, g, MAX(IF(lag = 7, m, NULL)) AS m
  FROM (
    SELECT pno, pord, g, lag, k,
           LAST_VALUE(rn IGNORE NULLS) OVER (PARTITION BY g ORDER BY ts, k, rn ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS m
    FROM (
      SELECT `공고번호` AS pno, `차수` AS pord, pubPrcrmntLrgClsfcNm AS g, lag, DATETIME_SUB(`개찰일시`, INTERVAL lag DAY) AS ts,
             0 AS k, CAST(NULL AS INT64) AS rn
      FROM targets, UNNEST([7]) AS lag WHERE pubPrcrmntLrgClsfcNm IS NOT NULL AND `개찰일시` IS NOT NULL
      UNION ALL
      SELECT NULL, NULL, g, NULL, ts, 1, rn FROM h))
  WHERE k = 0
  GROUP BY pno, pord, g)
SELECT t.`공고번호`, t.`차수`, s.streak AS value
FROM targets t LEFT JOIN q ON q.pno = t.`공고번호` AND q.pord = t.`차수`
LEFT JOIN s ON s.g = q.g AND s.rn = q.m
