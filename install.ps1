[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$VenvPath = if ($env:VENV_PATH) { $env:VENV_PATH } else { Join-Path $ProjectRoot "backend\.venv" }

function Assert-NativeSuccess {
    param([string]$Activity)
    if ($LASTEXITCODE -ne 0) { throw "$Activity failed with exit code $LASTEXITCODE." }
}

function Resolve-Python {
    $candidates = @(
        @{ Command = "py"; Prefix = @("-3") },
        @{ Command = "python"; Prefix = @() },
        @{ Command = "python3"; Prefix = @() }
    )
    foreach ($candidate in $candidates) {
        if (Get-Command $candidate.Command -ErrorAction SilentlyContinue) {
            & $candidate.Command @($candidate.Prefix) -c "import sys; raise SystemExit(sys.version_info < (3, 10))" 2>$null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        }
    }
    throw "Python 3.10 or newer is required. Install it from python.org and enable the py launcher."
}

Write-Host "Installing Math Book Translator dependencies..."
$Python = Resolve-Python

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js 22.12 or newer is required." }
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(major > 22 || (major === 22 && minor >= 12) ? 0 : 1)'
if ($LASTEXITCODE -ne 0) { throw "Node.js 22.12 or newer is required; found $(node --version)." }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw "npm is required." }

Write-Host "Creating Python virtual environment at $VenvPath..."
& $Python.Command @($Python.Prefix) -m venv $VenvPath
Assert-NativeSuccess "Creating the Python virtual environment"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
Assert-NativeSuccess "Upgrading pip"
& $VenvPython -m pip install -r (Join-Path $ProjectRoot "backend\requirements.txt")
Assert-NativeSuccess "Installing backend dependencies"

Write-Host "Installing locked frontend dependencies..."
& npm.cmd --prefix (Join-Path $ProjectRoot "frontend") ci
Assert-NativeSuccess "Installing frontend dependencies"

Write-Host "Building the frontend..."
& npm.cmd --prefix (Join-Path $ProjectRoot "frontend") run build
Assert-NativeSuccess "Building the frontend"

Write-Host "Installation complete. Run .\run.ps1 to start the local application."
