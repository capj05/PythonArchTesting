Write-Host "Running full checks..."

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
    $standardScript = Join-Path $scriptPath "check_standard.ps1"
    & $standardScript
    if ($LASTEXITCODE -ne 0) {
        $exitCode = $LASTEXITCODE
        throw "Standard checks failed with exit code $LASTEXITCODE"
    }

    & $activateScript
    $env:PYTHONPATH = $srcPath

    Invoke-QualityGate -Name "radon" -Executable "radon.exe" -Arguments @(
        "cc",
        "-nc",
        "src/",
        "tests/"
    )
    Invoke-QualityGate -Name "pylint" -Executable "pylint.exe" -Arguments @(
        "--disable=all",
        "--enable=C0901,R0912,R0915,R0903",
        "src/"
    )
    Invoke-QualityGate -Name "bandit" -Executable "bandit.exe" -Arguments @(
        "-r",
        "src/"
    )

    Write-Host "Full checks completed."
}
catch {
    Write-Error $_
    if ($exitCode -eq 0) {
        if ($script:ToolExitCode -ne 0) {
            $exitCode = $script:ToolExitCode
        }
        else {
            $exitCode = 1
        }
    }
}
finally {
    Pop-Location
}

exit $exitCode
