-- 시각: 개찰 시각 (시)
SELECT `공고번호`, `차수`, EXTRACT(HOUR FROM `개찰일시`) AS value FROM targets
