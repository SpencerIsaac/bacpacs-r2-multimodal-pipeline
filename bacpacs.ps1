[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$BacpacsArgs
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot

$pythonCandidates = @(
    (Join-Path $RepoRoot "BACPACS_env\python.exe"),
    (Join-Path $RepoRoot "BACPACS_env\Scripts\python.exe"),
    (Join-Path $RepoRoot "BAKPACS_env\python.exe"),
    (Join-Path $RepoRoot "BAKPACS_env\Scripts\python.exe")
)

$PythonExe = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $PythonExe) {
    Write-Error "Could not find a repo-local Python environment. Expected BACPACS_env\python.exe or BAKPACS_env\python.exe under $RepoRoot."
    exit 1
}

if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$RepoRoot;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $RepoRoot
}

Push-Location $RepoRoot
try {
    & $PythonExe -m Modality_Pipelines.cli @BacpacsArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
