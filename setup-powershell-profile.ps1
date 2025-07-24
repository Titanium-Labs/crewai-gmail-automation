# Setup script for PowerShell profile with PSReadLine error handling
# This script installs the profile to prevent PredictionSource parameter errors

param(
    [switch]$CurrentUser,
    [switch]$AllUsers,
    [switch]$ShowInfo
)

function Show-Information {
    Write-Host "PowerShell Profile Setup for PSReadLine Compatibility" -ForegroundColor Cyan
    Write-Host "=====================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "This script fixes the PSReadLine 'PredictionSource' parameter error by:"
    Write-Host "1. Detecting the installed PSReadLine version" -ForegroundColor Green
    Write-Host "2. Only using PredictionSource parameter if PSReadLine >= 2.2" -ForegroundColor Green
    Write-Host "3. Falling back to compatible options for older versions" -ForegroundColor Green
    Write-Host ""
    Write-Host "Current PSReadLine Version:" -ForegroundColor Yellow
    $psReadLineModule = Get-Module PSReadLine -ListAvailable | Select-Object -First 1
    if ($psReadLineModule) {
        Write-Host "  Version: $($psReadLineModule.Version)" -ForegroundColor White
        Write-Host "  Path: $($psReadLineModule.ModuleBase)" -ForegroundColor White
        
        $availableParams = (Get-Command Set-PSReadLineOption).Parameters.Keys
        if ($availableParams -contains "PredictionSource") {
            Write-Host "  PredictionSource parameter: AVAILABLE" -ForegroundColor Green
        } else {
            Write-Host "  PredictionSource parameter: NOT AVAILABLE" -ForegroundColor Red
        }
    } else {
        Write-Host "  PSReadLine module not found" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Profile Locations:" -ForegroundColor Yellow
    Write-Host "  Current User: $PROFILE" -ForegroundColor White
    Write-Host "  All Users: $($PROFILE.AllUsersCurrentHost)" -ForegroundColor White
    Write-Host ""
}

function Install-ProfileForCurrentUser {
    Write-Host "Installing PowerShell profile for current user..." -ForegroundColor Green
    
    $profileDir = Split-Path $PROFILE -Parent
    if (!(Test-Path $profileDir)) {
        New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
        Write-Host "Created profile directory: $profileDir" -ForegroundColor Yellow
    }
    
    $sourceProfile = Join-Path $PSScriptRoot "profile.ps1"
    if (Test-Path $sourceProfile) {
        Copy-Item $sourceProfile $PROFILE -Force
        Write-Host "Profile installed to: $PROFILE" -ForegroundColor Green
    } else {
        Write-Host "Error: Source profile not found at $sourceProfile" -ForegroundColor Red
        return $false
    }
    
    return $true
}

function Install-ProfileForAllUsers {
    Write-Host "Installing PowerShell profile for all users..." -ForegroundColor Green
    
    $allUsersProfile = $PROFILE.AllUsersCurrentHost
    $profileDir = Split-Path $allUsersProfile -Parent
    
    if (!(Test-Path $profileDir)) {
        New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
        Write-Host "Created profile directory: $profileDir" -ForegroundColor Yellow
    }
    
    $sourceProfile = Join-Path $PSScriptRoot "profile.ps1"
    if (Test-Path $sourceProfile) {
        Copy-Item $sourceProfile $allUsersProfile -Force
        Write-Host "Profile installed to: $allUsersProfile" -ForegroundColor Green
    } else {
        Write-Host "Error: Source profile not found at $sourceProfile" -ForegroundColor Red
        return $false
    }
    
    return $true
}

function Test-ProfileInstallation {
    Write-Host "Testing profile installation..." -ForegroundColor Yellow
    
    try {
        . $PROFILE
        Write-Host "Profile loaded successfully!" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "Error loading profile: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# Main execution
if ($ShowInfo) {
    Show-Information
    exit 0
}

if (!$CurrentUser -and !$AllUsers) {
    Write-Host "PowerShell Profile Setup" -ForegroundColor Cyan
    Write-Host "Please specify installation scope:" -ForegroundColor Yellow
    Write-Host "  -CurrentUser : Install for current user only" -ForegroundColor White
    Write-Host "  -AllUsers    : Install for all users (requires admin)" -ForegroundColor White
    Write-Host "  -ShowInfo    : Show PSReadLine version information" -ForegroundColor White
    Write-Host ""
    Write-Host "Example: .\setup-powershell-profile.ps1 -CurrentUser" -ForegroundColor Green
    exit 1
}

Show-Information

if ($AllUsers) {
    # Check if running as administrator
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
    if (!$isAdmin) {
        Write-Host "Error: Installing for all users requires administrator privileges" -ForegroundColor Red
        Write-Host "Please run PowerShell as Administrator and try again" -ForegroundColor Yellow
        exit 1
    }
    
    if (Install-ProfileForAllUsers) {
        Write-Host "Installation completed successfully!" -ForegroundColor Green
    }
} elseif ($CurrentUser) {
    if (Install-ProfileForCurrentUser) {
        Write-Host "Installation completed successfully!" -ForegroundColor Green
        Test-ProfileInstallation
    }
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Restart your PowerShell session or Warp terminal" -ForegroundColor White
Write-Host "2. The PSReadLine error should no longer appear" -ForegroundColor White
Write-Host "3. The profile will automatically detect your PSReadLine version" -ForegroundColor White
