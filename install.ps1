#Requires -Version 5.1
<#
.SYNOPSIS
    Install Sisyphusfy on Windows.

.DESCRIPTION
    Downloads and installs the Sisyphusfy release artifact for Windows.

.PARAMETER Version
    Release version to install (default: 0.1.0).

.PARAMETER InstallDir
    Installation directory (default: $env:USERPROFILE\.sisyphusfy\bin).

.PARAMETER DryRun
    Show what would be done without executing.

.EXAMPLE
    .\install.ps1
    .\install.ps1 -Version 0.2.0 -DryRun
#>
param(
    [string]$Version = "0.1.0",
    [string]$InstallDir = "$env:USERPROFILE\.sisyphusfy\bin",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$Repository = "lileililiwen/sisyphusfy"

function Get-Platform {
    $arch = if ([Environment]::Is64BitOperatingSystem) { "x86_64" } else {
        Write-Error "Unsupported architecture: x86. Supported: x86_64"
        exit 1
    }
    return @{ Platform = "win32"; Arch = $arch }
}

function Download-File {
    param([string]$Url, [string]$OutFile)
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing
}

function Get-Checksums {
    param([string]$Version)
    $url = "https://github.com/$Repository/releases/download/v$Version/SHA256SUMS.txt"
    $tmpFile = Join-Path $env:TEMP "sha256sums.txt"
    Download-File -Url $url -OutFile $tmpFile
    $content = Get-Content $tmpFile -Raw
    Remove-Item $tmpFile -ErrorAction SilentlyContinue
    return $content
}

function Verify-Checksum {
    param([string]$FilePath, [string]$Expected)
    $hash = (Get-FileHash -Path $FilePath -Algorithm SHA256).Hash.ToLower()
    if ($hash -ne $Expected.ToLower()) {
        Write-Error "Checksum mismatch: expected $Expected, got $hash"
        exit 1
    }
}

function Main {
    $platformInfo = Get-Platform
    $platform = $platformInfo.Platform
    $arch = $platformInfo.Arch

    $filename = "sisyphusfy-$Version-$platform-$arch.tar.gz"
    $url = "https://github.com/$Repository/releases/download/v$Version/$filename"

    Write-Host "Sisyphusfy $Version installer"
    Write-Host "Platform: $platform ($arch)"
    Write-Host "Install directory: $InstallDir"
    Write-Host ""

    if ($DryRun) {
        Write-Host "[dry-run] Would download: $url"
        Write-Host "[dry-run] Would verify checksum"
        Write-Host "[dry-run] Would extract to: $InstallDir"
        Write-Host "[dry-run] Would print PATH instructions"
        return
    }

    Write-Host "Fetching checksums..."
    $checksums = Get-Checksums -Version $Version
    $lines = $checksums -split "`n"
    $expected = $null
    foreach ($line in $lines) {
        $line = $line.Trim()
        if ($line -match "^(\S+)\s+$filename$") {
            $expected = $Matches[1]
            break
        }
    }

    if (-not $expected) {
        Write-Error "No checksum found for $filename"
        exit 1
    }

    Write-Host "Downloading $filename..."
    $tmpDir = Join-Path $env:TEMP "sisyphusfy-install"
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
    $archive = Join-Path $tmpDir $filename

    try {
        Download-File -Url $url -OutFile $archive

        Write-Host "Verifying checksum..."
        Verify-Checksum -FilePath $archive -Expected $expected

        Write-Host "Extracting..."
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
        tar xzf $archive -C $InstallDir

        Write-Host ""
        Write-Host "Installed to $InstallDir"
        Write-Host ""
        Write-Host "Add to your PATH:"
        Write-Host "  `$env:PATH = `"$InstallDir;`$env:PATH`""
        Write-Host ""
        Write-Host "Or add to your PowerShell profile:"
        Write-Host "  Add-Content `$PROFILE `"```$env:PATH = `"`"$InstallDir`";`$env:PATH`"`""
    }
    finally {
        Remove-Item -Path $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Main
