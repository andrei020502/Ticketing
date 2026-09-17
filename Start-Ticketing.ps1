<#
    Start-Ticketing.ps1
    ------------------------------------------------------------------
    Launches the local personal ticketing app and opens it in Microsoft
    Edge. On first run it creates a virtual environment and installs the
    Python dependencies automatically.

    Usage (from PowerShell, in this folder):
        .\Start-Ticketing.ps1

    If script execution is blocked, run once:
        Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
    ------------------------------------------------------------------
#>

$ErrorActionPreference = "Stop"

# Always work from the folder this script lives in.
Set-Location -Path $PSScriptRoot

$venvPath   = Join-Path $PSScriptRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$appUrl     = "http://127.0.0.1:5000"

# --- Locate a Python interpreter -------------------------------------------
function Get-Python {
    foreach ($cmd in @("python", "py")) {
        $p = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($p) { return $p.Source }
    }
    return $null
}

# --- Create the virtual environment on first run ---------------------------
if (-not (Test-Path $venvPython)) {
    Write-Host "First-time setup: creating virtual environment..." -ForegroundColor Cyan
    $py = Get-Python
    if (-not $py) {
        Write-Host "ERROR: Python was not found. Install Python 3.10+ from https://www.python.org/downloads/ and re-run." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    & $py -m venv $venvPath
    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    & $venvPython -m pip install --upgrade pip | Out-Null
    & $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
    Write-Host "Setup complete." -ForegroundColor Green
}

# --- Open Microsoft Edge at the app URL (slightly delayed) -----------------
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    try {
        Start-Process "msedge.exe" $using:appUrl
    } catch {
        # Fall back to the default browser if Edge isn't available.
        Start-Process $using:appUrl
    }
} | Out-Null

# --- Run the app (blocks until you press Ctrl+C) ---------------------------
Write-Host ""
Write-Host "Ticketing is running at $appUrl" -ForegroundColor Green
Write-Host "Press Ctrl+C in this window to stop the server." -ForegroundColor Yellow
Write-Host ""

& $venvPython (Join-Path $PSScriptRoot "app.py")
