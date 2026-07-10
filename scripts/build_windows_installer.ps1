param(
    [string]$InstallerUrl = "",
    [string]$ReleaseUrl = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Python virtualenv was not found at $Python"
}

$VersionInfo = & $Python -c "from app.version import APP_VERSION, APP_VERSION_DISPLAY, APP_RELEASE_TAG; print(APP_VERSION); print(APP_VERSION_DISPLAY); print(APP_RELEASE_TAG)"
$AppVersion = $VersionInfo[0].Trim()
$DisplayVersion = $VersionInfo[1].Trim()
$ReleaseTag = $VersionInfo[2].Trim()

Write-Host "Building Takeflow $DisplayVersion ($ReleaseTag)"

& $Python -m PyInstaller --version | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not installed in .venv. Run: .venv\Scripts\python.exe -m pip install pyinstaller"
}

$IsccCandidates = @(@(
    $env:INNO_SETUP_ISCC,
    (Get-Command "ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) })

if (-not $IsccCandidates) {
    throw "Inno Setup 6 compiler ISCC.exe was not found. Install Inno Setup 6, then rerun this script."
}

$Iscc = $IsccCandidates[0]

$BuildDir = Join-Path $ProjectRoot "build"
$DistAppDir = Join-Path $ProjectRoot "dist\takeflow"
$InstallerDir = Join-Path $ProjectRoot "dist\installer"

Remove-Item -LiteralPath $BuildDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $DistAppDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $InstallerDir | Out-Null

& $Python -m PyInstaller ".\packaging\pyinstaller_takeflow.spec" --noconfirm
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE."
}

if (Test-Path (Join-Path $DistAppDir ".env")) {
    throw "Safety stop: .env appeared in the packaged app output."
}

& $Iscc ".\packaging\Takeflow.iss" "/DMyAppVersion=$AppVersion"
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup build failed with exit code $LASTEXITCODE."
}

$InstallerPath = Join-Path $InstallerDir "TakeflowSetup-$AppVersion.exe"
if (-not (Test-Path $InstallerPath)) {
    throw "Installer was not produced at $InstallerPath"
}

$Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $InstallerPath).Hash.ToLowerInvariant()
Write-Host "Installer: $InstallerPath"
Write-Host "SHA256: $Hash"

if (-not $ReleaseUrl) {
    $ReleaseUrl = "https://github.com/KramerIgor/takeflow/releases/tag/$ReleaseTag"
}
if (-not $InstallerUrl) {
    $InstallerUrl = "https://github.com/KramerIgor/takeflow/releases/download/$ReleaseTag/TakeflowSetup-$AppVersion.exe"
}

$ManifestPath = Join-Path $ProjectRoot "update.json"
& $Python ".\scripts\update_release_manifest.py" `
    --manifest $ManifestPath `
    --version $AppVersion `
    --display-version $DisplayVersion `
    --release-tag $ReleaseTag `
    --release-url $ReleaseUrl `
    --asset-key "windows-x64" `
    --asset-url $InstallerUrl `
    --sha256 $Hash `
    --format "exe"
if ($LASTEXITCODE -ne 0) {
    throw "Update manifest generation failed with exit code $LASTEXITCODE."
}
Write-Host "Update manifest: $ManifestPath"
