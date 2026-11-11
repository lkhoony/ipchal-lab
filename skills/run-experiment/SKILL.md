---
name: run-experiment
description: 선택한 feature들로 모델을 학습·평가할 때 쓴다. "이 feature들로 모델 만들어 줘", "실험 돌려 줘", "성능 비교해 줘", "이 feature 효과 있어?" 같은 말에 반응한다.
---

# 실험 실행

feature 묶음으로 모델을 학습하고, 지금 서빙 중인 모델과 비교한 표를 보여 준다.

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


## 단계

1. 쓸 feature를 정한다. 이름을 모르면 `ipchal features list` 로 함께 고른다. 실험에는 상태가 검사통과인 feature만 쓸 수 있다.
2. 시간이 걸리고 조회량이 많다는 점(몇 분~수십 분)을 알린 뒤 `ipchal experiment run --features 이름1,이름2 --note "<메모>"` 를 실행한다.
3. 출력된 비교표를 해석한다.
   - 지금 서빙 중인 모델(기준)과 이번 실험의 점수를 나란히 놓고, 숫자가 어느 쪽이 좋은지 먼저 말해 준다.
   - 차이가 우연 범위 안인지 본다. 표에 나온 오차 범위(신뢰구간 등)보다 차이가 작으면 "우연일 수 있어서 좋아졌다고 말하기 어렵다"고 설명한다.
   - 실험 번호는 나중에 `ipchal experiment show <번호>` 로 다시 볼 수 있다고 알려 준다.
4. 눈에 띄게 좋아졌으면 request-serving 스킬로 서빙 요청을 제안한다. 아니면 feature를 더하거나 고쳐 보자고 제안한다.

실험 기록은 자동으로 남는다 (사용자 이름과 함께).
