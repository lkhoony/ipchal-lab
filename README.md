# ipchal-lab

입찰 낙찰금액 예측 모델 실험실. Claude Code 플러그인(스킬 7개)과 `ipchal` 명령으로, feature를 추가하고 모델을 평가하고 서빙을 요청·승인한다.

이 저장소는 공개라서 프로젝트·테이블·버킷 이름이 없다. 실제 값은 관리자가 따로 주는 설정 파일(`ipchal-lab.env`)과 데이터 안내서(`ipchal-data-guide.md`)에 있다.

## 사용자용 (Mac · Windows)

자세한 내용은 [사용자 매뉴얼](docs/user-manual.md)에 있다. 운영에서 데이터·feature·모델이 흐르는 방식은 [운영 워크플로](docs/operations-workflow.md)를 본다.

Claude 데스크톱 앱 말고는 아무것도 미리 설치하지 않아도 된다 (Python·Homebrew·git 불필요).

1. Claude 앱 Code 탭에서 `/plugin marketplace add https://raw.githubusercontent.com/lkhoony/ipchal-lab/main/.claude-plugin/marketplace.json`
2. `/plugin install ipchal-lab@ipchal-lab`
3. Claude에게 **"시작할래"** 라고 말한다. uv 설치, CLI 설치(uv가 Python 3.12를 직접 받음), 설정 파일, 로그인, 점검을 안내에 따라 진행한다. 관리자에게 받은 설정 파일과 데이터 안내서를 미리 준비해 둔다.

CLI 직접 설치·업데이트: `uv tool install --managed-python --python 3.12 --reinstall https://github.com/lkhoony/ipchal-lab/archive/refs/heads/main.zip`

화면에서 이렇게 말하면 된다.

- "어떤 데이터가 있어?" / "이 컬럼 뭐야?"
- "어떤 feature가 있어?" / "운영에서 뭐 써?"
- "발주기관별 평균을 feature로 추가해 줘"
- "이 feature들로 모델 만들어 줘"
- "이 모델 서빙해 줘" (요청만 등록되고, 관리자가 승인해야 반영된다)

## 관리자용

설정 파일에 `ROLE=admin` 이 있는 사람만 아래를 할 수 있다.

1. **최초 세팅 (완료)**: 기준 뷰·테이블 생성과 기존 feature 67개 등록은 2026-11 관리자가 한 번 해 두었다. 팀원은 따로 할 일이 없다.
2. **배포**: 설정 파일 `ipchal-lab.env` 와 데이터 안내서 `ipchal-data-guide.md` 는 저장소에 올리지 않고 비공개로 따로 전달한다 (`docs/data-guide.template.md` 가 안내서 틀). 사용자용 설정 파일에는 `ROLE` 을 넣지 않거나 `user` 로 둔다. 관리자 설정 파일만 `ROLE=admin`.
3. **하루 조회량 한도**: 공유 계정은 권한이 크므로 평소 사용량에 맞게 한도를 걸어 둔다. Google Cloud 콘솔 → IAM 및 관리자 → 할당량(Quotas)에서 서비스 "BigQuery API"의 "Query usage per day"를 찾아 편집한다. 값은 TiB 단위이고, 기본은 "제한 없음(Unlimited)" 체크 상태이므로 체크를 풀고 허용할 TiB를 입력한다. (이 저장소의 명령은 한도를 바꾸지 않는다. 콘솔에서 직접 설정한다.)
4. **서빙 승인**: 사용자가 요청하면 관리자가 "서빙 요청 보여 줘"로 시작해 승인하거나 반려한다. 문제가 생기면 `ipchal serving rollback <버전>` 으로 되돌린다.
