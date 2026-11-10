-- 기준 뷰(VIEW_MODEL_BASE) 본문. 2026-11 최초 세팅 때 이 SELECT 로 뷰를 만들었다 (manifest 의 model_base_sha256 이 이 파일의 지문).
-- (공고번호, 차수)당 1행. 같은 키가 여러 수집일(ingest_date)에 있으면 최신 수집일 행을 쓴다 (수집일 NULL 은 가장 오래된 것으로 본다).
WITH
l AS (
  SELECT bidNtceNo, bidNtceOrd, bidNtceNm, ntceInsttNm, bidNtceDt, opengDt,
         SAFE_CAST(sucsfbidLwltRate AS FLOAT64) AS rate,
         pubPrcrmntLrgClsfcNm, pubPrcrmntMidClsfcNm, pubPrcrmntClsfcNo, pubPrcrmntClsfcNm
  FROM `{project}.{dataset}.{TABLE_BID_LIST}`
  QUALIFY ROW_NUMBER() OVER (PARTITION BY bidNtceNo, bidNtceOrd ORDER BY ingest_date DESC) = 1),
b AS (
  SELECT bidNtceNo, bidNtceOrd, SAFE_CAST(bssamt AS FLOAT64) AS bssamt,
         TRIM(rsrvtnPrceRngBgnRate) AS bgn, TRIM(rsrvtnPrceRngEndRate) AS endr
  FROM `{project}.{dataset}.{TABLE_BSIS_AMOUNT}`
  QUALIFY ROW_NUMBER() OVER (PARTITION BY bidNtceNo, bidNtceOrd ORDER BY ingest_date DESC) = 1),
o AS (
  SELECT bidNtceNo, bidNtceOrd, prtcptPsblRgnNm, bidprcPsblIndstrytyNm
  FROM `{project}.{dataset}.{TABLE_OPN_STD_BID}`
  QUALIFY ROW_NUMBER() OVER (PARTITION BY bidNtceNo, bidNtceOrd ORDER BY ingest_date DESC) = 1),
-- 결과: 개방표준 낙찰(투찰 업체마다 1행). 최신 수집일의 행들만 모은다.
-- 출처는 학습 샘플과 맞춰 보고 정했다 (2016~2021 샘플 38,982건 비교):
--   최종낙찰금액 = 개찰 1순위(opengRank='1') 행의 투찰금액 bidprcAmt -> 샘플과 100% 일치.
--     fnlSucsfAmt 는 1순위가 탈락해 다음 순위가 낙찰된 공고와 낙찰자 미확정 공고에서 달라 90.3% 만 일치.
--   예정가격 = 1순위 행의 rsrvtnPrce -> 99.9% (재입찰 행의 예정가격이 섞이지 않게 1순위 행만 본다).
--   참여업체수 = 같은 공고의 투찰 행 수 -> 100%. 과거 수집분은 같은 업체 행이 겹치거나 재입찰 행이 함께 있어
--     낙찰 현황의 prtcptCnum 보다 클 수 있다 (prtcptCnum 과 같은 공고 68%). 샘플로 학습한 기존 모델과 맞추려고 그대로 둔다.
--   1순위 행이 없으면(유찰·개찰 전) 결과 컬럼과 y 는 NULL.
r AS (
  SELECT bidNtceNo, bidNtceOrd,
         MAX(IF(opengRank = '1', NULLIF(SAFE_CAST(bidprcAmt AS FLOAT64), 0), NULL)) AS fnl,
         MAX(IF(opengRank = '1', NULLIF(SAFE_CAST(rsrvtnPrce AS FLOAT64), 0), NULL)) AS rsrv,
         COUNT(*) AS n
  FROM `{project}.{dataset}.{TABLE_OPN_STD_SCSBID}`
  GROUP BY bidNtceNo, bidNtceOrd, ingest_date
  QUALIFY ROW_NUMBER() OVER (PARTITION BY bidNtceNo, bidNtceOrd ORDER BY ingest_date DESC) = 1),
-- 대상 업종 이름: 대상 업종 코드 -> 업종 기준표 이름
tg AS (
  SELECT ARRAY_AGG(DISTINCT x.indstrytyNm) AS names
  FROM `{project}.{dataset}.{TABLE_TARGET_INDSTRYTY}` t
  JOIN `{project}.{dataset}.{TABLE_INDSTRYTY_BASE}` x USING (indstrytyClsfcCd, indstrytyCd)),
j AS (
  SELECT l.*, b.bssamt, b.bgn, b.endr, o.prtcptPsblRgnNm AS rgn, o.bidprcPsblIndstrytyNm AS ind,
         TRIM(SPLIT(o.prtcptPsblRgnNm, ',')[SAFE_OFFSET(0)]) AS rgn1,
         r.fnl, r.rsrv, r.n, tg.names
  FROM l
  JOIN b USING (bidNtceNo, bidNtceOrd)
  LEFT JOIN o USING (bidNtceNo, bidNtceOrd)
  LEFT JOIN r USING (bidNtceNo, bidNtceOrd)
  CROSS JOIN tg
  WHERE l.rate >= 80 AND b.bssamt > 0),
k AS (
  SELECT *,
         (SELECT STRING_AGG(DISTINCT TRIM(v), ', ' ORDER BY TRIM(v))
          FROM UNNEST(SPLIT(ind, ',')) v WHERE TRIM(v) IN UNNEST(names)) AS ind_clean,
         IF(STARTS_WITH(rgn1, '전국'), '전국', REPLACE(SPLIT(rgn1, ' ')[SAFE_OFFSET(0)], '...(이하생략', '')) AS sido0
  FROM j)
SELECT
  bidNtceNo AS `공고번호`, bidNtceOrd AS `차수`, bidNtceNm AS `용역명`, ntceInsttNm AS `공고기관`,
  bidNtceDt AS `공고일시`, opengDt AS `개찰일시`,
  bssamt AS `기초금액`, rate AS `낙찰하한율`,
  IF(bgn IS NULL, NULL, CONCAT(bgn, ' ~ ', IFNULL(endr, ''))) AS `예비가격범위`,
  pubPrcrmntLrgClsfcNm, pubPrcrmntMidClsfcNm, pubPrcrmntClsfcNo, pubPrcrmntClsfcNm,
  rgn AS prtcptPsblRgnNm, ind AS `업종_원문`,
  CASE sido0 WHEN '강원특별자치도' THEN '강원도' WHEN '전북특별자치도' THEN '전라북도' WHEN '' THEN '(없음)' ELSE sido0 END AS `시도`,
  IF(rgn IS NULL, NULL, IF(STRPOS(rgn1, ' ') > 0, 1, 0)) AS `시군구있음`,
  LENGTH(rgn) - LENGTH(REPLACE(rgn, ',', '')) + 1 AS `지역수`,
  LENGTH(ind) - LENGTH(REPLACE(ind, ',', '')) + 1 AS `업종수`,
  ind_clean AS `업종_정리`,
  ind_clean IS NOT NULL AS `학습범위_업종`,
  LOG10(bssamt) AS `log_기초금액`,
  rsrv AS `예정가격`, n AS `참여업체수`, fnl AS `최종낙찰금액`,
  (fnl / (bssamt * rate / 100) - 1) * 100 AS y
FROM k
