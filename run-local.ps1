$ErrorActionPreference = "Stop"

$workspaceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $workspaceRoot "backend"
$frontendDir = Join-Path $workspaceRoot "frontend"
$backendEnvFile = Join-Path $backendDir ".env"
$frontendEnvFile = Join-Path $frontendDir ".env.local"
$backendLogFile = Join-Path $backendDir "dev-backend.out.log"
$frontendLogFile = Join-Path $frontendDir "dev-frontend.out.log"

function Stop-LocalPortProcess {
    param([int[]]$Ports)

    foreach ($port in $Ports) {
        Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique |
            ForEach-Object {
                try {
                    Stop-Process -Id $_ -Force -ErrorAction Stop
                } catch {
                }
            }
    }
}

$dotenv = @{}
if (Test-Path -LiteralPath $backendEnvFile) {
    foreach ($line in Get-Content -LiteralPath $backendEnvFile) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
            $dotenv[$matches[1]] = $matches[2].Trim()
        }
    }
}

$frontendSupabaseUrl = $dotenv["SUPABASE_URL"]
$frontendSupabaseKey = $dotenv["SUPABASE_ANON_KEY"]
if ([string]::IsNullOrWhiteSpace($frontendSupabaseKey)) {
    $frontendSupabaseKey = $dotenv["SUPABASE_PUBLISHABLE_KEY"]
}

if (-not [string]::IsNullOrWhiteSpace($frontendSupabaseUrl) -and -not [string]::IsNullOrWhiteSpace($frontendSupabaseKey)) {
    @(
        "NEXT_PUBLIC_SUPABASE_URL=$frontendSupabaseUrl"
        "NEXT_PUBLIC_SUPABASE_ANON_KEY=$frontendSupabaseKey"
        "NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1"
    ) | Set-Content -LiteralPath $frontendEnvFile
}

Stop-LocalPortProcess -Ports @(8000, 3000)

"" | Set-Content -LiteralPath $backendLogFile
"" | Set-Content -LiteralPath $frontendLogFile

Start-Process cmd `
    -WindowStyle Hidden `
    -WorkingDirectory $backendDir `
    -ArgumentList @(
        "/c",
        ".\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > dev-backend.out.log 2>&1"
    )

Start-Process cmd `
    -WindowStyle Hidden `
    -WorkingDirectory $frontendDir `
    -ArgumentList @(
        "/c",
        "call npm run dev > dev-frontend.out.log 2>&1"
    )

Write-Host "Local backend starting at http://127.0.0.1:8000"
Write-Host "Local frontend starting at http://127.0.0.1:3000"
Write-Host "Logs: backend\dev-backend.out.log and frontend\dev-frontend.out.log"
