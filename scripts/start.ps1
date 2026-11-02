$ErrorActionPreference = 'Stop'
$studioRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $studioRoot
if (-not (Test-Path -LiteralPath 'frontend/dist/index.html')) { throw 'Build the editor first with Setup Content Studio.cmd.' }
try {
    $status = Invoke-RestMethod -Uri 'http://127.0.0.1:5057/api/config' -TimeoutSec 2
    if ($status.version) { Start-Process 'http://127.0.0.1:5057'; exit 0 }
} catch {}
Write-Host 'Opening StarPower Content Studio at http://127.0.0.1:5057'
Write-Host 'Keep this window open while creating and exporting videos. Press Ctrl+C to stop.'
$studioPython = Join-Path $studioRoot '.venv/Scripts/python.exe'
$browserStarter = Start-Job -ScriptBlock { Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:5057' }
try { & $studioPython app.py } finally { Remove-Job -Job $browserStarter -Force -ErrorAction SilentlyContinue }
