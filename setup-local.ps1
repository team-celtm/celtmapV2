$ErrorActionPreference = "Stop"

$workspaceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $workspaceRoot "backend"
$frontendDir = Join-Path $workspaceRoot "frontend"
$backendVenvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$backendEnv = Join-Path $backendDir ".env"
$backendEnvExample = Join-Path $backendDir ".env.example"
$frontendLock = Join-Path $frontendDir "package-lock.json"

function Invoke-ProjectPython {
    param([string[]]$Arguments)

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 @Arguments
        return
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python @Arguments
        return
    }

    throw "Python was not found. Install Python 3.11 or newer and rerun this script."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Install Node.js 20 or newer and rerun this script."
}

if (-not (Test-Path -LiteralPath $backendVenvPython)) {
    Write-Host "Creating backend virtual environment..."
    Invoke-ProjectPython -Arguments @("-m", "venv", (Join-Path $backendDir ".venv"))
}

Write-Host "Installing backend Python packages..."
& $backendVenvPython -m pip install --upgrade pip
& $backendVenvPython -m pip install -r (Join-Path $backendDir "requirements.txt")

if (-not (Test-Path -LiteralPath $backendEnv) -and (Test-Path -LiteralPath $backendEnvExample)) {
    Copy-Item -LiteralPath $backendEnvExample -Destination $backendEnv
    Write-Host "Created backend\.env from backend\.env.example."
}

Write-Host "Installing frontend npm packages..."
Push-Location $frontendDir
try {
    if (Test-Path -LiteralPath $frontendLock) {
        npm ci
    } else {
        npm install
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Install complete."
Write-Host "Start the app from the project root with: .\run-local.ps1"
