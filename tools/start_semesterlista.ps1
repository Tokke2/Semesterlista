# Windows entry point: runs before any application packages are imported.
param([switch]$FunctionsOnly, [switch]$MaintenanceOnly)
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent

function Find-Python {
    $candidates = @()
    $storePackages = @(Get-AppxPackage -Name 'PythonSoftwareFoundation.Python.*' -ErrorAction SilentlyContinue)
    foreach ($package in $storePackages) {
        $storePython = Join-Path $package.InstallLocation 'python.exe'
        if (Test-Path $storePython) { $candidates += ,@($storePython) }
    }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) { $candidates += ,@($launcher.Source, '-3') }
    foreach ($name in @('python.exe', 'python3.exe')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command -and $command.Source -notlike '*\WindowsApps\*') {
            $candidates += ,@($command.Source)
        }
    }
    foreach ($key in @('HKCU:\Software\Python\PythonCore',
                       'HKLM:\Software\Python\PythonCore',
                       'HKLM:\Software\WOW6432Node\Python\PythonCore')) {
        foreach ($version in @(Get-ChildItem $key -ErrorAction SilentlyContinue)) {
            $install = Get-ItemProperty ($version.PSPath + '\InstallPath') -ErrorAction SilentlyContinue
            if ($install -and $install.'(default)') {
                $exe = Join-Path $install.'(default)' 'python.exe'
                if (Test-Path $exe) { $candidates += ,@($exe) }
            }
        }
    }
    foreach ($candidate in $candidates) {
        try {
            $exe = $candidate[0]
            $arguments = @($candidate | Select-Object -Skip 1)
            $json = & $exe @arguments -c "import json,sys; print(json.dumps(dict(executable=getattr(sys,'_base_executable',sys.executable),major=sys.version_info[0],minor=sys.version_info[1])))" 2>$null
            if ($LASTEXITCODE -eq 0) { return ($json | ConvertFrom-Json) }
        } catch { }
    }
    $registered = @(Get-ItemProperty -Path @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    ) -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match '^(Python [0-9]|Anaconda|Miniconda)' })
    if ($candidates.Count -gt 0 -or $storePackages.Count -gt 0 -or $registered.Count -gt 0) {
        throw 'Python hittades men kunde inte startas. Reparera installationen; ingen extra kopia installeras.'
    }
    return $null
}

function Invoke-Winget([string[]]$Arguments) {
    # Do not hang application startup indefinitely on network/UAC problems.
    $process = Start-Process -FilePath 'winget.exe' -ArgumentList $Arguments -PassThru -NoNewWindow
    if (-not $process.WaitForExit(180000)) {
        $process.Kill()
        throw 'Python-kontrollen tog för lång tid.'
    }
    return $process.ExitCode
}

function Update-Python($Python) {
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $Python) {
        if (-not $winget) { throw 'Python saknas. Installera Python från python.org eller installera Windows App Installer (winget).' }
        # Supported stable baseline, not preview/nightly. Only this branch installs.
        $code = Invoke-Winget -Arguments @('install', '--id', 'Python.Python.3.14', '--exact',
            '--source', 'winget', '--scope', 'user', '--silent',
            '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity')
        if ($code -ne 0) { throw "Python kunde inte installeras (kod $code)." }
        $Python = Find-Python
        if (-not $Python) { throw 'Python installerades men hittades inte. Starta om startprogrammet.' }
        return $Python
    }
    if ($Python.major -ne 3 -or $Python.minor -lt 10) {
        throw 'Befintlig Python är för gammal (minst 3.10 krävs). Uppgradera den manuellt; ingen extra kopia installeras.'
    }
    if ($winget) {
        try {
            $id = "Python.Python.$($Python.major).$($Python.minor)"
            # Upgrade ONLY the installed series. Never fall back to install.
            $code = Invoke-Winget -Arguments @('upgrade', '--id', $id, '--exact', '--source', 'winget',
                '--silent', '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity')
            if ($code -ne 0) { Write-Host "Ingen Python-uppgradering utförd (winget-kod $code). Befintlig Python behålls." }
        } catch { Write-Warning "Python kunde inte uppdateras: $_. Befintlig installation behålls." }
    } else {
        Write-Warning 'winget saknas; Python-versionen kan inte uppdateras automatiskt.'
    }
    return $Python
}

function Get-WeeklySlot([datetime]$Now = (Get-Date)) {
    $days = (([int]$Now.DayOfWeek + 6) % 7)
    $slot = $Now.Date.AddDays(-$days).AddHours(8)
    if ($Now -lt $slot) { $slot = $slot.AddDays(-7) }
    return $slot.ToString('yyyy-MM-dd')
}

function Claim-WeeklyMaintenance([string]$Directory, [datetime]$Now = (Get-Date)) {
    # Called only while owning the mutex. Record attempts, also when offline,
    # to avoid repeating update requests on every subsequent application start.
    $state = Join-Path $Directory 'data\runtime-weekly.json'
    $slot = Get-WeeklySlot $Now
    if (Test-Path $state) {
        try {
            $saved = Get-Content $state -Raw | ConvertFrom-Json
            if ($saved.slot -ge $slot) { return $false }
        } catch { Write-Warning 'Veckostatus kunde inte läsas; en ny kontroll görs.' }
    }
    New-Item (Split-Path $state) -ItemType Directory -Force | Out-Null
    $temporary = "$state.tmp"
    @{ slot = $slot; attempted_at = $Now.ToString('o') } | ConvertTo-Json | Set-Content $temporary -Encoding UTF8
    Move-Item $temporary $state -Force
    return $true
}

function Register-WeeklyMaintenance {
    # Current user, no elevation. Maintenance is separate from app startup.
    # Never stop a running app to update its loaded libraries.
    try {
        $scriptPath = Join-Path $Root 'Starta Semesterlista.vbs'
        $arguments = '//NoLogo "' + $scriptPath + '" /maintenance'
        $hostPath = Join-Path $env:SystemRoot 'System32\wscript.exe'
        $name = 'Semesterlista - veckounderhall'
        $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if ($existing -and $existing.Actions.Arguments -eq $arguments -and $existing.Actions.Execute -eq $hostPath) { return }
        $action = New-ScheduledTaskAction -Execute $hostPath -Argument $arguments
        $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At '08:00'
        $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
        $user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
        Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
    } catch { Write-Warning "Veckoschemat kunde inte registreras. Appen startar utan uppdatering. $_" }
}

function Invoke-RuntimeCheck($Python, [string[]]$Arguments = @()) {
    & $Python.executable (Join-Path $PSScriptRoot 'runtime_check.py') @Arguments | Out-Host
    return $LASTEXITCODE
}

function Start-Runtime($Python, [switch]$Maintenance) {
    if ($Maintenance) {
        # Only the separate maintenance invocation may claim a weekly slot
        # and upgrade an existing interpreter. Never install Python in a task.
        if (-not $Python) { return 0 }
        if (-not (Claim-WeeklyMaintenance $Root)) { return 0 }
        Write-Host 'Veckokontroll: uppdaterar befintlig Python och dess tillägg...'
        $Python = Update-Python $Python
        return (Invoke-RuntimeCheck -Python $Python -Arguments @('--maintenance-only'))
    }
    # First installation remains possible only if no Python exists at all.
    # No weekly catch-up and no upgrade of existing Python during app startup.
    if (-not $Python) { $Python = Update-Python $null }
    return (Invoke-RuntimeCheck -Python $Python)
}

if ($FunctionsOnly) { return }
if (-not $MaintenanceOnly) { Register-WeeklyMaintenance }
$mutex = New-Object System.Threading.Mutex($false, 'Local\SemesterlistaRuntimeMaintenance')
$owned = $false
try {
    try { $owned = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $owned = $true }
    # Allow an updating/restarting app a moment to release its old mutex.
    if (-not $owned -and -not $MaintenanceOnly) {
        try { $owned = $mutex.WaitOne(2000) } catch [System.Threading.AbandonedMutexException] { $owned = $true }
    }
    $python = Find-Python
    if (-not $owned) {
        if ($MaintenanceOnly) { exit 0 }
        if (-not $python) { throw 'En startkontroll pågår redan. Försök igen när den är klar.' }
        & $python.executable (Join-Path $PSScriptRoot 'runtime_check.py') --no-repair
        exit $LASTEXITCODE
    }
    $code = Start-Runtime -Python $python -Maintenance:$MaintenanceOnly
    if ($code -eq 43) { exit 1 } # Python already displayed the error.
    if ($code -ne 0) { throw 'Semesterlista kunde inte startas/uppdateras. Se data/loggar/app.log.' }
} catch {
    Write-Host "Startfel: $_" -ForegroundColor Red
    if (-not $MaintenanceOnly) {
        try {
            Add-Type -AssemblyName System.Windows.Forms
            [System.Windows.Forms.MessageBox]::Show("Startfel: $_", 'Semesterlista') | Out-Null
        } catch { }
    }
    exit 1
} finally {
    if ($owned) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
