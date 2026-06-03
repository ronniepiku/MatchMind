<#
.SYNOPSIS
    Runs the full CI pipeline locally before pushing to GitHub.

.DESCRIPTION
    Mirrors the GitHub Actions CI workflow (ci.yml + deploy-frontend.yml build step)
    to catch issues before they hit remote CI. Runs:
      1. Python tests (pytest with coverage)
      2. Python linting (ruff)
      3. Python type checking (mypy)
      4. Frontend type checking (tsc --noEmit)
      5. Frontend linting (eslint)
      6. Frontend build (vite)

.PARAMETER SkipFrontend
    Skip frontend checks (useful if only backend changes).

.PARAMETER SkipBackend
    Skip backend checks (useful if only frontend changes).

.PARAMETER Fix
    Auto-fix linting issues where possible (ruff --fix, eslint --fix).

.EXAMPLE
    .\scripts\run-ci-local.ps1
    .\scripts\run-ci-local.ps1 -SkipFrontend
    .\scripts\run-ci-local.ps1 -Fix
#>

param(
    [switch]$SkipFrontend,
    [switch]$SkipBackend,
    [switch]$Fix
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# --- Helpers ---

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "  [PASS] $Message" -ForegroundColor Green
}

function Write-Failure {
    param([string]$Message)
    Write-Host "  [FAIL] $Message" -ForegroundColor Red
}

$failures = @()
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

# --- Backend Checks ---

if (-not $SkipBackend) {
    Write-Step "Python: Installing dependencies"
    & uv sync --all-extras
    if ($LASTEXITCODE -ne 0) {
        $failures += "uv sync"
        Write-Failure "Dependency install failed"
    }
    else {
        Write-Success "Dependencies installed"
    }

    Write-Step "Python: Running tests (pytest)"
    $env:POSTGRES_HOST = ""
    $env:POSTGRES_DB = ""
    & uv run pytest --tb=short -q
    if ($LASTEXITCODE -ne 0) {
        $failures += "pytest"
        Write-Failure "Tests failed"
    }
    else {
        Write-Success "All tests passed"
    }
    Remove-Item Env:\POSTGRES_HOST -ErrorAction SilentlyContinue
    Remove-Item Env:\POSTGRES_DB -ErrorAction SilentlyContinue

    Write-Step "Python: Linting (ruff)"
    if ($Fix) {
        & uv run ruff check --fix .
    }
    else {
        & uv run ruff check .
    }
    if ($LASTEXITCODE -ne 0) {
        $failures += "ruff"
        Write-Failure "Linting issues found (run with -Fix to auto-fix)"
    }
    else {
        Write-Success "No linting issues"
    }

    Write-Step "Python: Format check (ruff format)"
    if ($Fix) {
        & uv run ruff format .
        Write-Success "Code formatted"
    }
    else {
        & uv run ruff format --check .
        if ($LASTEXITCODE -ne 0) {
            $failures += "ruff format"
            Write-Failure "Formatting issues found (run with -Fix to auto-fix)"
        }
        else {
            Write-Success "Code formatting OK"
        }
    }

    Write-Step "Python: Type checking (mypy)"
    & uv run mypy src/football_analytics --ignore-missing-imports
    if ($LASTEXITCODE -ne 0) {
        # mypy failures are warnings, not blockers (strict mode is aspirational)
        Write-Host "  [WARN] Type checking found issues (non-blocking)" -ForegroundColor Yellow
    }
    else {
        Write-Success "Type checking passed"
    }
}

# --- Frontend Checks ---

if (-not $SkipFrontend) {
    $FrontendDir = Join-Path $ProjectRoot "frontend"

    if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
        Write-Step "Frontend: Installing dependencies"
        Push-Location $FrontendDir
        & npm ci
        if ($LASTEXITCODE -ne 0) {
            $failures += "npm ci"
            Write-Failure "Frontend dependency install failed"
        }
        else {
            Write-Success "Dependencies installed"
        }
        Pop-Location
    }

    Write-Step "Frontend: Type checking (tsc --noEmit)"
    Push-Location $FrontendDir
    & npx tsc --noEmit
    if ($LASTEXITCODE -ne 0) {
        $failures += "tsc"
        Write-Failure "TypeScript type errors found"
    }
    else {
        Write-Success "No type errors"
    }
    Pop-Location

    Write-Step "Frontend: Linting (eslint)"
    Push-Location $FrontendDir
    if ($Fix) {
        & npx eslint . --fix
    }
    else {
        & npx eslint .
    }
    if ($LASTEXITCODE -ne 0) {
        $failures += "eslint"
        Write-Failure "ESLint issues found"
    }
    else {
        Write-Success "No linting issues"
    }
    Pop-Location

    Write-Step "Frontend: Build (vite)"
    Push-Location $FrontendDir
    & npm run build
    if ($LASTEXITCODE -ne 0) {
        $failures += "vite build"
        Write-Failure "Frontend build failed"
    }
    else {
        Write-Success "Build succeeded"
    }
    Pop-Location
}

# --- Summary ---

$stopwatch.Stop()
$elapsed = $stopwatch.Elapsed.ToString("mm\:ss")

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CI PIPELINE SUMMARY ($elapsed)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if ($failures.Count -eq 0) {
    Write-Host ""
    Write-Host "  All checks passed! Safe to push." -ForegroundColor Green
    Write-Host ""
    exit 0
}
else {
    Write-Host ""
    Write-Host "  $($failures.Count) check(s) failed:" -ForegroundColor Red
    foreach ($f in $failures) {
        Write-Host "    - $f" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "  Fix issues before pushing." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
