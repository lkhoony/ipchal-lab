-- 전년동월_평균: 작년 같은 달 전체 공고 평균
WITH ym AS (
  SELECT EXTRACT(YEAR FROM `개찰일시`) AS yy, EXTRACT(MONTH FROM `개찰일시`) AS mm, AVG(LEAST(GREATEST(y, -3.5), 6)) AS v
  FROM base WHERE y IS NOT NULL AND `학습범위_업종` AND `개찰일시` IS NOT NULL
  GROUP BY yy, mm)
SELECT t.`공고번호`, t.`차수`, ym.v AS value
FROM targets t LEFT JOIN ym ON ym.yy = EXTRACT(YEAR FROM t.`개찰일시`) - 1 AND ym.mm = EXTRACT(MONTH FROM t.`개찰일시`)
