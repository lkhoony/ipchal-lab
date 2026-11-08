-- 월: 개찰 월
SELECT `공고번호`, `차수`, EXTRACT(MONTH FROM `개찰일시`) AS value FROM targets
