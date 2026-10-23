param([string]$Profile = "core", [string]$RuntimeHome, [switch]$InstallBlender, [switch]$InstallODA, [switch]$InstallFont)
$ErrorActionPreference = "Stop"
$EZarchConfig = if ($env:EZARCH_CONFIG) { $env:EZARCH_CONFIG } else { Join-Path $env:LOCALAPPDATA "EZarch/settings.json" }
if ($RuntimeHome) { $env:EZARCH_HOME = $RuntimeHome }
if (-not $env:EZARCH_HOME -and (Test-Path $EZarchConfig)) { $env:EZARCH_HOME = (Get-Content -Raw $EZarchConfig | ConvertFrom-Json).home }
if (-not $env:EZARCH_HOME) { throw 'Choose a runtime directory with -RuntimeHome (any writable drive), or set EZARCH_HOME. No download has started.' }
$EZarchToolDir = Join-Path $env:EZARCH_HOME "tools"
New-Item -ItemType Directory -Force -Path $EZarchToolDir | Out-Null
$env:UV_CACHE_DIR = Join-Path $env:EZARCH_HOME "cache/uv"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $env:EZARCH_HOME "runtimes/python"
$env:UV_TOOL_DIR = Join-Path $EZarchToolDir "uv-tools"
$env:TMP = Join-Path $env:EZARCH_HOME "temp"
$env:TEMP = $env:TMP
New-Item -ItemType Directory -Force -Path $env:TMP | Out-Null
$EZarchUv = Join-Path $EZarchToolDir "uv.exe"
if (-not (Test-Path $EZarchUv)) {
    $existing = Get-Command uv -ErrorAction SilentlyContinue
    if ($existing) { $EZarchUv = $existing.Source }
    else {
        $installer = Join-Path $EZarchToolDir "install-uv.ps1"
        Invoke-WebRequest "https://astral.sh/uv/0.11.26/install.ps1" -OutFile $installer
        $env:UV_INSTALL_DIR = $EZarchToolDir
        $env:UV_NO_MODIFY_PATH = "1"
        & $installer
    }
}
$env:EZARCH_UV = $EZarchUv
$arguments = @("run", "--no-project", "--python", "3.12", "python", (Join-Path $PSScriptRoot "bootstrap.py"), "--profile", $Profile, "--home", $env:EZARCH_HOME)
if ($InstallBlender) { $arguments += "--install-blender" }
if ($InstallODA) { $arguments += "--install-oda" }
if ($InstallFont) { $arguments += "--install-font" }
& $EZarchUv @arguments
exit $LASTEXITCODE
