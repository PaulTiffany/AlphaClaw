# Load AlphaClaw's local .env file into the current PowerShell session.
# Usage from the repository root:
#   . .\scripts\load-env.ps1
#
# The leading dot matters: it keeps the variables in your current shell.

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $RepoRoot ".env"

if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "No .env file found at $EnvFile. Copy .env.example to .env first."
}

$loaded = @()
$lineNumber = 0

foreach ($rawLine in Get-Content -LiteralPath $EnvFile) {
    $lineNumber += 1
    $line = $rawLine.Trim()

    if (-not $line -or $line.StartsWith("#")) {
        continue
    }

    $separator = $line.IndexOf("=")
    if ($separator -lt 1) {
        throw "Invalid .env entry on line $lineNumber. Expected NAME=value."
    }

    $name = $line.Substring(0, $separator).Trim()
    $value = $line.Substring($separator + 1).Trim()

    if ($name -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
        throw "Invalid environment variable name on line ${lineNumber}: $name"
    }

    if ($value.Length -ge 2) {
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
    }

    [Environment]::SetEnvironmentVariable($name, $value, "Process")
    $loaded += $name
}

if ($loaded.Count -eq 0) {
    Write-Host "No environment variables were loaded from .env."
    return
}

Write-Host "Loaded environment variable names from .env (values hidden):"
$loaded | Sort-Object -Unique | ForEach-Object { Write-Host "  $_" }
