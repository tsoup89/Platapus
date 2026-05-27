# Platapicker Setup for Windows
# Run this once to set up Platapicker on your PC.
#
# Usage:
#   1. Right-click this file and choose "Run with PowerShell"
#   OR open PowerShell and run: .\setup.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Duck  Platapicker Setup" -ForegroundColor Cyan
Write-Host "--------------------------------------" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Find Python 3.9+ ─────────────────────────────────────────── #

Write-Host "Checking Python 3..." -ForegroundColor Yellow

$python = $null
$candidates = @("python", "python3", "py")

foreach ($cmd in $candidates) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 9) {
                $python = $cmd
                Write-Host "  OK  Found $ver" -ForegroundColor Green
                break
            }
        }
    } catch {}
}

if (-not $python) {
    Write-Host ""
    Write-Host "  ERROR  Python 3.9 or later is required." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Install it free from the Microsoft Store:"
    Write-Host "  https://apps.microsoft.com/detail/9NRWMJLKBM0T" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  After installing, run this script again."
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Step 2: Create virtual environment ──────────────────────────────── #

Write-Host ""
Write-Host "Setting up Python environment..." -ForegroundColor Yellow

$appData = $env:APPDATA
$venvDir = Join-Path $appData "platapicker\venv"

if (Test-Path $venvDir) {
    Write-Host "  Existing environment found — updating..." -ForegroundColor Yellow
} else {
    New-Item -ItemType Directory -Path (Split-Path $venvDir) -Force | Out-Null
    & $python -m venv $venvDir
    Write-Host "  OK  Created Python environment" -ForegroundColor Green
}

$pip = Join-Path $venvDir "Scripts\pip.exe"

# ── Step 3: Install packages ─────────────────────────────────────────── #

Write-Host ""
Write-Host "Installing packages (this takes ~60 seconds the first time)..." -ForegroundColor Yellow

# Find requirements.txt next to this script or inside the installer folder
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$reqs = $null
foreach ($loc in @(
    (Join-Path $scriptDir "requirements.txt")
)) {
    if (Test-Path $loc) { $reqs = $loc; break }
}

if (-not $reqs) {
    Write-Host "  ERROR  requirements.txt not found next to setup.ps1" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

& $pip install --upgrade pip --quiet
& $pip install -r $reqs --quiet

Write-Host "  OK  Packages installed" -ForegroundColor Green

# ── Step 4: Install the app ──────────────────────────────────────────── #

Write-Host ""
Write-Host "Installing Platapicker..." -ForegroundColor Yellow

$installer = Get-ChildItem $scriptDir -Filter "Platapicker-Setup.exe" | Select-Object -First 1

if ($installer) {
    Write-Host "  Running installer..." -ForegroundColor Yellow
    Start-Process $installer.FullName -Wait
    Write-Host "  OK  Platapicker installed" -ForegroundColor Green
} else {
    Write-Host "  NOTE  Installer not found next to this script." -ForegroundColor Yellow
    Write-Host "        If you already ran Platapicker-Setup.exe, you're good."
}

# ── Done ─────────────────────────────────────────────────────────────── #

Write-Host ""
Write-Host "--------------------------------------" -ForegroundColor Cyan
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Launch Platapicker from your Start Menu or Desktop."
Write-Host ""
Read-Host "Press Enter to exit"
