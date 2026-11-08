---
name: features
description: 등록된 feature 목록과 운영 중인 feature를 볼 때 쓴다. "어떤 feature가 있어?", "운영에서 뭐 써?", "이 feature 설명해 줘", "누가 만들었어?" 같은 말에 반응한다.
---

# feature 보기

feature는 모델이 공고를 보고 계산하는 "참고 값" 하나(예: 최근 20건 평균 결과)를 말한다. 등록표를 읽어 쉽게 설명한다.

## 먼저 할 일

1. `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json` 을 읽어 `version` 값을 확인한다.
2. `ipchal doctor --plugin-version <그 버전>` 을 실행한다.
3. 실패하면(✗ 표시) 이 단계로 더 진행하지 말고 setup 스킬로 안내한다. 버전이 다르다고 나오면 `uv tool install --managed-python --python 3.12 --reinstall https://github.com/lkhoony/ipchal-lab/archive/refs/heads/main.zip` 을 안내하고 다시 확인한다.

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
