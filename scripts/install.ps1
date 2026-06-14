param(
    [switch]$DryRun
)

$Repository = if ($env:NINA_REPOSITORY) { $env:NINA_REPOSITORY } else { "__NINA_REPOSITORY__" }
$Channel = if ($env:NINA_CHANNEL) { $env:NINA_CHANNEL } else { "latest" }
$InstallRoot = if ($env:NINA_INSTALL_ROOT) { $env:NINA_INSTALL_ROOT } else { Join-Path $HOME ".nina" }
$AppDir = Join-Path $InstallRoot "app"
$BinDir = Join-Path $InstallRoot "bin"
$LauncherDir = if ($env:NINA_LAUNCHER_DIR) { $env:NINA_LAUNCHER_DIR } else { Join-Path $env:LOCALAPPDATA "Programs\Nina\bin" }

function Get-Target {
    if (-not $IsWindows) {
        throw "install.ps1 only supports Windows. Use install.sh on Linux or macOS."
    }
    if ($env:PROCESSOR_ARCHITECTURE -notin @("AMD64", "x86_64")) {
        throw "Unsupported Windows architecture: $env:PROCESSOR_ARCHITECTURE"
    }
    "windows-x64"
}

$Target = Get-Target
$Asset = "nina-latest-$Target.zip"
$Url = "https://github.com/$Repository/releases/download/$Channel/$Asset"

Write-Host "Installing Nina $Channel for $Target from $Repository"
Write-Host "Archive: $Url"

if ($DryRun) {
    Write-Host "Install root: $InstallRoot"
    Write-Host "Launcher: $(Join-Path $LauncherDir nina.cmd)"
    exit 0
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $UvBin = Join-Path $HOME ".local\bin"
    $CargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
    $env:PATH = "$UvBin;$CargoBin;$env:PATH"
}

$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("nina-install-" + [System.Guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $TempDir, $AppDir, $BinDir, $LauncherDir | Out-Null

try {
    $Archive = Join-Path $TempDir $Asset
    Invoke-WebRequest -Uri $Url -OutFile $Archive
    Expand-Archive -Path $Archive -DestinationPath $TempDir -Force
    uv venv $AppDir
    & (Join-Path $AppDir "Scripts\python.exe") -m pip install --upgrade pip
    $WheelFiles = Get-ChildItem -Path (Join-Path $TempDir "wheels") -Filter *.whl -File | ForEach-Object { $_.FullName }
    if (-not $WheelFiles) {
        throw "No wheel files found in release archive."
    }
    & (Join-Path $AppDir "Scripts\python.exe") -m pip install @WheelFiles
    Copy-Item (Join-Path $TempDir "bin\nina-tui.exe") (Join-Path $BinDir "nina-tui.exe") -Force

    $Launcher = Join-Path $LauncherDir "nina.cmd"
    @"
@echo off
set NINA_TUI_BIN=$BinDir\nina-tui.exe
"$AppDir\Scripts\nina.exe" %*
"@ | Set-Content -Path $Launcher -Encoding ASCII

    Write-Host "Nina installed."
    Write-Host "Add $LauncherDir to PATH if needed."
    Write-Host "Try: nina version"
}
finally {
    Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
}
