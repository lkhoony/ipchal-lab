# Install or update (Windows): powershell -ExecutionPolicy Bypass -File install.ps1 <plugin data folder> [source]
# Keeps uv, Python, ipchal and the download cache inside that folder only. Uninstalling the plugin removes them.
param([Parameter(Mandatory = $true)][string]$D,
      [string]$Src = "https://github.com/lkhoony/ipchal-lab/archive/refs/heads/main.zip")
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $D | Out-Null
$bin = Join-Path $D "bin"
$uv = Join-Path $bin "uv.exe"
if (-not (Test-Path $uv)) {
    # unmanaged: no receipt file, no PATH change
    $env:UV_UNMANAGED_INSTALL = $bin
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
}
$env:UV_TOOL_DIR = Join-Path $D "tools"
$env:UV_TOOL_BIN_DIR = $bin
$env:UV_PYTHON_INSTALL_DIR = Join-Path $D "python"
$env:UV_PYTHON_BIN_DIR = $bin
$env:UV_CACHE_DIR = Join-Path $D "cache"
& $uv tool install --managed-python --python 3.12 --reinstall $Src
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& (Join-Path $bin "ipchal.exe") --help | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output "Installed: $(Join-Path $bin 'ipchal.exe')"
