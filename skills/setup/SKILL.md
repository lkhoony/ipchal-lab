---
name: setup
description: 처음 설치하고 로그인할 때 쓴다. "시작할래", "설치해 줘", "설정해 줘", "로그인이 안 돼", "doctor가 실패했어" 같은 말에 반응한다.
---

# 시작하기 (설치·설정·로그인)

처음 쓰는 사람의 PC를 준비한다. 다른 스킬의 doctor가 실패했을 때도 여기로 온다. (이 스킬은 설정이 아직 없을 수 있으므로 doctor 실패가 정상이다.)

## 먼저 할 일

1. `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json` 을 읽어 `version` 값을 확인한다.
2. `ipchal doctor --plugin-version <그 버전>` 을 실행한다.
3. 이 스킬(setup)에서는 doctor가 실패하거나 `ipchal` 명령이 아직 없는 것이 정상이다. 오류로 멈추지 말고 아래 단계를 계속한다. 버전이 다르다고 나오면 `uv tool install --managed-python --python 3.12 --reinstall https://github.com/lkhoony/ipchal-lab/archive/refs/heads/main.zip` 을 안내한다.

## 안전 규칙

`ipchal` 명령만 쓴다. bq·gcloud·gsutil을 직접 실행하지 않는다. 쓰기·삭제는 명령이 제공하는 것만.

## 말하는 방식

결과는 비개발자가 알아듣는 쉬운 한국어로 설명한다. 전문 용어는 처음 나올 때 한 번 풀어 쓴다.
명령이 `--yes-bytes N` 을 붙여 다시 실행하라는 안내(예상 조회량이 한도를 넘는다는 뜻)를 출력하면, 예상 조회량을 GB로 바꿔 사용자에게 보여 주고 진행할지 먼저 묻는다. 사용자가 동의한 뒤에만 그 옵션을 붙여 다시 실행한다.


## 단계

1. 운영체제를 묻거나 확인한다 (Mac / Windows).
2. `uv`(파이썬과 프로그램을 알아서 설치해 주는 도구)가 있는지 확인한다 (`uv --version`). 없으면 설치한다. Python·Homebrew·git은 따로 설치하지 않는다.
   - Mac: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - 설치 직후에는 PATH(명령을 찾는 경로)에 아직 반영되지 않아 `uv` 를 못 찾을 수 있다. 그때는 전체 경로로 실행한다: Mac `~/.local/bin/uv`, Windows `"$env:USERPROFILE\.local\bin\uv.exe"`. 이어서 `uv tool update-shell` 을 한 번 실행해 두면 Claude 앱을 다시 시작한 뒤부터는 `uv`·`ipchal` 만으로 실행된다.
3. CLI 설치(업데이트도 같은 명령): `uv tool install --managed-python --python 3.12 --reinstall https://github.com/lkhoony/ipchal-lab/archive/refs/heads/main.zip`
   - Python 3.12를 uv가 직접 내려받아 쓰므로 PC에 Python이 없어도 된다. 몇 분 걸릴 수 있다고 미리 알려 준다.
   - 설치 후 `ipchal --help` 로 확인한다. 못 찾으면 전체 경로로 실행한다: Mac `~/.local/bin/ipchal`, Windows `"$env:USERPROFILE\.local\bin\ipchal.exe"`. 이번 대화에서는 이후 명령도 전체 경로로 실행한다.
4. 담당자에게 받은 파일 두 개(설정 파일 `ipchal-lab.env`, 데이터 안내서 `ipchal-data-guide.md`)가 어디 있는지 묻는다. 없으면 "담당자에게 설정 파일을 받으세요"라고 안내하고 멈춘다. 위치를 모르면 파일을 채팅창에 끌어다 놓게 하거나, 보통 다운로드(Downloads) 폴더에 있다고 안내한다. Windows 경로는 `C:\Users\이름\Downloads\ipchal-lab.env` 처럼 역슬래시(\)로 쓰며, 경로는 항상 큰따옴표로 감싼다.
5. 사용자 이름(결과에 만든 사람으로 남는다)을 묻고 `ipchal setup --env-file "<설정파일 경로>" --guide "<안내서 경로>" --name "<이름>"` 을 실행한다.
6. `ipchal login` 을 실행한다. 브라우저 창이 열리면 담당자가 알려 준 공유 계정으로 로그인하고 허용을 누르라고 안내한다.
7. 마지막으로 `ipchal doctor` 를 실행해 모두 ✓ 인지 확인하고, 다음으로 "어떤 데이터가 있어?" 같은 질문을 해 보라고 알려 준다.

문제가 생기면 출력된 한 줄 메시지를 그대로 쉬운 말로 풀어 주고, 해결이 안 되면 담당자에게 문의하라고 한다.
