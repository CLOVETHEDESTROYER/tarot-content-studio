param([Parameter(Mandatory=$true)][string]$Plan)
$ErrorActionPreference = 'Stop'
$install = Get-Content -LiteralPath $Plan -Raw | ConvertFrom-Json
$installParent = [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($install.target))
if ([IO.Path]::GetFileName($install.target) -ne 'StarPower Content Studio') { throw 'Unexpected app target' }
foreach ($entry in @(@($install.staged,'.starpower-incoming-'),@($install.previous,'.starpower-previous-'))) {
    $resolved = [IO.Path]::GetFullPath($entry[0])
    if ([IO.Path]::GetDirectoryName($resolved) -ne $installParent -or -not [IO.Path]::GetFileName($resolved).StartsWith($entry[1])) { throw 'Unsafe installer path' }
}
$deadline = [DateTime]::UtcNow.AddSeconds(180)
while (Get-Process -Id $install.pid -ErrorAction SilentlyContinue) {
    if ([DateTime]::UtcNow -gt $deadline) { throw 'App did not exit; installed files unchanged' }
    Start-Sleep -Milliseconds 300
}
$env:STUDIO_DATA_DIR = $install.data
$env:STUDIO_EXPORT_DIR = $install.exports
$env:PYINSTALLER_RESET_ENVIRONMENT = '1'
$newProcess = $null
try {
    Move-Item -LiteralPath $install.target -Destination $install.previous
    Move-Item -LiteralPath $install.staged -Destination $install.target
    $binary = Join-Path $install.target 'StarPower Content Studio.exe'
    $launchArgs = '--update-health "' + $install.health + '"'
    $newProcess = Start-Process -FilePath $binary -ArgumentList $launchArgs -PassThru
    $deadline = [DateTime]::UtcNow.AddSeconds(90)
    $healthy = $false
    while ([DateTime]::UtcNow -lt $deadline -and -not $newProcess.HasExited) {
        if (Test-Path -LiteralPath $install.health) {
            $health = Get-Content -LiteralPath $install.health -Raw | ConvertFrom-Json
            if ($health.passed -and $health.version -eq $install.version -and $health.appPath -eq $install.target) { $healthy = $true; break }
        }
        Start-Sleep -Milliseconds 500
        $newProcess.Refresh()
    }
    if (-not $healthy) { throw 'New app did not confirm healthy startup' }
    'Update installed; previous app retained at ' + $install.previous | Set-Content -LiteralPath (Join-Path $install.recovery 'result.txt')
} catch {
    $failure = $_.Exception.Message
    if ($newProcess -and -not $newProcess.HasExited) { Stop-Process -Id $newProcess.Id; $newProcess.WaitForExit(15000) | Out-Null }
    if (Test-Path -LiteralPath $install.previous) {
        if (Test-Path -LiteralPath $install.target) {
            $failedTarget = Join-Path $installParent ('.starpower-failed-' + [guid]::NewGuid().ToString('N'))
            Move-Item -LiteralPath $install.target -Destination $failedTarget
        }
        Move-Item -LiteralPath $install.previous -Destination $install.target
        Start-Process -FilePath (Join-Path $install.target 'StarPower Content Studio.exe')
    }
    'Rolled back app only; current history preserved. ' + $failure | Set-Content -LiteralPath (Join-Path $install.recovery 'result.txt')
}
