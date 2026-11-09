# Run on Windows CI without upgrading the runner's Python.
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/../tools/start_semesterlista.ps1" -FunctionsOnly
# Exercise real discovery against the runner, without running winget.
$discovered = Find-Python
if (-not $discovered -or -not (Test-Path $discovered.executable)) { throw 'Could not discover runner Python' }
# The choice must depend on compatibility, not registry/PATH enumeration order.
$p315 = [pscustomobject]@{ major=3; minor=15; executable='C:\Python315\python.exe'; ready=$true }
$p314 = [pscustomobject]@{ major=3; minor=14; executable='C:\Python314\python.exe'; ready=$true }
$p312 = [pscustomobject]@{ major=3; minor=12; executable='C:\Python312\python.exe'; ready=$true }
$p39 = [pscustomobject]@{ major=3; minor=9; executable='C:\Python39\python.exe'; ready=$true }
if ((Select-CompatiblePython @($p312,$p314,$p315)).minor -ne 15) { throw 'Working 3.15 not preferred' }
$p315.ready = $false
if ((Select-CompatiblePython @($p315,$p312,$p314)).minor -ne 14) { throw '3.14 fallback broken' }
$p314.ready = $false
if ((Select-CompatiblePython @($p315,$p314,$p312)).minor -ne 12) { throw 'Other installed Python fallback broken' }
$p312.ready = $false
if ((Select-CompatiblePython @($p315,$p314,$p312)).minor -ne 14) { throw 'Repair should prefer stable existing fallback' }
if ($null -ne (Select-CompatiblePython @($p39))) { throw 'Unsupported Python 3.9 selected' }
if ($null -ne (Get-PythonInfo -Executable 'C:\missing-python-for-test\python.exe')) { throw 'Broken executable accepted' }
Write-Host 'Python 3.15 / 3.14 / system fallback tests passed'
$script:commands = @()
function Invoke-Winget([string[]]$Arguments) { $script:commands += ,$Arguments; return 0 }
function Get-Command { return @{ Source = 'winget.exe' } }
$python = [pscustomobject]@{ major = 3; minor = 12; executable = 'C:\Python312\python.exe' }
$result = Update-Python $python
if ($result.executable -ne $python.executable -or $script:commands.Count -ne 0) { throw 'Existing Python must never be upgraded' }
$script:detectedPython = $python
function Find-Python { return $script:detectedPython }
$result = Update-Python $null
if ($script:commands.Count -ne 1 -or $script:commands[0][0] -ne 'install') { throw 'First installation broken' }
Write-Host 'No automatic Python upgrade tests passed'

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

# Normal start still uses the runtime with its interactive repair offer.
$script:runtimeCalls = @()
function Invoke-RuntimeCheck($Python, [string[]]$Arguments = @()) {
    $script:runtimeCalls += ,@{ Python = $Python; Arguments = $Arguments }
    return 0
}
if ((Start-Runtime -Python $python) -ne 0) { throw 'Normal start failed' }
if ($script:runtimeCalls.Count -ne 1 -or $script:runtimeCalls[0].Arguments.Count -ne 0) { throw 'Normal repair path lost' }
$script:runtimeCalls = @()
$script:commands = @()
Start-Runtime -Python $python -Maintenance | Out-Null
Start-Runtime -Python $null -Maintenance | Out-Null
if ($script:runtimeCalls.Count -ne 0 -or $script:commands.Count -ne 0) { throw 'Retired maintenance did work' }

# Task removal is confined to our exact name/path/action; mock all OS changes.
$script:task = $null
$script:disabled = 0
$script:deleted = 0
function Get-ScheduledTask { return $script:task }
function Disable-ScheduledTask { $script:disabled++ }
function Unregister-ScheduledTask { $script:deleted++ }
if (-not (Remove-LegacyMaintenance)) { throw 'No-task cleanup failed' }
if ($script:deleted -ne 0) { throw 'Deleted a nonexistent task' }
foreach ($arguments in @(
    ('//NoLogo "' + (Join-Path $Root 'Starta Semesterlista.vbs') + '" /maintenance'),
    ('-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $Root 'tools\start_semesterlista.ps1') + '" -MaintenanceOnly')
)) {
    $script:task = [pscustomobject]@{ Actions = [pscustomobject]@{ Arguments = $arguments } }
    if (-not (Remove-LegacyMaintenance)) { throw 'Known task cleanup failed' }
}
if ($script:deleted -ne 2 -or $script:disabled -ne 2) { throw 'Both legacy formats must be disabled and deleted' }
$script:task = [pscustomobject]@{ Actions = [pscustomobject]@{ Arguments = 'another app folder' } }
Remove-LegacyMaintenance | Out-Null
if ($script:deleted -ne 2) { throw 'Unrelated task removed' }
$script:task = [pscustomobject]@{ Actions = [pscustomobject]@{ Arguments = $arguments } }
function Disable-ScheduledTask { throw 'Access denied' }
if (Remove-LegacyMaintenance) { throw 'Permission error hidden' }
if ($script:deleted -ne 2) { throw 'Deletion attempted after disable failed' }
Write-Host 'Retired scheduler and safe cleanup tests passed'

# The generated shortcut must carry the app icon, not a Python/WSH icon.
$temp = Join-Path ([System.IO.Path]::GetTempPath()) ('Semesterlista icon ' + [guid]::NewGuid())
$originalRoot = $Root
try {
    New-Item (Join-Path $temp 'assets/ikon') -ItemType Directory -Force | Out-Null
    Copy-Item (Join-Path $Root 'assets/ikon/appikon.ico') (Join-Path $temp 'assets/ikon/appikon.ico')
    $Root = $temp
    Ensure-AppShortcut
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut((Join-Path $temp 'Semesterlista.lnk'))
    if ($link.IconLocation -ne ((Join-Path $temp 'assets/ikon/appikon.ico') + ',0')) { throw 'Shortcut icon missing' }
    if ($link.Arguments -notlike '*Starta Semesterlista.vbs*') { throw 'Wrong shortcut target' }
    if ($link.WorkingDirectory -ne $temp) { throw 'Wrong shortcut working directory' }
} finally {
    $Root = $originalRoot
    Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host 'App shortcut icon tests passed'
