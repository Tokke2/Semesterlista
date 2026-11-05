# Windows entry point: runs before any application packages are imported.
param([switch]$FunctionsOnly)
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent

function Find-Python {
    $candidates = @()
    $venvPython = Join-Path $Root '.venv\Scripts\python.exe'
    if (Test-Path $venvPython) { $candidates += ,@($venvPython) }
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
            if ($install) {
                $exe = Join-Path $install.'(default)' 'python.exe'
                if (Test-Path $exe) { $candidates += ,@($exe) }
            }
        }
    }
    foreach ($candidate in $candidates) {
        try {
            $exe = $candidate[0]
            $arguments = @($candidate | Select-Object -Skip 1)
            $json = & $exe @arguments -c 'import json,sys; print(json.dumps(dict(executable=getattr(sys,"_base_executable",sys.executable),major=sys.version_info[0],minor=sys.version_info[1])))' 2>$null
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

if ($FunctionsOnly) { return }
$mutex = New-Object System.Threading.Mutex($false, 'Local\SemesterlistaRuntimeMaintenance')
$owned = $false
try {
    try { $owned = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $owned = $true }
    if (-not $owned) {
        # An instance is running: do not modify packages it has loaded.
        $existing = Join-Path $Root '.venv\Scripts\pythonw.exe'
        if (-not (Test-Path $existing)) { throw 'En startkontroll pågår redan. Försök igen när den är klar.' }
        $env:SEMESTERLISTA_RUNTIME_READY = '1'
        & $existing (Join-Path $Root 'main.pyw')
        exit 0
    }
    Write-Host 'Kontrollerar Python och Semesterlistas tillägg...'
    $python = Update-Python (Find-Python)
    & $python.executable (Join-Path $PSScriptRoot 'runtime_check.py')
    if ($LASTEXITCODE -ne 0) { throw 'Semesterlista kunde inte startas. Se data/loggar/app.log.' }
} catch {
    Write-Host "Startfel: $_" -ForegroundColor Red
    exit 1
} finally {
    if ($owned) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
