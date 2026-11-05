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
    # Compatibility name: never upgrade an existing interpreter.
    if ($Python) { return $Python }
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) { throw 'Python saknas. Installera Python från python.org eller Windows App Installer (winget).' }
    $code = Invoke-Winget -Arguments @('install', '--id', 'Python.Python.3.14', '--exact',
        '--source', 'winget', '--scope', 'user', '--silent',
        '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity')
    if ($code -ne 0) { throw "Python kunde inte installeras (kod $code)." }
    $Python = Find-Python
    if (-not $Python) { throw 'Python installerades men hittades inte. Starta om startprogrammet.' }
    return $Python
}

function Remove-LegacyMaintenance {
    # Only remove our known task when its action targets THIS installation.
    # Never delete unrelated tasks, or a task belonging to another app folder.
    try {
        $name = 'Semesterlista - veckounderhall'
        $existing = Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction SilentlyContinue
        if (-not $existing) { return $true }
        $knownArguments = @(
            ('//NoLogo "' + (Join-Path $Root 'Starta Semesterlista.vbs') + '" /maintenance'),
            ('-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $Root 'tools\start_semesterlista.ps1') + '" -MaintenanceOnly')
        )
        if (@($existing.Actions).Count -ne 1 -or $existing.Actions.Arguments -notin $knownArguments) { return $true }
        Disable-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop | Out-Null
        Unregister-ScheduledTask -TaskName $name -TaskPath '\' -Confirm:$false -ErrorAction Stop
        return $true
    } catch {
        Write-Warning "Det gamla veckoschemat kunde inte tas bort. Avaktivera 'Semesterlista - veckounderhall' i Schemaläggaren. $_"
        return $false
    }
}

function Invoke-RuntimeCheck($Python, [string[]]$Arguments = @()) {
    & $Python.executable (Join-Path $PSScriptRoot 'runtime_check.py') @Arguments | Out-Host
    return $LASTEXITCODE
}

function Start-Runtime($Python, [switch]$Maintenance) {
    # Old task/manual maintenance invocations must do nothing, even if task
    # removal was denied. No discovery, upgrades or package maintenance.
    if ($Maintenance) { return 0 }
    # First installation remains possible only if no Python exists at all.
    # No weekly catch-up and no upgrade of existing Python during app startup.
    if (-not $Python) { $Python = Update-Python $null }
    return (Invoke-RuntimeCheck -Python $Python)
}

if ($FunctionsOnly) { return }
$removed = Remove-LegacyMaintenance
if ($MaintenanceOnly) { exit 0 }
if (-not $removed) {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show(
            "Det gamla veckoschemat kunde inte tas bort. Avaktivera 'Semesterlista - veckounderhall' i Schemaläggaren. Appen kan ändå startas och gamla underhållsanrop gör inget.",
            'Semesterlista') | Out-Null
    } catch { }
}
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
