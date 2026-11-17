<h1 align="center">ipchal-lab</h1>

입찰 낙찰 예측 모델 실험실입니다. Claude에게 문장으로 말하면 Claude가 `ipchal` 명령을 대신 실행하고 결과를 쉬운 말로 풀어 줍니다. 명령어는 외우지 않아도 됩니다.

## 준비물

- Claude 유료 요금제(Pro·Max·Team·Enterprise)
- [Claude 데스크톱 앱](https://claude.ai/download)의 **Code** 탭 또는 Claude Code(터미널). 일반 Chat 탭에서는 동작하지 않습니다.
- 담당자에게 받는 비공개 파일 두 개(설정 파일 `ipchal-lab.env`, 데이터 안내서 `ipchal-data-guide.md`)와 공유 Google 계정 로그인 방법
- Python·Homebrew·git은 필요 없습니다.

## 설치

Code 탭(또는 Claude Code) 입력창에 한 줄씩 보냅니다.

```
/plugin marketplace add https://raw.githubusercontent.com/lkhoony/ipchal-lab/main/.claude-plugin/marketplace.json
```
```
/plugin install ipchal-lab@ipchal-lab
```

범위를 물으면 **사용자(User)** 를 고릅니다. `/reload-plugins` (또는 앱 재시작) 후 **"시작할래"** 라고 말하세요. Claude가 프로그램 설치 → 설정 파일 위치 → 이름 → Google 로그인 → 점검을 차례로 안내합니다. 점검이 모두 ✓ 면 끝입니다.

데스크톱 앱에서 `/plugin` 이 안 되면 터미널에 Claude Code를 설치해 같은 두 줄로 한 번 설치하세요. 같은 PC면 앱에도 보입니다.

```bash
curl -fsSL https://claude.ai/install.sh | bash      # Mac
```
```powershell
irm https://claude.ai/install.ps1 | iex             # Windows (PowerShell)
```

## 업데이트

```
/plugin marketplace update ipchal-lab
```

그다음 `/plugin` → **Installed** → `ipchal-lab` → **Update now** (터미널에서는 `claude plugin update ipchal-lab@ipchal-lab`), `/reload-plugins`, 마지막으로 **"업데이트해 줘"** 라고 말합니다.

## 프롬프트 샘플

| 하고 싶은 일 | 예시 |
|---|---|
| 시작·점검 | - "시작할래"<br>- "점검해 줘"<br>- "로그인 다시 해 줘"<br>- "업데이트해 줘" |
| 데이터 보기 | - "어떤 데이터가 있어?"<br>- "model_base 컬럼 설명해 줘"<br>- "최근 개찰된 공고 10건 보여 줘"<br>- "공고번호 R26BK01788169 정보 보여 줘"<br>- "연도별 공고 수와 예가율 있는 비율 알려 줘" |
| 통계 분석 | - "2026년 10월 개찰 공고의 예가율 평균 알려 줘"<br>- "2025년 예가율 분포를 0.1 단위로 보여 줘"<br>- "낙찰하한율별 예가율 평균·중앙값·건수 비교해 줘"<br>- "대분류별 최근 1년 예가율 평균을 월별로 보여 줘"<br>- "참여업체수와 예가율 상관계수 알려 줘"<br>- "학습 범위 업종만 시도별 예가율 비교해 줘" |
| 원본 데이터 | - "개찰 결과 원본에서 이 공고 업체별 투찰 내역 보여 줘"<br>- "원본으로 ○○ 업체의 최근 1년 투찰률 분포 보여 줘"<br>- "원본 공고 목록에서 이 공고 수집 이력 보여 줘" |
| 비용 | - "이번 달 GCP 얼마 썼어?"<br>- "비용 한도 남았어?" |
| feature 보기 | - "어떤 feature가 있어?"<br>- "운영에서 지금 어떤 feature 써?"<br>- "전체_sma20 이 뭐야? SQL도 보여 줘"<br>- "내가 만든 feature 보여 줘" |
| feature 만들기·고치기 | - "같은 공고기관의 최근 20건 평균 예가율을 feature로 만들어 줘"<br>- "이 feature SQL 고쳐서 다시 검사해 줘"<br>- "초안 상태 feature 왜 실패했어?"<br>- "이 feature 폐기해 줘" |
| 실험 | - "낙찰하한율, log_기초금액, 대분류_sma20 으로 모델 만들어 줘"<br>- "운영 모델 feature에 기관_최근20_평균을 더하면 좋아져?"<br>- "검사통과한 feature 전부로 실험해 줘"<br>- "지금까지 실험 목록 보여 줘"<br>- "실험 exp-… 결과 다시 보여 줘" |
| 운영 반영 | - "이 실험 서빙해 줘"<br>- "서빙 요청 보여 줘"<br>- "승인해 줘" / "반려해 줘, 이유는 …"<br>- "지금 운영 모델 뭐야?"<br>- "v03으로 되돌려 줘" |

기간("2025년", "최근 3개월")과 결과 모양("표로", "월별로")을 넣으면 조회량이 줄고 답이 분명해집니다.

## 알아 두기

- **예가율**: 모델이 맞히려는 값. 최종낙찰금액이 낙찰하한가보다 몇 % 높은지입니다. `(최종낙찰금액 ÷ (기초금액 × 낙찰하한율 ÷ 100) − 1) × 100`, 데이터 열 이름은 `y`.
- **model_base**: 조회·통계의 기본 데이터(공고 1건 = 1행, 2016년부터 매일 갱신). 원본 테이블은 "원본으로"라고 말해야 읽고, 그때도 Claude가 한 번 더 확인합니다.
- **비용 한도**: 데이터를 읽기 전에 이번 달 GCP 사용액을 확인하고, 한도(월 10만 원)를 넘길 조회는 실행하지 않습니다. 매달 1 TiB까지 무료라 평소엔 0원입니다.
- **feature**: 등록할 때 형식·빈 값·미래 정보(개찰 7일 전보다 앞선 결과만 쓰는지)·비용을 자동 검사합니다. 만들거나 고쳐도 운영 모델은 그대로입니다.
- **실험**: 데이터의 마지막 12개월로 평가합니다. 주 지표는 0.01 적중률(0.01%p 칸 중 모델이 고른 5칸 안에 실제 결과가 든 비율)입니다. 차이가 ±(표준오차)의 2배보다 작으면 우연일 수 있고, 같은 feature로 다시 학습해도 0.2%p쯤 흔들립니다.
- **운영 반영**: 요청과 승인은 누구나 할 수 있습니다. 승인 직전에 Claude가 영향과 근거를 설명하고 다시 묻습니다. 되돌릴 수 있지만 새 버전 파일은 남습니다.

## 지켜 주세요

- 테이블은 Claude와 `ipchal` 로만 다룹니다. 콘솔에서 직접 고치지 마세요.
- 비용 한도에 막히면 우회하지 말고 담당자에게 알리세요.
- 설정 파일·데이터 안내서·로그인 정보, 원본의 개인정보(대표자명·연락처·주소)는 공유하지 마세요.

## FAQ

**"버전이 다릅니다"가 나와요.** [업데이트](#업데이트)를 하세요.

**"시작할래"에 반응이 없어요.** `/reload-plugins` 또는 재시작. 그래도 안 되면 `/plugin` → **Installed** 에서 `ipchal-lab` 이 켜져 있는지 보세요.

**"월 한도를 넘어 실행하지 않았습니다" / "사용액을 확인할 수 없어…"** 메시지를 그대로 담당자에게 보내 주세요.

**실험이 오래 걸려요.** feature 2~5개로 시작하세요.

**Windows에서도 되나요?** 됩니다. 모델 라이브러리 오류가 나오면 점검 결과의 Microsoft 링크로 구성 요소를 설치하세요.

**다 지우고 싶어요.** `/plugin uninstall ipchal-lab@ipchal-lab`. 프로그램·Python·설정·로그인 정보는 모두 플러그인 전용 폴더(`~/.claude/plugins/data/ipchal-lab-ipchal-lab/`)에만 있어서 같이 지워집니다.

## 담당자용

- 이 저장소는 공개라 프로젝트·테이블·버킷 이름이 없습니다. 실제 값은 `ipchal-lab.env` 와 `ipchal-data-guide.md` 로 비공개 전달합니다(틀: `docs/data-guide.template.md`). 모두 같은 설정 파일을 씁니다.
- 기준 뷰·테이블과 기존 feature 등록은 2026-11에 끝났습니다. 팀원은 따로 할 일이 없습니다.
- 팀 계정에는 사용액을 읽을 수 있게 **BigQuery 리소스 뷰어** 권한이 있어야 합니다. 없으면 모든 조회가 막힙니다.
- 하루 조회량 한도: Google Cloud 콘솔 → IAM 및 관리자 → 할당량에서 "BigQuery API"의 "Query usage per day"를 TiB 단위로 설정합니다.
- 데이터·feature·모델이 운영에서 흐르는 방식: [운영 워크플로](docs/operations-workflow.md)
