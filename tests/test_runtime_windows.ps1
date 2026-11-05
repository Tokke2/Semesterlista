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
