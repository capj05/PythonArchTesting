Write-Host "Running standard checks..."

$ErrorActionPreference = "Stop"
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $scriptPath ".venv"
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
$srcPath = Join-Path $scriptPath "src"
$script:ToolExitCode = 0
$exitCode = 0

function Invoke-QualityGate {
    param(
        [string]$Name,
        [string]$Executable,
        [string[]]$Arguments
    )

    Write-Host "Running $Name..."
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        $script:ToolExitCode = $LASTEXITCODE
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path $activateScript)) {
    Write-Error "Virtual environment activation script not found at $activateScript"
    exit 1
}

Push-Location $scriptPath
try {
    & $activateScript
    $env:PYTHONPATH = $srcPath

    Invoke-QualityGate -Name "pytest" -Executable "pytest.exe" -Arguments @(
        "tests/",
        "-v",
        "-n",
        "auto",
        "--cov=pythonarchtesting",
        "--cov-fail-under=80"
    )
    Invoke-QualityGate -Name "flake8" -Executable "flake8.exe" -Arguments @(
        "src/",
        "tests/"
    )
    Invoke-QualityGate -Name "black" -Executable "black.exe" -Arguments @(
        "--check",
        "src/",
        "tests/"
    )
    Invoke-QualityGate -Name "isort" -Executable "isort.exe" -Arguments @(
        "--check-only",
        "src/",
        "tests/"
    )
    Invoke-QualityGate -Name "mypy" -Executable "python.exe" -Arguments @(
        "-m",
        "mypy",
        "src/pythonarchtesting",
        "--ignore-missing-imports"
    )
    Invoke-QualityGate -Name "vulture" -Executable "vulture.exe" -Arguments @(
        "--min-confidence",
        "70",
        "src",
        "tests"
    )

    Write-Host "Standard checks completed."
}
catch {
    Write-Error $_
    if ($script:ToolExitCode -ne 0) {
        $exitCode = $script:ToolExitCode
    }
    else {
        $exitCode = 1
    }
}
finally {
    Pop-Location
}

exit $exitCode
