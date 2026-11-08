-- 연도: 개찰 연도
SELECT `공고번호`, `차수`, EXTRACT(YEAR FROM `개찰일시`) AS value FROM targets
