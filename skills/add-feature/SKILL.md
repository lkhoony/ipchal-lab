---
name: add-feature
description: 새 feature를 만들어 등록할 때 쓴다. "발주기관별 평균을 feature로 추가해 줘", "feature 만들어 줘", "새 변수 추가", "SQL로 feature 등록" 같은 말에 반응한다.
---

# feature 추가

사용자의 아이디어를 SQL로 만들어 미리 보고, 검사를 거쳐 등록한다.

## 먼저 할 일

1. `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json` 을 읽어 `version` 값을 확인한다.
2. `ipchal doctor --plugin-version <그 버전>` 을 실행한다.
3. 실패하면(✗ 표시) 이 단계로 더 진행하지 말고 setup 스킬로 안내한다. 버전이 다르다고 나오면 `uv tool install --managed-python --python 3.12 --reinstall https://github.com/lkhoony/ipchal-lab/archive/refs/heads/main.zip` 을 안내하고 다시 확인한다.

## 안전 규칙

`ipchal` 명령만 쓴다. bq·gcloud·gsutil을 직접 실행하지 않는다. 쓰기·삭제는 명령이 제공하는 것만.

## 말하는 방식

결과는 비개발자가 알아듣는 쉬운 한국어로 설명한다. 전문 용어는 처음 나올 때 한 번 풀어 쓴다.
명령이 `--yes-bytes N` 을 붙여 다시 실행하라는 안내(예상 조회량이 한도를 넘는다는 뜻)를 출력하면, 예상 조회량을 GB로 바꿔 사용자에게 보여 주고 진행할지 먼저 묻는다. 사용자가 동의한 뒤에만 그 옵션을 붙여 다시 실행한다.


## 단계

1. 아이디어를 듣는다 (무엇을 어떤 기준으로 계산할지, 숫자인지 범주(글자 값)인지).
2. 비슷한 feature가 이미 있는지 `ipchal features list` 로 확인하고, 있으면 먼저 알려 준다.
3. 아래 규칙대로 SQL을 작성해 파일로 저장한다 (예: 작업 폴더의 `my_feature.sql`).
4. `ipchal features preview --sql-file my_feature.sql` (범주 feature면 `--kind 범주` 도 붙인다) 로 최근 한 달 공고에서 값이 나오는지 본다. 등록은 되지 않는다. 결과(몇 건, 빈 값 비율)를 쉬운 말로 설명한다.
5. 사용자에게 이름·한 줄 설명·종류를 확인받는다. 확인 없이 등록하지 않는다.
6. `ipchal features add --name <이름> --desc "<설명>" --kind 숫자 --sql-file my_feature.sql` 로 등록한다 (범주면 `--kind 범주`).
   - 검사에는 몇 분이 걸리고 약 4 GB를 조회한다. 시작 전에 미리 알려 준다.
   - 검사 결과: 통과면 "실험에 쓸 수 있다"고, 실패면 어떤 문제인지(형식, 빈 값, 미래 정보, 비용) 풀어서 설명하고 초안으로 저장됐음을 알린다. 고친 뒤 `ipchal features update --name <이름> --sql-file my_feature.sql` 로 다시 검사한다.

## SQL 작성 규칙

- 읽을 수 있는 것은 `base` 와 `targets` 두 개뿐이다. `base` 는 과거 결과를 포함한 전체 기준 표이고, `targets` 는 값을 계산해 줄 공고들이다. 다른 테이블 이름이나 프로젝트 이름은 쓰지 않는다.
- 결과 열은 `공고번호`, `차수`, `value` 세 개. `targets` 의 공고마다 정확히 한 행이어야 한다 (두 행이거나 빠지면 등록이 거부된다).
- 한글 열 이름은 반드시 `백틱`으로 감싼다.
- 개찰일시는 DATETIME 이므로 날짜를 뺄 때 ``DATETIME_SUB(t.`개찰일시`, INTERVAL 7 DAY)`` 를 쓴다.
- 미래 정보 금지: 어떤 공고의 값을 계산할 때는 그 공고 개찰일시보다 7일 이상 앞서 개찰된 결과(`개찰일시` < 개찰일시 − 7일)만 쓴다. 개찰 직전 며칠은 결과가 아직 다 알려지지 않았기 때문이다. 어기면 검사가 "미래 정보"로 막는다.
- 윈도 함수의 `ORDER BY` 는 항상 `개찰일시`, `공고번호`, `차수` 로 끝낸다. 같은 시각 개찰 건 때문에 순서가 흔들리면 값이 불안정해져 "미래 정보"로 잡힌다.
- 통계(평균 등)는 `base` 에서 계산한다. `targets` 끼리 섞어 계산하지 않는다. feature는 공고 하나하나에 대한 값이어야 한다.
- 과거가 없는 공고는 값이 NULL(빈 값)로 나와도 되고, 행이 빠지면 안 된다 (그래서 `targets` 에서 시작해 LEFT JOIN).

## 예시 (같은 낙찰하한율의 직전 20건 평균 y)

```sql
WITH past AS (
  SELECT
    t.`공고번호`,
    t.`차수`,
    b.y,
    ROW_NUMBER() OVER (
      PARTITION BY t.`공고번호`, t.`차수`
      ORDER BY b.`개찰일시` DESC, b.`공고번호` DESC, b.`차수` DESC
    ) AS rn
  FROM targets t
  JOIN base b
    ON b.`낙찰하한율` = t.`낙찰하한율`
   AND b.y IS NOT NULL
   AND b.`개찰일시` < DATETIME_SUB(t.`개찰일시`, INTERVAL 7 DAY)
)
SELECT
  t.`공고번호`,
  t.`차수`,
  AVG(p.y) AS value
FROM targets t
LEFT JOIN past p
  ON p.`공고번호` = t.`공고번호` AND p.`차수` = t.`차수` AND p.rn <= 20
GROUP BY t.`공고번호`, t.`차수`
```
