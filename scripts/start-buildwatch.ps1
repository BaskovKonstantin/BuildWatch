param(
  [int]$ApiPort = 8600,
  [int]$WebPort = 8700
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$api = Get-NetTCPConnection -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue
$web = Get-NetTCPConnection -LocalPort $WebPort -State Listen -ErrorAction SilentlyContinue
if ($api -or $web) { throw "Порт уже занят. API=$ApiPort WEB=$WebPort" }
$logs = Join-Path $root "runtime-logs"
New-Item -ItemType Directory -Force $logs | Out-Null
Start-Process python -ArgumentList "-m","uvicorn","app:app","--host","127.0.0.1","--port",$ApiPort `
  -WorkingDirectory (Join-Path $root "backend") `
  -RedirectStandardOutput (Join-Path $logs "api.out.log") `
  -RedirectStandardError (Join-Path $logs "api.err.log") | Out-Null
$workerPython = Join-Path $root ".venv-cpu\Scripts\python.exe"
if (-not (Test-Path $workerPython)) { $workerPython = "python" }
Start-Process $workerPython -ArgumentList "scripts\worker.py" -WorkingDirectory $root `
  -RedirectStandardOutput (Join-Path $logs "worker.out.log") `
  -RedirectStandardError (Join-Path $logs "worker.err.log") | Out-Null
Start-Process npm.cmd -ArgumentList "run","dev","--","--port",$WebPort `
  -WorkingDirectory (Join-Path $root "frontend") `
  -RedirectStandardOutput (Join-Path $logs "web.out.log") `
  -RedirectStandardError (Join-Path $logs "web.err.log") | Out-Null
Start-Sleep 3
$health = Invoke-WebRequest "http://127.0.0.1:$ApiPort/api/health" -UseBasicParsing
if ($health.StatusCode -ne 200) { throw "API health-check failed" }
Write-Host "BuildWatch запущен: http://127.0.0.1:$WebPort"
Write-Host "API: http://127.0.0.1:$ApiPort"
