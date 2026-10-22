<#
.SYNOPSIS
    1-Click Windows Bootstrap for Breadwinner
.DESCRIPTION
    Detects Python (3.11+), initializes virtual environment in .venv,
    installs Breadwinner in editable mode, and verifies the environment.
#>

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Breadwinner: Local-First Career Engineering Studio       " -ForegroundColor Yellow
Write-Host "  Windows Automated Environment Bootstrap                  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Locate Python 3.11+
$PythonExe = $null

if (Get-Command "py" -ErrorAction SilentlyContinue) {
    try {
        $pyVer = & py -3.12 --version 2>&1
        if ($LASTEXITCODE -eq 0) { $PythonExe = "py -3.12" }
    } catch {}
    if (-not $PythonExe) {
        try {
            $pyVer = & py -3.11 --version 2>&1
            if ($LASTEXITCODE -eq 0) { $PythonExe = "py -3.11" }
        } catch {}
    }
    if (-not $PythonExe) {
        try {
            $pyVer = & py --version 2>&1
            if ($LASTEXITCODE -eq 0) { $PythonExe = "py" }
        } catch {}
    }
}

if (-not $PythonExe -and (Get-Command "python" -ErrorAction SilentlyContinue)) {
    $PythonExe = "python"
}

if (-not $PythonExe) {
    Write-Host "`n[ERROR] Python was not found on your system." -ForegroundColor Red
    Write-Host "Please install Python 3.11 or newer from https://www.python.org/downloads/ or Microsoft Store." -ForegroundColor Yellow
    exit 1
}

Write-Host "[OK] Using Python: $PythonExe" -ForegroundColor Green

# 2. Create virtual environment
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ScriptDir ".venv"

if (-not (Test-Path $VenvDir)) {
    Write-Host "`n[+] Creating virtual environment in .venv..." -ForegroundColor Cyan
    Invoke-Expression "$PythonExe -m venv `"$VenvDir`""
} else {
    Write-Host "[OK] Existing virtual environment found in .venv" -ForegroundColor Green
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"
$VenvBreadwinner = Join-Path $VenvDir "Scripts\breadwinner.exe"

# 3. Upgrade pip and install package
Write-Host "`n[+] Installing Breadwinner and dependencies..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip
& $VenvPip install -e .

if (Test-Path $VenvBreadwinner) {
    Write-Host "`n==========================================================" -ForegroundColor Green
    Write-Host "  [SUCCESS] Breadwinner installed successfully!           " -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "`nTo start Breadwinner:" -ForegroundColor Yellow
    Write-Host "  .\breadwinner.bat" -ForegroundColor White
    Write-Host "Or run directly:" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\breadwinner" -ForegroundColor White
} else {
    Write-Host "`n[ERROR] Installation completed but breadwinner.exe was not found." -ForegroundColor Red
    exit 1
}
