# ============================================================
#  start.ps1 — One-click launcher for Agentic RAG
#  Run from the project root: .\start.ps1
# ============================================================

$BackendDir = "$PSScriptRoot\backend"
$FrontendDir = "$PSScriptRoot\frontend"
$VenvPython  = "$BackendDir\venv\Scripts\python.exe"
$VenvPip     = "$BackendDir\venv\Scripts\pip.exe"
$VenvUvicorn = "$BackendDir\venv\Scripts\uvicorn.exe"

# --- Step 1: Create venv with Python 3.11 if it doesn't exist ---
if (-not (Test-Path $VenvPython)) {
    Write-Host "[1/3] Creating Python 3.11 virtual environment..." -ForegroundColor Cyan
    py -3.11 -m venv "$BackendDir\venv"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Python 3.11 not found. Install it from https://python.org" -ForegroundColor Red
        exit 1
    }
}

# --- Step 2: Install dependencies only if not already installed ---
& $VenvPython -c "import chromadb" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[2/3] Installing dependencies (first time only, ~2-3 min)..." -ForegroundColor Cyan
    & $VenvPip install -r "$BackendDir\requirements.txt" --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: pip install failed. Check your internet connection." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[2/3] Dependencies already installed. Skipping." -ForegroundColor Green
}

# --- Step 3: Start backend + frontend in parallel ---
Write-Host "[3/3] Starting servers..." -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backend  -> http://localhost:8000       (API)" -ForegroundColor Yellow
Write-Host "  API Docs -> http://localhost:8000/docs  (Swagger UI)" -ForegroundColor Yellow
Write-Host "  Frontend -> http://localhost:3000       (Web App)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop both servers." -ForegroundColor Gray
Write-Host ""

# Start frontend in a background job
Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    python -m http.server 3000
} -ArgumentList $FrontendDir | Out-Null

# Start backend in foreground (Ctrl+C stops everything)
Set-Location $BackendDir
& $VenvUvicorn main:app --reload --port 8000
