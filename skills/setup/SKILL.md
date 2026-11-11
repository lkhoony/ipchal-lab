---
name: setup
description: 처음 설치하고 로그인할 때 쓴다. "시작할래", "설치해 줘", "설정해 줘", "로그인이 안 돼", "doctor가 실패했어" 같은 말에 반응한다.
---

# 시작하기 (설치·설정·로그인)

처음 쓰는 사람의 PC를 준비한다. 다른 스킬의 doctor가 실패했을 때도 여기로 온다. (이 스킬은 설정이 아직 없을 수 있으므로 doctor 실패가 정상이다.)

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
3. 이 스킬(setup)에서는 doctor가 실패하거나 `ipchal` 명령이 아직 없는 것이 정상이다. 오류로 멈추지 말고 아래 단계를 계속한다. 버전이 다르다고 나오면 아래 2단계(설치·업데이트)를 한다.

## 안전 규칙

`ipchal` 명령만 쓴다. bq·gcloud·gsutil을 직접 실행하지 않는다. 쓰기·삭제는 명령이 제공하는 것만.

## 말하는 방식

결과는 비개발자가 알아듣는 쉬운 한국어로 설명한다. 전문 용어는 처음 나올 때 한 번 풀어 쓴다.
명령이 `--yes-bytes N` 을 붙여 다시 실행하라는 안내(예상 조회량이 한도를 넘는다는 뜻)를 출력하면, 예상 조회량을 GB로 바꿔 사용자에게 보여 주고 진행할지 먼저 묻는다. 사용자가 동의한 뒤에만 그 옵션을 붙여 다시 실행한다.


## 단계

1. 운영체제를 묻거나 확인한다 (Mac / Windows).
2. 위의 설치·업데이트 명령을 운영체제에 맞게 실행한다. 실행 전에 이렇게 알려 준다: "프로그램(ipchal)과 그 프로그램 전용 Python을 이 플러그인 전용 폴더에 내려받습니다. 몇 분 걸리고, 다른 프로그램이나 작업 폴더에는 아무것도 바꾸지 않습니다. 나중에 플러그인을 지우면 같이 지워집니다." Python·Homebrew·git은 따로 설치하지 않는다.
3. 끝나면 `ipchal --help` 로 설치를 확인한다.
4. 담당자에게 받은 파일 두 개(설정 파일 `ipchal-lab.env`, 데이터 안내서 `ipchal-data-guide.md`)가 어디 있는지 묻는다. 없으면 "담당자에게 설정 파일을 받으세요"라고 안내하고 멈춘다. 위치를 모르면 파일을 채팅창에 끌어다 놓게 하거나, 보통 다운로드(Downloads) 폴더에 있다고 안내한다. Windows 경로는 `C:\Users\이름\Downloads\ipchal-lab.env` 처럼 역슬래시(\)로 쓰며, 경로는 항상 큰따옴표로 감싼다.
5. 사용자 이름(결과에 만든 사람으로 남는다)을 묻고 `ipchal setup --env-file "<설정파일 경로>" --guide "<안내서 경로>" --name "<이름>"` 을 실행한다.
6. `ipchal login` 을 실행한다. 브라우저 창이 열리면 담당자가 알려 준 공유 계정으로 로그인하고 허용을 누르라고 안내한다.
7. 마지막으로 `ipchal doctor` 를 실행해 모두 ✓ 인지 확인하고, 다음으로 "어떤 데이터가 있어?" 같은 질문을 해 보라고 알려 준다.

문제가 생기면 출력된 한 줄 메시지를 그대로 쉬운 말로 풀어 주고, 해결이 안 되면 담당자에게 문의하라고 한다.
