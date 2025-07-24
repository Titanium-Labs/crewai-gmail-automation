@echo off
echo Installing PowerShell Profile for PSReadLine compatibility...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "$profilePath = $PROFILE; ^
     Write-Host 'Profile path:' $profilePath; ^
     $profileDir = Split-Path $profilePath -Parent; ^
     if (!(Test-Path $profileDir)) { ^
         Write-Host 'Creating profile directory:' $profileDir; ^
         New-Item -ItemType Directory -Path $profileDir -Force | Out-Null ^
     }; ^
     if (Test-Path 'profile.ps1') { ^
         Copy-Item 'profile.ps1' $profilePath -Force; ^
         Write-Host 'Profile installed successfully!' -ForegroundColor Green; ^
         Write-Host 'Location:' $profilePath -ForegroundColor Cyan; ^
         Write-Host 'Testing profile...' -ForegroundColor Yellow; ^
         try { ^
             . $profilePath; ^
             Write-Host 'Profile test successful!' -ForegroundColor Green ^
         } catch { ^
             Write-Host 'Profile test failed:' $_.Exception.Message -ForegroundColor Red ^
         } ^
     } else { ^
         Write-Host 'Error: profile.ps1 not found in current directory' -ForegroundColor Red ^
     }"

echo.
echo To complete the setup:
echo 1. Restart your PowerShell session or Warp terminal
echo 2. The PSReadLine error should be resolved
pause
