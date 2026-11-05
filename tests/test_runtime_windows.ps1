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

# Exercise the real GUI launcher using a harmless fake bootstrap in a path
# with spaces and non-ASCII characters. Never update the runner's packages.
$temp = Join-Path ([System.IO.Path]::GetTempPath()) ('Semesterlista start å ' + [guid]::NewGuid())
try {
    New-Item (Join-Path $temp 'tools') -ItemType Directory -Force | Out-Null
    Copy-Item "$PSScriptRoot/../Starta Semesterlista.vbs" $temp
    @'
param([switch]$MaintenanceOnly)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WindowProbe {
    [DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow();
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
}
"@
@{ maintenance = [bool]$MaintenanceOnly;
   visible = [WindowProbe]::IsWindowVisible([WindowProbe]::GetConsoleWindow()) } |
   ConvertTo-Json | Set-Content (Join-Path $PSScriptRoot '../result.json') -Encoding UTF8
if ($MaintenanceOnly) { exit 0 }
exit 23
'@ | Set-Content (Join-Path $temp 'tools/start_semesterlista.ps1') -Encoding UTF8
    foreach ($maintenance in @($false, $true)) {
        $arguments = '//NoLogo "' + (Join-Path $temp 'Starta Semesterlista.vbs') + '"'
        if ($maintenance) { $arguments += ' /maintenance' }
        $process = Start-Process -FilePath "$env:SystemRoot/System32/wscript.exe" -ArgumentList $arguments -PassThru
        $null = $process.Handle  # Keep the handle available for ExitCode.
        if (-not $process.WaitForExit(30000)) {
            $process.Kill()
            throw 'Hidden launcher did not finish'
        }
        $expected = if ($maintenance) { 0 } else { 23 }
        if ($process.ExitCode -ne $expected) { throw "Launcher exit code: $($process.ExitCode), expected $expected" }
        $result = Get-Content (Join-Path $temp 'result.json') -Raw | ConvertFrom-Json
        if ($result.visible) { throw 'Bootstrap console is visible' }
        if ($result.maintenance -ne $maintenance) { throw 'Maintenance flag not forwarded' }
    }
} finally {
    Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host 'Hidden Windows launcher tests passed'

# Startup must not claim a weekly slot or upgrade existing Python, even if due.
$script:claims = 0
$script:upgrades = @()
$script:runtimeCalls = @()
function Claim-WeeklyMaintenance { $script:claims++; return $true }
function Update-Python($Python) { $script:upgrades += ,$Python; return $script:detectedPython }
function Invoke-RuntimeCheck($Python, [string[]]$Arguments = @()) {
    $script:runtimeCalls += ,@{ Python = $Python; Arguments = $Arguments }
    return 0
}
if ((Start-Runtime -Python $python) -ne 0) { throw 'Normal start failed' }
if ($script:claims -ne 0 -or $script:upgrades.Count -ne 0) { throw 'Startup attempted weekly/Python maintenance' }
if ($script:runtimeCalls.Count -ne 1 -or $script:runtimeCalls[0].Arguments.Count -ne 0) { throw 'Startup must use normal runtime with repair offer' }
if ($script:runtimeCalls[0].Python.executable -ne $python.executable) { throw 'Startup changed Python' }
if ((Start-Runtime -Python $python -Maintenance) -ne 0) { throw 'Maintenance failed' }
if ($script:claims -ne 1 -or $script:upgrades.Count -ne 1) { throw 'Separate weekly maintenance lost' }
if ($script:runtimeCalls[1].Arguments -notcontains '--maintenance-only') { throw 'Maintenance may not launch app' }
# Missing Python may be installed at first app launch, but not by the task.
$script:claims = 0
$script:upgrades = @()
$script:runtimeCalls = @()
Start-Runtime -Python $null -Maintenance | Out-Null
if ($script:claims -ne 0 -or $script:upgrades.Count -ne 0 -or $script:runtimeCalls.Count -ne 0) { throw 'Task installed missing Python' }
Start-Runtime -Python $null | Out-Null
if ($script:upgrades.Count -ne 1 -or $null -ne $script:upgrades[0]) { throw 'First installation path broken' }
if ($script:runtimeCalls[0].Arguments.Count -ne 0) { throw 'First launch forced package maintenance' }
# Runtime failures must propagate, not report success to the launcher.
function Invoke-RuntimeCheck { return 43 }
if ((Start-Runtime -Python $python) -ne 43) { throw 'Runtime error code lost' }
Write-Host 'Startup without Python upgrade tests passed'
