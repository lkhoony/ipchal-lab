-- 차수_n: 공고 차수 (재공고면 1 이상)
SELECT `공고번호`, `차수`, SAFE_CAST(`차수` AS INT64) AS value FROM targets
