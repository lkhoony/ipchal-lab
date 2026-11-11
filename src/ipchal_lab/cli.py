"""ipchal 명령. 출력은 쉬운 한국어, 예상된 오류는 한 줄 + exit 1."""
from __future__ import annotations

import argparse
import difflib
import os
import shutil
import sys
from dataclasses import replace
from pathlib import Path

from .config import CONFIG_DIR, KEYS, ConfigError, load_settings
from .experiments import get_experiment, list_experiments, record_experiment
from .guard import GuardError, Permission
from .registry import add_feature, get_feature, list_features, list_prod, retire_feature, update_feature
from .runner import TARGETS_TRAIN, FeatureDef, run_features
from .serving import approve, current_manifest, reject, request_serving, rollback, serving_status

TABLE_DESC = {
    "TABLE_BID_LIST": "공고 목록", "TABLE_BSIS_AMOUNT": "공고별 기초금액", "TABLE_OPN_STD_BID": "개찰 대상 공고(표준)",
    "TABLE_OPN_STD_SCSBID": "개찰 결과·낙찰 정보(표준)", "TABLE_SCSBID_STTUS": "낙찰 현황",
    "TABLE_TARGET_INDSTRYTY": "공고별 대상 업종", "TABLE_INDSTRYTY_BASE": "업종 기준 정보",
    "VIEW_MODEL_BASE": "모델용 기준 뷰 (공고당 1행, 결과 y 포함)", "TABLE_FEATURES": "feature 등록표",
    "TABLE_FEATURES_PROD": "서빙 중인 feature 세트", "TABLE_EXPERIMENTS": "실험 기록",
}


def _yes(p):
    p.add_argument("--yes-bytes", type=int, metavar="N", help="예상 조회량이 한도를 넘어도 N 바이트까지 허용")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ipchal", description="입찰 모델 실험실")
    sub = p.add_subparsers(dest="cmd", required=True)

    def grp(name, help):
        return sub.add_parser(name, help=help).add_subparsers(dest="sub", required=True)

    def leaf(g, _cmd, *args, yes=False, **opts):
        sp = g.add_parser(_cmd)
        for a in args:
            sp.add_argument(a)
        for k, v in opts.items():
            sp.add_argument("--" + k.replace("_", "-"), **v)
        if yes:
            _yes(sp)
        return sp

    s = sub.add_parser("setup", help="설정 파일 설치")
    s.add_argument("--env-file", required=True); s.add_argument("--guide"); s.add_argument("--name", required=True)
    s.add_argument("--home", help=argparse.SUPPRESS)
    sub.add_parser("login", help="브라우저 로그인")
    d = sub.add_parser("doctor", help="설정·로그인·접근·버전 확인")
    d.add_argument("--plugin-version")
    g = grp("data", "데이터 보기")
    leaf(g, "guide"); leaf(g, "tables"); leaf(g, "describe", "key"); leaf(g, "query", "sql", yes=True)
    g = grp("features", "feature 등록표")
    leaf(g, "list", prod=dict(action="store_true"), all=dict(action="store_true"))
    leaf(g, "show", "name"); leaf(g, "retire", "name")
    leaf(g, "preview", sql_file=dict(required=True), kind=dict(default="숫자"), yes=True)
    leaf(g, "add", name=dict(required=True), desc=dict(required=True), kind=dict(required=True),
         sql_file=dict(required=True), yes=True)
    leaf(g, "update", name=dict(required=True), desc={}, kind={}, sql_file={}, yes=True)
    g = grp("experiment", "실험")
    leaf(g, "run", features=dict(required=True), note=dict(default=""), yes=True)
    leaf(g, "list"); leaf(g, "show", "id")
    g = grp("serving", "서빙")
    leaf(g, "request", "id", reason=dict(required=True)); leaf(g, "list")
    leaf(g, "approve", "id", yes=True)
    leaf(g, "reject", "id", note=dict(required=True)); leaf(g, "rollback", "version"); leaf(g, "status")
    return p


def _get(deps, key):
    return deps.get(key) if isinstance(deps, dict) else getattr(deps, key, None)


class Ctx:
    def __init__(self, deps, yes_bytes=None):
        self.deps, self.yes = deps, yes_bytes
        f = _get(deps, "settings")
        self.s = f() if f else load_settings()
        if yes_bytes:
            self.s = replace(self.s, max_bytes_per_query=yes_bytes)
        self._bq = self._gcs = None

    @property
    def bq(self):
        if self._bq is None:
            f = _get(self.deps, "bq")
            if f:
                self._bq = f(self.s)
            else:
                from .bq import Bq
                self._bq = Bq(self.s)
        return self._bq

    @property
    def gcs(self):
        if self._gcs is None:
            f = _get(self.deps, "gcs")
            if f:
                self._gcs = f(self.s)
            else:
                from google.cloud import storage
                from .auth import get_credentials
                self._gcs = storage.Client(project=self.s.gcp_project, credentials=get_credentials(
                    self.s, interactive=False)).bucket(self.s.gcs_bucket)
        return self._gcs

    @property
    def user(self):
        if not self.s.user_name:
            raise ValueError("사용자 이름이 없습니다. 먼저 `ipchal setup --env-file … --name 이름` 을 실행하세요")
        return self.s.user_name


def _frame(df, n=50):
    print(df.head(n).to_string(index=False))
    if len(df) > n:
        print(f"… 총 {len(df)}행 중 {n}행만 보여 드렸습니다")


def _report(r):
    print("검사 통과" if r.ok else "검사 실패 (초안으로 저장됩니다)")
    for x in r.problems:
        print(f"  - {x}")
    print(f"예상 조회량 {r.bytes_train / 1024**3:.2f} GB, 빈 값 비율 {r.null_rate:.1%}, 미래 정보 점검 {r.leak_days_checked}일치")


def _read(path):
    return Path(path).read_text(encoding="utf-8")


def _fdef(name, kind, sql, desc=""):
    return FeatureDef(name, kind, sql, desc)


def cmd_setup(a, deps):
    home = Path(a.home) if a.home else _get(deps, "home")
    cfg = CONFIG_DIR(home)
    env = Path(a.env_file)
    if not env.is_file() or (a.guide and not Path(a.guide).is_file()):
        raise ValueError("파일을 찾을 수 없습니다. 담당자에게 설정 파일을 받으세요")
    cfg.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(env, cfg / "ipchal-lab.env")
    if a.guide:
        shutil.copyfile(a.guide, cfg / "ipchal-data-guide.md")
    (cfg / "user.env").write_text(f"USER_NAME={a.name}\n", encoding="utf-8")
    load_settings(env={}, home=home)
    print(f"설정을 {cfg} 에 저장했습니다. 다음은 `ipchal login` 입니다")
    return 0


def cmd_login(a, deps):
    from .auth import get_credentials
    get_credentials(Ctx(deps).s, interactive=True)
    print("로그인에 성공했습니다")
    return 0


def cmd_doctor(a, deps):
    bad = 0

    def line(ok, msg):
        nonlocal bad
        bad += not ok
        print(("✓ " if ok else "✗ ") + msg)

    try:
        c = Ctx(deps)
        line(True, "설정을 읽었습니다")
    except Exception as e:
        line(False, f"설정: {e}")
        return 1
    try:
        from .auth import get_credentials
        get_credentials(c.s, interactive=False)
        line(True, "로그인 정보가 있습니다")
    except Exception as e:
        line(False, f"로그인: {e}")
    try:
        c.bq.query_df("SELECT 1")
        line(True, "BigQuery 조회가 됩니다")
    except Exception as e:
        line(False, f"BigQuery: {e}")
    try:
        ok = c.gcs.exists()
        line(bool(ok), "GCS 저장소에 접근할 수 있습니다" if ok else "GCS 저장소를 찾을 수 없습니다")
    except Exception as e:
        line(False, f"GCS: {e}")
    try:
        import lightgbm  # noqa: F401
        line(True, "모델 라이브러리(lightgbm)를 불러올 수 있습니다")
    except OSError as e:
        hint = ("Microsoft Visual C++ 재배포 패키지를 설치하세요: https://aka.ms/vs/17/release/vc_redist.x64.exe"
                if sys.platform == "win32" else "담당자에게 이 메시지를 전달하세요")
        line(False, f"모델 라이브러리(lightgbm)를 불러올 수 없습니다 ({e}). {hint}")
    from importlib.metadata import PackageNotFoundError, version
    try:
        v = version("ipchal-lab")
    except PackageNotFoundError:
        v = None
    if a.plugin_version and v != a.plugin_version:
        line(False, f"버전이 다릅니다 (CLI {v}, 플러그인 {a.plugin_version}). 업데이트가 필요합니다: uv tool install --managed-python --python 3.12 --reinstall https://github.com/lkhoony/ipchal-lab/archive/refs/heads/main.zip")
    else:
        line(True, f"버전 {v}")
    return 1 if bad else 0


def cmd_data(a, c):
    if a.sub == "guide":
        p = CONFIG_DIR() / "ipchal-data-guide.md"
        if not p.is_file():
            raise ValueError("데이터 안내서가 없습니다. 담당자에게 받아 `ipchal setup --guide` 로 설치하세요")
        print(p.read_text(encoding="utf-8"))
    elif a.sub == "tables":
        for k in KEYS:
            if k.startswith(("TABLE_", "VIEW_")):
                print(f"{k}: {c.s.table(k).split('.', 2)[2]}  - {TABLE_DESC.get(k, '')}")
    elif a.sub == "describe":
        key = a.key.upper()
        if key not in TABLE_DESC:
            raise ValueError(f"'{a.key}'은(는) 테이블 키가 아닙니다. ipchal data tables 로 확인하세요")
        for f in c.bq.client.get_table(c.s.table(key)).schema:
            print(f"{f.name}  ({f.field_type})")
    else:
        try:
            _frame(c.bq.query_df(a.sql, perm=Permission.READ))
        except GuardError as e:
            raise GuardError(f"읽기 전용입니다: {e}") from None
    return 0


def cmd_features(a, c):
    if a.sub == "list":
        if a.prod:
            df = list_prod(c.bq)
        else:
            df = list_features(c.bq, include_retired=a.all)
        _frame(df[[x for x in ("name", "kind", "status", "description", "model_version") if x in df]])
    elif a.sub == "show":
        f = get_feature(c.bq, a.name)
        print(f"{f.name} ({f.kind}): {f.description}\n\n{f.sql}")
    elif a.sub == "preview":
        f = _fdef("미리보기", a.kind, _read(a.sql_file))
        where = "DATE(`개찰일시`) >= DATE_SUB(CURRENT_DATE('Asia/Seoul'), INTERVAL 1 MONTH)"
        df = run_features(c.bq, [f], where)
        print(df.head(10).to_string())
        print(f"공고 {len(df)}건, 빈 값 비율 {df['미리보기'].isna().mean():.1%} (등록하지 않았습니다)")
    elif a.sub == "add":
        f = _fdef(a.name, a.kind, _read(a.sql_file), a.desc)
        from .checks import check_feature
        r = check_feature(c.bq, f, set(list_features(c.bq, include_retired=True)["name"]))
        user = c.user
        add_feature(c.bq, f, user, r)
        _report(r)
        print(f"'{a.name}'을(를) 등록했습니다" + ("" if r.ok else " (초안 상태, 문제를 고친 뒤 update 하세요)"))
    elif a.sub == "update":
        old = get_feature(c.bq, a.name)
        f = _fdef(a.name, a.kind or old.kind, _read(a.sql_file) if a.sql_file else old.sql,
                  a.desc if a.desc is not None else old.description)
        from .checks import check_feature
        r = check_feature(c.bq, f, set())
        user = c.user
        update_feature(c.bq, f, user, r)
        _report(r)
        print(f"'{a.name}'을(를) 수정했습니다")
    else:
        user = c.user
        retire_feature(c.bq, a.name, user)
        print(f"'{a.name}'을(를) 폐기했습니다 (기록은 남습니다)")
    return 0


def cmd_experiment(a, c):
    if a.sub == "list":
        _frame(list_experiments(c.bq))
    elif a.sub == "show":
        for k, v in get_experiment(c.bq, a.id).items():
            print(f"{k}: {v}")
    else:
        names = [n.strip() for n in a.features.split(",") if n.strip()]
        df = list_features(c.bq).set_index("name")
        for n in names:
            if n not in df.index:
                near = difflib.get_close_matches(n, list(df.index), n=3)
                raise ValueError(f"등록된 feature '{n}'이(가) 없습니다" + (f". 혹시 {', '.join(near)}?" if near else ""))
            if df.loc[n, "status"] != "검사통과":
                raise ValueError(f"feature '{n}'은(는) 검사통과 상태가 아닙니다 (지금 '{df.loc[n, 'status']}'). 실험에는 검사통과 feature만 씁니다")
        user = c.user
        feats = [_fdef(n, df.loc[n, "kind"], df.loc[n, "sql"], df.loc[n, "description"] or "") for n in names]
        from .evaluate import evaluate_features, format_comparison
        m = current_manifest(c.gcs, c.s)
        serving = None if m is None else [_fdef(f["name"], f["kind"], f["sql"], f.get("description", "")) for f in m["features"]]
        r = evaluate_features(c.bq, feats, serving_features=serving)
        print(format_comparison(r))
        print("실험 번호:", record_experiment(c.bq, user, feats, r, a.note, m and m["version"]))
    return 0


def cmd_serving(a, c):
    if a.sub == "request":
        request_serving(c.bq, a.id, c.user, a.reason)
        print(f"서빙을 요청했습니다: {a.id}")
    elif a.sub == "list":
        df = list_experiments(c.bq, 100)
        _frame(df[df["serving_status"] == "요청"])
    elif a.sub == "approve":
        print("승인했습니다. 서빙 버전:", approve(c.bq, c.gcs, c.s, a.id, c.user))
    elif a.sub == "reject":
        reject(c.bq, a.id, c.user, a.note)
        print(f"반려했습니다: {a.id}")
    elif a.sub == "rollback":
        rollback(c.bq, c.gcs, c.s, a.version, c.user)
        print(f"{a.version}(으)로 되돌렸습니다")
    else:
        st = serving_status(c.gcs, c.s)
        print("서빙 중인 모델이 없습니다" if not st else "\n".join(f"{k}: {v}" for k, v in st.items()))
    return 0


def _use_bundled_libomp():
    """macOS: lightgbm은 Homebrew 경로에서만 libomp를 찾는다. Homebrew가 없는 PC를 위해
    scikit-learn에 들어 있는 libomp를 대체 경로로 잡고 한 번 다시 실행한다 (Homebrew libomp가 있으면 그쪽이 우선)."""
    if sys.platform != "darwin":
        return
    from importlib.util import find_spec
    spec = find_spec("sklearn")
    d = spec and Path(next(iter(spec.submodule_search_locations)), ".dylibs")
    cur = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH")
    if not d or not (d / "libomp.dylib").is_file() or str(d) in (cur or "").split(":"):
        return
    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = f"{d}:{cur or '/usr/local/lib:/usr/lib'}"
    os.execv(sys.executable, [sys.executable, "-c", "import sys; from ipchal_lab.cli import main; sys.exit(main())",
                              *sys.argv[1:]])


def main(argv=None, deps=None) -> int:
    if argv is None and deps is None:
        _use_bundled_libomp()
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")
        except Exception:
            pass
    deps = deps or {}
    a = build_parser().parse_args(argv)
    from .bq import TooExpensive
    try:
        if a.cmd in ("setup", "login", "doctor"):
            return {"setup": cmd_setup, "login": cmd_login, "doctor": cmd_doctor}[a.cmd](a, deps)
        c = Ctx(deps, getattr(a, "yes_bytes", None))
        return {"data": cmd_data, "features": cmd_features, "experiment": cmd_experiment,
                "serving": cmd_serving}[a.cmd](a, c)
    except TooExpensive as e:
        print(f"약 {e.bytes / 1024**3:.1f} GB를 조회합니다. 진행하려면 --yes-bytes {e.bytes} 을 붙여 다시 실행하세요", file=sys.stderr)
    except KeyError as e:
        print(e.args[0], file=sys.stderr)
    except (ConfigError, GuardError, PermissionError, ValueError, RuntimeError, OSError) as e:
        print(str(e), file=sys.stderr)
    except Exception as e:
        from google.api_core.exceptions import GoogleAPICallError
        from google.auth.exceptions import GoogleAuthError
        if not isinstance(e, (GoogleAPICallError, GoogleAuthError)):
            raise
        print(f"Google 서비스 오류: {getattr(e, 'message', None) or e}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
