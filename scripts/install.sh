#!/bin/sh
# 설치·업데이트 (Mac): sh install.sh <플러그인 데이터 폴더> [설치 원본]
# uv·Python·ipchal·다운로드 캐시를 모두 그 폴더 안에만 둔다. 플러그인을 지우면 같이 지워진다.
set -e
D="$1"
SRC="${2:-https://github.com/lkhoony/ipchal-lab/archive/refs/heads/main.zip}"
[ -n "$D" ] || { echo "플러그인 데이터 폴더 경로가 필요합니다" >&2; exit 2; }
mkdir -p "$D"
# unmanaged: 영수증 파일·PATH 설정 없이 그 폴더에만 설치
[ -x "$D/bin/uv" ] || curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="$D/bin" sh
export UV_TOOL_DIR="$D/tools" UV_TOOL_BIN_DIR="$D/bin" UV_PYTHON_INSTALL_DIR="$D/python" \
       UV_PYTHON_BIN_DIR="$D/bin" UV_CACHE_DIR="$D/cache"
"$D/bin/uv" tool install --managed-python --python 3.12 --reinstall "$SRC"
"$D/bin/ipchal" --help >/dev/null
echo "설치를 마쳤습니다: $D/bin/ipchal"
