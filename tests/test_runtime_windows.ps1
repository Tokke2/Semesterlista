# Run on Windows CI without upgrading the runner's Python.
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/../tools/start_semesterlista.ps1" -FunctionsOnly
# Exercise real discovery against the runner, without running winget.
$discovered = Find-Python
if (-not $discovered -or -not (Test-Path $discovered.executable)) { throw 'Could not discover runner Python' }
$script:commands = @()
function Invoke-Winget([string[]]$Arguments) {
    $script:commands += ,$Arguments
    return 0
}
function Get-Command { return @{ Source = 'winget.exe' } }
$python = [pscustomobject]@{ major = 3; minor = 12; executable = 'C:\Python312\python.exe' }
$result = Update-Python $python
if ($result.executable -ne $python.executable) { throw 'Changed Python path' }
if ($script:commands.Count -ne 1) { throw 'Expected one upgrade' }
if ($script:commands[0][0] -ne 'upgrade') { throw 'Must not install over existing Python' }
if ($script:commands[0] -notcontains 'Python.Python.3.12') { throw 'Wrong series' }
# An unrecognized winget installation must not trigger an install fallback.
function Invoke-Winget([string[]]$Arguments) {
    if ($Arguments[0] -eq 'install') { throw 'Unexpected installation' }
    return 42
}
$result = Update-Python $python
if ($result.executable -ne $python.executable) { throw 'Lost existing Python on failure' }
# Install is allowed only when discovery returned no Python.
$script:commands = @()
function Invoke-Winget([string[]]$Arguments) { $script:commands += ,$Arguments; return 0 }
$script:detectedPython = $python
function Find-Python { return $script:detectedPython }
$result = Update-Python $null
if ($script:commands[0][0] -ne 'install') { throw 'Missing Python should be installed' }
Write-Host 'Windows runtime bootstrap tests passed'

# Weekly boundary and persistence: local Monday 08:00, including catch-up.
if ((Get-WeeklySlot ([datetime]'2026-11-09T07:59:00')) -ne '2026-11-02') { throw 'Before Monday 8 boundary' }
if ((Get-WeeklySlot ([datetime]'2026-11-09T08:00:00')) -ne '2026-11-09') { throw 'Monday 8 boundary' }
if ((Get-WeeklySlot ([datetime]'2026-11-15T23:59:00')) -ne '2026-11-09') { throw 'Sunday catch-up boundary' }
$temp = Join-Path ([System.IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
try {
    if (-not (Claim-WeeklyMaintenance $temp ([datetime]'2026-11-09T08:00:00'))) { throw 'First weekly attempt required' }
    if (Claim-WeeklyMaintenance $temp ([datetime]'2026-11-10T12:00:00')) { throw 'Repeated attempt in same week' }
    if (Claim-WeeklyMaintenance $temp ([datetime]'2026-11-16T07:59:00')) { throw 'Too early on next Monday' }
    if (-not (Claim-WeeklyMaintenance $temp ([datetime]'2026-11-16T08:00:00'))) { throw 'Next week should be due' }
} finally {
    Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host 'Weekly schedule tests passed'
