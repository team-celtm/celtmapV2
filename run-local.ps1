$ErrorActionPreference = "Stop"

$workspaceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $workspaceRoot "backend"
$frontendDir = Join-Path $workspaceRoot "frontend"
$backendEnvFile = Join-Path $backendDir ".env"
$frontendEnvFile = Join-Path $frontendDir ".env.local"

function Stop-StaleLocalDevProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Match
    )

    Get-CimInstance Win32_Process |
        Where-Object {
            $_.CommandLine -and $_.CommandLine -like "*$Match*"
        } |
        ForEach-Object {
            try {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
            } catch {
            }
        }
}

function Stop-LocalPortProcess {
    param(
        [Parameter(Mandatory = $true)]
        [int[]]$Ports
    )

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

function ConvertTo-PowerShellLiteral {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    return "'" + $Value.Replace("'", "''") + "'"
}

Stop-StaleLocalDevProcess -Match "$backendDir"
Stop-StaleLocalDevProcess -Match "$frontendDir"
Stop-StaleLocalDevProcess -Match "uvicorn app.main:app"
Stop-StaleLocalDevProcess -Match "npm run dev"
Stop-LocalPortProcess -Ports @(8000, 3000)

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

$redisUrl = $dotenv["REDIS_URL"]
$useConfiguredRedis = -not [string]::IsNullOrWhiteSpace($redisUrl) -and (
    $redisUrl -notmatch "localhost" -and $redisUrl -notmatch "127\.0\.0\.1"
)

$backendCommandParts = @()

foreach ($entry in $dotenv.GetEnumerator()) {
    if (-not [string]::IsNullOrWhiteSpace($entry.Value)) {
        $backendCommandParts += "`$env:$($entry.Key)=" + (ConvertTo-PowerShellLiteral -Value $entry.Value)
    }
}

$backendCommandParts += "`$env:APP_ENV='development'"
$backendCommandParts += "`$env:FRONTEND_ORIGIN='http://127.0.0.1:3000,http://localhost:3000'"

if ($useConfiguredRedis) {
    $backendCommandParts += "`$env:REDIS_ENABLED='true'"
    $backendCommandParts += "`$env:CELERY_EAGER_MODE='false'"
    $backendCommandParts += "`$env:REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS='3'"
    $backendCommandParts += "`$env:REDIS_SOCKET_TIMEOUT_SECONDS='3'"
} else {
    $backendCommandParts += "`$env:REDIS_ENABLED='false'"
    $backendCommandParts += "`$env:REDIS_FAIL_OPEN='true'"
    $backendCommandParts += "`$env:CELERY_EAGER_MODE='true'"
    $backendCommandParts += "`$env:REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS='0.2'"
    $backendCommandParts += "`$env:REDIS_SOCKET_TIMEOUT_SECONDS='0.2'"
}

$backendCommandParts += "& .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

$backendCommand = $backendCommandParts -join "; "

Start-Process powershell -WorkingDirectory $backendDir -ArgumentList "-NoExit", "-Command", $backendCommand
Start-Process powershell -WorkingDirectory $frontendDir -ArgumentList "-NoExit", "-Command", "npm run dev"

Write-Host "Local backend starting at http://127.0.0.1:8000"
Write-Host "Local frontend starting at http://127.0.0.1:3000"
