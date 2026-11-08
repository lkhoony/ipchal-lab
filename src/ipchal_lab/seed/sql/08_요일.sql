-- 요일: 개찰 요일 (0=월)
SELECT `공고번호`, `차수`, MOD(EXTRACT(DAYOFWEEK FROM `개찰일시`) + 5, 7) AS value FROM targets
