"""로그인: 브라우저 로그인 결과를 설정 폴더(CONFIG_DIR)의 credentials.json 에 저장해 재사용."""
from __future__ import annotations

from .config import CONFIG_DIR, Settings

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def get_credentials(settings: Settings, *, interactive: bool = True):
    import pydata_google_auth
    from pydata_google_auth.cache import ReadWriteCredentialsCache

    cache_dir = CONFIG_DIR()
    cache = ReadWriteCredentialsCache(dirname=str(cache_dir), filename="credentials.json")
    if not interactive:
        cached = cache.load()
        if cached is not None:
            return cached
    else:
        return pydata_google_auth.get_user_credentials(
            scopes=SCOPES, credentials_cache=cache, auth_local_webserver=True)
    import google.auth
    try:
        return google.auth.default(scopes=SCOPES)[0]
    except Exception:
        raise RuntimeError("로그인 정보가 없습니다. 먼저 `ipchal login` 을 실행해 로그인하세요") from None
