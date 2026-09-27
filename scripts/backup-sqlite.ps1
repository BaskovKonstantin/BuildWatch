param([string]$Target = "backups")
$root = Split-Path -Parent $PSScriptRoot
New-Item -ItemType Directory -Force (Join-Path $root $Target) | Out-Null
$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
Copy-Item (Join-Path $root "backend\buildwatch.db") (Join-Path $root "$Target\buildwatch-$stamp.db")
Write-Host "Backup created: $Target/buildwatch-$stamp.db"
