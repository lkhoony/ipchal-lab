---
name: request-serving
description: 좋은 실험 결과를 실제 서비스에 쓰도록 요청할 때 쓴다. "이 모델 서빙해 줘", "운영에 반영해 줘", "서빙 요청", "이 실험 올려 줘" 같은 말에 반응한다.
---

# 서빙 요청

실험 결과를 운영에 올리자고 요청을 등록한다. 요청만으로는 운영이 바뀌지 않고, 누군가 승인해야 반영된다. 승인은 누구나 할 수 있다 (approve-serving 스킬).

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

1. 어느 실험인지 정한다. 모르면 `ipchal experiment list` 로 고른다.
2. 요청하기 전에 비교표를 먼저 설명한다: `ipchal experiment show <실험번호>` 로 기준(지금 서빙 중인 모델)과 이번 실험의 점수 비교표를 보여 주고, 무엇이 얼마나 좋아졌는지, 우연 범위 안은 아닌지를 쉬운 말로 풀어 준다. 이 표가 승인 여부를 정하는 근거이기 때문이다.
3. 요청 이유를 한두 문장으로 받는다.
4. 사용자가 확인하면 `ipchal serving request <실험번호> --reason "<이유>"` 를 실행한다.
5. 요청만 등록됐고 아직 운영은 그대로라고 알린다. 바로 반영하고 싶다고 하면 approve-serving 스킬의 단계(반영 전 확인 포함)를 따른다. 진행 상황은 `ipchal serving status` 로 볼 수 있다.
