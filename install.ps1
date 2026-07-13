<#
.SYNOPSIS
    Updater installer - installs via pipx and sets up global config.

.DESCRIPTION
    1. Checks Python >= 3.11.
    2. Installs pipx if missing and adds its folders to PATH.
    3. Installs the package from the current directory (editable) via pipx.
    4. Copies UPDATER_OPENAI_API_KEY (and other UPDATER_*) from the local .env
       into the global ~/.updater/.env so AI commands work from any directory.
    5. Verifies that `updater` is available.

.PARAMETER Force
    Reinstall the package even if already installed.

.EXAMPLE
    .\install.ps1
    .\install.ps1 -Force
#>

[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Step([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "    $msg" -ForegroundColor Yellow }
function Write-Err([string]$msg)  { Write-Host "    $msg" -ForegroundColor Red }

# -- 1. Python --
Write-Step "Checking Python"
$py = (python --version 2>&1)
if ($LASTEXITCODE -ne 0) {
    Write-Err "Python not found. Install Python >= 3.11 and add to PATH."
    exit 1
}
$pyVer = ($py -replace "Python ", "")
$pyMajor = [int]($pyVer.Split(".")[0])
$pyMinor = [int]($pyVer.Split(".")[1])
if ($pyMajor -lt 3 -or ($pyMajor -eq 3 -and $pyMinor -lt 11)) {
    Write-Err "Need Python >= 3.11, found $pyVer"
    exit 1
}
Write-Ok "Python $pyVer"

# -- 2. pipx --
Write-Step "Checking pipx"
$pipxCmd = $null
$pipxOnPath = Get-Command pipx -ErrorAction SilentlyContinue
if ($pipxOnPath) {
    $pipxCmd = "pipx"
    Write-Ok "pipx already on PATH"
} else {
    $scriptsDir = (& python -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>$null).Trim()
    $candidate = Join-Path $scriptsDir "pipx.exe"
    if (Test-Path $candidate) {
        $pipxCmd = $candidate
        Write-Ok "pipx found: $candidate"
    } else {
        Write-Warn "pipx not found - installing..."
        python -m pip install pipx 2>&1 | Out-Null
        $pipxCmd = Join-Path $scriptsDir "pipx.exe"
        if (-not (Test-Path $pipxCmd)) {
            Write-Err "Failed to install pipx"
            exit 1
        }
        Write-Ok "pipx installed"
    }
}

# ensurepath (adds ~/.local/bin to user PATH)
$ErrorActionPreference = "Continue"
& $pipxCmd ensurepath 2>&1 | Out-Null
$ErrorActionPreference = "Stop"
# Refresh PATH for the current session
$userBin = Join-Path $env:USERPROFILE ".local\bin"
if ($env:Path -notlike "*$userBin*") {
    $env:Path = "$userBin;" + $env:Path
}

# -- 3. Install package via pipx --
Write-Step "Installing package via pipx"
$updaterInstalled = Get-Command updater -ErrorAction SilentlyContinue
if ($updaterInstalled -and -not $Force) {
    Write-Ok "updater already installed (use -Force to reinstall)"
} else {
    if ($updaterInstalled -and $Force) {
        Write-Warn "Reinstalling (--Force)..."
        $ErrorActionPreference = "Continue"
    & $pipxCmd uninstall updater 2>&1 | Out-Null
    $ErrorActionPreference = "Stop"
    }
    $ErrorActionPreference = "Continue"
    & $pipxCmd install --editable $ProjectRoot --force 2>&1 | Out-Null
    $ErrorActionPreference = "Stop"
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "Package installed"
    } else {
        Write-Err "pipx install failed"
        exit 1
    }
}

# -- 4. Global config ~/.updater/.env --
Write-Step "Setting up global config"
$updaterHome = Join-Path $env:USERPROFILE ".updater"
if (-not (Test-Path $updaterHome)) {
    New-Item -ItemType Directory -Path $updaterHome -Force | Out-Null
}
$globalEnv = Join-Path $updaterHome ".env"
$localEnv  = Join-Path $ProjectRoot ".env"

# Collect UPDATER_* variables: local .env first, then process env overrides
$configVars = [ordered]@{}

# 4a. From local .env (if present)
if (Test-Path $localEnv) {
    Get-Content $localEnv | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#")) {
            $idx = $line.IndexOf("=")
            if ($idx -gt 0) {
                $k = $line.Substring(0, $idx).Trim()
                $v = $line.Substring($idx + 1).Trim()
                if ($k -like "UPDATER_*") {
                    $configVars[$k] = $v
                }
            }
        }
    }
    Write-Ok "Read local .env"
}

# 4b. From process environment (overrides .env)
Get-ChildItem env: | Where-Object { $_.Name -like "UPDATER_*" } | ForEach-Object {
    $configVars[$_.Name] = $_.Value
}

# 4c. Persist to global .env
if ($configVars.Count -gt 0) {
    $lines = @()
    foreach ($k in ($configVars.Keys | Sort-Object)) {
        $lines += "$k=$($configVars[$k])"
    }
    $content = ($lines -join "`n") + "`n"
    # Write as UTF-8 WITHOUT BOM (PowerShell 5.1's Set-Content -Encoding UTF8 adds BOM,
    # which breaks pydantic-settings parsing of the first key).
    [System.IO.File]::WriteAllText($globalEnv, $content, (New-Object System.Text.UTF8Encoding $false))
    Write-Ok "Global config: $globalEnv ($($configVars.Count) vars)"
} else {
    Write-Warn "UPDATER_OPENAI_API_KEY not found in .env or environment."
    Write-Warn "AI commands (suggest, migrate) won't work until a key is set."
    Write-Warn "Create $globalEnv or set UPDATER_OPENAI_API_KEY env var."
}

# -- 5. Verify --
Write-Step "Verifying installation"
$updaterBin = Join-Path $userBin "updater.exe"
if (Test-Path $updaterBin) {
    Write-Ok "updater available: $updaterBin"
} elseif (Get-Command updater -ErrorAction SilentlyContinue) {
    Write-Ok "updater available on PATH"
} else {
    Write-Warn "updater not found on PATH. Open a NEW terminal and retry:"
    Write-Warn "  updater --help"
}

Write-Host ""
Write-Host "Installation complete." -ForegroundColor Green
Write-Host "Open a new terminal and run:" -ForegroundColor Green
Write-Host "  updater --help" -ForegroundColor White
Write-Host "  updater scan run <path-to-project>" -ForegroundColor White