---
name: approve-serving
description: 서빙 요청을 검토하고 승인·반려·되돌릴 때 쓴다(관리자 전용). "서빙 요청 보여 줘", "승인", "반려", "이전 버전으로 되돌려 줘" 같은 말에 반응한다.
---

# 서빙 승인 (관리자)

요청된 모델을 운영에 반영하거나 되돌린다. 설정 파일에 `ROLE=admin` 이 있는 관리자만 쓸 수 있다. 일반 사용자라면 여기서 멈추고 관리자에게 부탁하라고 안내한다.

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

1. 요청 목록: `ipchal serving list`. 현재 서빙 상태: `ipchal serving status`.
2. 검토할 요청의 비교표를 `ipchal experiment show <실험번호>` 로 보여 주고, 요청 이유와 함께 쉬운 말로 설명한다 (기준 대비 좋아졌는지, 우연 범위 안인지, 쓰인 feature).
3. 승인 여부를 사용자에게 명확하게 "승인할까요, 말까요?" 예/아니오로 묻는다. 분명한 "예"를 받기 전에는 승인하지 않는다.
4. 예 → `ipchal serving approve <실험번호>`. 서빙 모델 파일이 새로 만들어져 올라가므로 몇 분 걸릴 수 있다. 끝나면 새 서빙 버전을 알려 준다.
   - 요청한 사람과 승인하는 사람이 같으면 기본적으로 거부된다. 관리자가 한 명뿐이라 불가피할 때만 `--self-approve` 를 붙이는 방법이 있다고 설명하고, 사용자가 원할 때만 쓴다. 다른 관리자가 승인하는 것이 원칙이다.
   - 조회량 안내가 나오면 위의 `--yes-bytes` 규칙을 따른다.
5. 아니오 → `ipchal serving reject <실험번호> --note "<반려 이유>"`.

## 되돌리기

문제가 생기면 이전 버전으로 되돌릴 수 있다. 어떤 버전이 있는지 `ipchal serving status` 로 확인하고, 사용자에게 어느 버전으로 돌아갈지 확인받은 뒤 `ipchal serving rollback <버전>` 을 실행한다. 이전 버전 파일은 저장소에 그대로 남아 있어 필요하면 다시 전환할 수 있다.
