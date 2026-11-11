---
name: features
description: 등록된 feature 목록과 운영 중인 feature를 볼 때 쓴다. "어떤 feature가 있어?", "운영에서 뭐 써?", "이 feature 설명해 줘", "누가 만들었어?" 같은 말에 반응한다.
---

# feature 보기

feature는 모델이 공고를 보고 계산하는 "참고 값" 하나(예: 최근 20건 평균 결과)를 말한다. 등록표를 읽어 쉽게 설명한다.

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

- 전체 목록: `ipchal features list` (폐기된 것까지 보려면 `ipchal features list --all`)
- 운영(서빙) 중인 목록: `ipchal features list --prod`
- 하나의 자세한 내용(설명, SQL): `ipchal features show <이름>`
- 최근 실험에서 어떤 feature가 얼마나 도움이 됐는지: `ipchal experiment list`, `ipchal experiment show <실험번호>`

## 설명할 때

- 상태를 풀어 준다: 검사통과 = 실험에 쓸 수 있음, 초안 = 검사에서 문제가 있어 고쳐야 함, 폐기 = 더 쓰지 않음.
- 비슷한 이름이 많으면 종류(숫자/범주)와 설명으로 묶어서 보여 준다.
- feature를 새로 만들고 싶어 하면 add-feature 스킬로 안내한다.
