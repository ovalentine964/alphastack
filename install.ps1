# AlphaStack Windows Installer
# Run in PowerShell (as Administrator):
# irm https://raw.githubusercontent.com/ovalentine964/alphastack/main/install.ps1 | iex

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       AlphaStack Installer v0.1.0        ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "🪟 Detected: Windows" -ForegroundColor Green
Write-Host ""

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Python..." -ForegroundColor Yellow
    winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

# Check Git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Git..." -ForegroundColor Yellow
    winget install Git.Git --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}

Write-Host "Cloning AlphaStack..." -ForegroundColor Yellow
git clone https://github.com/ovalentine964/alphastack.git
Set-Location alphastack

Write-Host "Setting up Python environment..." -ForegroundColor Yellow
python -m venv venv
.\venv\Scripts\Activate.ps1

Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install pydantic redis sqlalchemy structlog prometheus-client fastapi uvicorn

# Copy config
Copy-Item config\alphastack.yaml config\alphastack.local.yaml -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "✅ AlphaStack installed!" -ForegroundColor Green
Write-Host ""
Write-Host "To start:" -ForegroundColor Cyan
Write-Host "  cd alphastack"
Write-Host "  .\venv\Scripts\Activate.ps1"
Write-Host "  python -m alphastack.main"
Write-Host ""
Write-Host "Web dashboard: http://localhost:3000" -ForegroundColor Cyan
Write-Host "API docs: http://localhost:8000/docs" -ForegroundColor Cyan
