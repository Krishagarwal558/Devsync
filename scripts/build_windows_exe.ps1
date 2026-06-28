param(
    [string]$Python = "python",
    [string]$Name = "DevSyncAlpha"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

& $Python -m pip install --upgrade pyinstaller

$IconPath = Join-Path $ProjectRoot "desktop\assets\app-icon.ico"
$IconArgs = @()
if (Test-Path $IconPath) {
    $IconArgs = @("--icon", $IconPath)
} else {
    Write-Host "No .ico found at desktop\assets\app-icon.ico; using default executable icon."
}

& $Python -m PyInstaller `
    --name $Name `
    --noconfirm `
    --windowed `
    --clean `
    @IconArgs `
    --add-data "desktop\app\themes;desktop\app\themes" `
    desktop\app\main.py

Write-Host "Built dist\$Name\$Name.exe"

