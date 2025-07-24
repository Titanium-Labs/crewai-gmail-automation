# Simple PowerShell Profile Installer
Write-Host "Installing PowerShell Profile for PSReadLine compatibility..." -ForegroundColor Green

# Get profile path
$profilePath = $PROFILE
Write-Host "Profile path: $profilePath" -ForegroundColor Yellow

# Create profile directory if it doesn't exist
$profileDir = Split-Path $profilePath -Parent
if (!(Test-Path $profileDir)) {
    Write-Host "Creating profile directory: $profileDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
}

# Copy the profile
if (Test-Path "profile.ps1") {
    Copy-Item "profile.ps1" $profilePath -Force
    Write-Host "Profile installed successfully!" -ForegroundColor Green
    Write-Host "Location: $profilePath" -ForegroundColor Cyan
    
    # Test the profile
    Write-Host "Testing profile..." -ForegroundColor Yellow
    try {
        . $profilePath
        Write-Host "Profile test successful!" -ForegroundColor Green
    }
    catch {
        Write-Host "Profile test failed: $($_.Exception.Message)" -ForegroundColor Red
    }
} else {
    Write-Host "Error: profile.ps1 not found in current directory" -ForegroundColor Red
}

Write-Host ""
Write-Host "To complete the setup:" -ForegroundColor Cyan
Write-Host "1. Restart your PowerShell session" -ForegroundColor White
Write-Host "2. The PSReadLine error should be resolved" -ForegroundColor White
