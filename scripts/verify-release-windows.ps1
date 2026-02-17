param (
    [string]$TargetRoot = "src-tauri/target"
)

$ErrorActionPreference = "Stop"

# Verifies NSIS installer is present, optionally signed, and can install silently.

$installer = Get-ChildItem -Path $TargetRoot -Recurse -File -Filter *.exe |
    Where-Object { $_.FullName -match '\\bundle\\nsis\\' } |
    Sort-Object LastWriteTimeUtc |
    Select-Object -Last 1

if ($null -eq $installer) {
    throw "NSIS installer not found under $TargetRoot"
}

Write-Host "Verifying installer: $($installer.FullName)"

$signature = Get-AuthenticodeSignature -FilePath $installer.FullName
Write-Host "Authenticode status: $($signature.Status)"

$requireSignature = $env:REQUIRE_WINDOWS_SIGNATURE -eq "true"
if ($requireSignature -and $signature.Status -ne "Valid") {
    throw "Windows signature required but installer signature is $($signature.Status)"
}
if (-not $requireSignature -and $signature.Status -ne "Valid") {
    Write-Warning "Installer is not Authenticode-signed (status: $($signature.Status))"
}

$installDir = Join-Path $env:USERPROFILE "yt-downloader-smoke"
if (Test-Path $installDir) {
    Remove-Item -Recurse -Force $installDir
}
New-Item -ItemType Directory -Path $installDir | Out-Null

try {
    # NSIS silent install. /D must be the final argument.
    $arguments = @("/S", "/D=$installDir")
    $process = Start-Process -FilePath $installer.FullName -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Silent installer failed with exit code $($process.ExitCode)"
    }

    $installedExe = Get-ChildItem -Path $installDir -Recurse -File -Filter *.exe |
        Where-Object { $_.Name -notmatch 'unins|uninstall' } |
        Select-Object -First 1

    if ($null -eq $installedExe) {
        throw "No installed application executable found in $installDir"
    }

    Write-Host "Installed executable detected: $($installedExe.FullName)"
}
finally {
    if (Test-Path $installDir) {
        Remove-Item -Recurse -Force $installDir
    }
}

Write-Host "Windows release verification passed."
