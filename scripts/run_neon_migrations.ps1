param(
    [string]$EnvFile = "server\.env.beta",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $EnvFile)) {
    throw "Env file not found: $EnvFile"
}

Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) {
        return
    }
    $idx = $line.IndexOf("=")
    if ($idx -lt 1) {
        return
    }
    $name = $line.Substring(0, $idx)
    $value = $line.Substring($idx + 1)
    [Environment]::SetEnvironmentVariable($name, $value, "Process")
}

& $Python -m alembic -c server/alembic.ini upgrade head
