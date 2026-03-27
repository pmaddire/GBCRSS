param(
    [string]$TargetRepoPath = (Get-Location).Path,
    [string]$GcieRepoUrl = "https://github.com/pmaddire/GBCRSS.git",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"

function New-GcieVenv {
    param([string]$RepoPath)

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv (Join-Path $RepoPath ".venv")
        return
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv (Join-Path $RepoPath ".venv")
        return
    }
    throw "Python 3.11+ is required. Install Python and retry."
}

$target = (Resolve-Path -LiteralPath $TargetRepoPath).Path
$tempRoot = Join-Path $env:TEMP ("gcie_bootstrap_" + [guid]::NewGuid().ToString("N"))

Write-Host "[GCIE] Cloning from $GcieRepoUrl ..."
git clone --depth 1 --branch $Branch $GcieRepoUrl $tempRoot | Out-Null

Write-Host "[GCIE] Creating virtual environment ..."
New-GcieVenv -RepoPath $tempRoot

$venvPython = Join-Path $tempRoot ".venv\Scripts\python.exe"

Write-Host "[GCIE] Installing minimal dependencies ..."
& $venvPython -m pip install --disable-pip-version-check --quiet networkx GitPython typer

Write-Host "[GCIE] Running setup in target repo: $target"
& $venvPython -m cli.app setup $target

Write-Host "[GCIE] Done. You can now run in your repo:"
Write-Host "  gcie.cmd context . \"<task>\" --intent edit --budget auto"
