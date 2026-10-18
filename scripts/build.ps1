$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $buildPython = Join-Path $projectRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $buildPython)) {
        throw 'Create .venv and install build dependencies first; see README.md.'
    }
    # Build and validate before closing the user's current workbench.
    $releaseDir = Join-Path $projectRoot '.local/release'
    $stagedExe = Join-Path $releaseDir 'cli.exe'
    $targetExe = [System.IO.Path]::GetFullPath((Join-Path $projectRoot 'cli.exe'))
    $backupExe = Join-Path $releaseDir 'cli.previous.exe'
    & $buildPython -m PyInstaller --noconfirm --onefile --console --name cli --distpath $releaseDir --workpath .local/build --specpath .local cli.py
    if ($LASTEXITCODE -ne 0) { throw 'cli.exe build failed.' }
    & $stagedExe --help
    if ($LASTEXITCODE -ne 0) { throw 'Built executable failed its startup check; existing cli.exe was preserved.' }
    $expectedHash = (Get-FileHash -LiteralPath $stagedExe -Algorithm SHA256).Hash

    # PyInstaller onefile has both a launcher and a child with this exact path.
    # Do not stop unrelated programs that happen to have the same process name.
    $runningCli = @(Get-Process -Name cli -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -and [string]::Equals($_.Path, $targetExe, [System.StringComparison]::OrdinalIgnoreCase)
    })
    if ($runningCli.Count -gt 0) {
        Write-Host 'Closing the running project CLI to install the new build...'
        foreach ($cliProcess in $runningCli) {
            try {
                $cliProcess.Kill()
            } catch {
                if (-not $cliProcess.HasExited) { throw }
            }
        }
        foreach ($cliProcess in $runningCli) {
            if (-not $cliProcess.WaitForExit(10000)) {
                throw 'The running project CLI did not exit; existing cli.exe was preserved.'
            }
        }
    }

    # Atomic replacement retains a recoverable previous binary. Retry briefly
    # while Windows releases image handles or a virus scanner finishes reading.
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        try {
            if (Test-Path -LiteralPath $targetExe) {
                [System.IO.File]::Replace($stagedExe, $targetExe, $backupExe)
            } else {
                [System.IO.File]::Move($stagedExe, $targetExe)
            }
            break
        } catch {
            if ($attempt -eq 19) {
                throw "Cannot replace cli.exe. Close this project's CLI or run this build outside the sandbox, then retry. Validated build remains at $stagedExe. Details: $($_.Exception.Message)"
            }
            Start-Sleep -Milliseconds 250
        }
    }
    if ((Get-FileHash -LiteralPath $targetExe -Algorithm SHA256).Hash -ne $expectedHash) {
        throw 'Installed cli.exe does not match the validated build.'
    }
    Write-Host "Built and installed: $targetExe"
} finally {
    Pop-Location
}
