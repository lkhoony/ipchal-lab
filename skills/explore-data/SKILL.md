---
name: explore-data
description: 데이터를 살펴볼 때 쓴다. "어떤 데이터가 있어?", "이 컬럼 뭐야?", "샘플 보여 줘", "테이블 설명해 줘" 같은 말에 반응한다.
---

# 데이터 살펴보기

데이터 안내서와 읽기 전용 조회로 어떤 데이터가 있는지 설명한다.

## ipchal 실행 방법

`ipchal` 은 이 플러그인의 데이터 폴더에 설치된 것만 쓴다. PATH에 있는 다른 `ipchal`·`uv` 는 쓰지 않는다. 이 문서에서 `ipchal <명령>` 이라고 쓴 것은 아래처럼 실행한다.
- Mac: `"${CLAUDE_PLUGIN_DATA}/bin/ipchal" <명령>`
- Windows (PowerShell): `& "${CLAUDE_PLUGIN_DATA}\bin\ipchal.exe" <명령>`

설치·업데이트 (uv·Python·ipchal을 모두 데이터 폴더 안에 받는다. 몇 분 걸린다):
- Mac: `sh "${CLAUDE_PLUGIN_ROOT}/scripts/install.sh" "${CLAUDE_PLUGIN_DATA}"`
- Windows: `powershell -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}\scripts\install.ps1" "${CLAUDE_PLUGIN_DATA}"`

설치 끝에 "PATH에 없다"는 경고가 나와도 정상이다. PATH나 셸 설정을 바꾸지 않는다 (플러그인을 지우면 깨끗이 지워지도록).

## 먼저 할 일

1. `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json` 을 읽어 `version` 값을 확인한다.
2. `ipchal doctor --plugin-version <그 버전>` 을 실행한다.
3. 실패하면(✗ 표시) 이 단계로 더 진행하지 말고 setup 스킬로 안내한다. `ipchal` 이 아직 없거나 버전이 다르다고 나오면 위의 설치·업데이트 명령을 실행하고 다시 확인한다.

## 안전 규칙

`ipchal` 명령만 쓴다. bq·gcloud·gsutil을 직접 실행하지 않는다. 쓰기·삭제는 명령이 제공하는 것만.

## 말하는 방식

결과는 비개발자가 알아듣는 쉬운 한국어로 설명한다. 전문 용어는 처음 나올 때 한 번 풀어 쓴다.
명령이 `--yes-bytes N` 을 붙여 다시 실행하라는 안내(예상 조회량이 한도를 넘는다는 뜻)를 출력하면, 예상 조회량을 GB로 바꿔 사용자에게 보여 주고 진행할지 먼저 묻는다. 사용자가 동의한 뒤에만 그 옵션을 붙여 다시 실행한다.


## 하는 일

1. `ipchal data guide` 로 데이터 안내서를 읽고, 테이블이 무엇을 담는지 쉬운 말로 설명한다.
2. 테이블 목록이 필요하면 `ipchal data tables`, 컬럼이 궁금하면 `ipchal data describe <키>` (키는 `TABLE_...`/`VIEW_...` 형태).
3. 샘플·요약이 필요하면 `ipchal data query "<SELECT 문>"` 으로 조회한다. 읽기 전용이다.
   - 한글 컬럼 이름은 반드시 `백틱`으로 감싼다 (예: `` `개찰일시` ``).
   - 처음에는 `LIMIT 10` 이나 날짜 조건으로 작게 시작한다. 모델용 기준 뷰는 크므로 필요한 컬럼만 고른다.
   - 데이터 범위: 2016~2021년은 거의 다 있고, 2022~2025년은 거의 비어 있으며, 2026년은 계속 쌓이는 중이다. 기간 이야기가 나오면 알려 준다.
4. 결과 표는 한두 문장으로 요약해 의미를 설명한다.

## 자주 헷갈리는 점

- `최종낙찰금액` 은 개찰 1순위 업체의 투찰금액이다.
- `참여업체수` 는 개찰 결과 행의 개수다.
- `y` 는 최종낙찰금액을 낙찰하한 금액과 비교한 값(%)으로, 모델이 맞히려는 값이다. 아직 개찰 전인 공고는 비어 있다.
