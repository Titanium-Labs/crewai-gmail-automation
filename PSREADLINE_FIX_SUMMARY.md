# PowerShell PSReadLine "PredictionSource" Error Fix

## Problem
When using Warp terminal with PowerShell, users encounter an error:
```
Set-PSReadLineOption: A parameter cannot be found that matches parameter name 'PredictionSource'
```

This occurs because the `PredictionSource` parameter was introduced in PSReadLine version 2.2, but many systems still have PSReadLine 2.0 installed.

## Solution Implementation

### 1. Version Detection
- **Detected Version**: PSReadLine 2.0.0 (confirmed via `Get-Module PSReadLine -ListAvailable`)
- **Parameter Check**: Verified `PredictionSource` parameter is NOT available in this version
- **Available Parameters**: Confirmed compatible parameters like `EditMode`, `ShowToolTips`, etc.

### 2. Smart Profile (`profile.ps1`)
Created an intelligent PowerShell profile that:
- Automatically detects PSReadLine version
- Uses `PredictionSource` parameter only if PSReadLine >= 2.2
- Falls back to compatible options for older versions
- Includes error handling to prevent script failures
- Provides user feedback about which configuration is being used

### 3. Installation Methods
Provided multiple ways to install the profile:

#### A. Simple PowerShell Script (`install-profile.ps1`)
- Detects profile location automatically
- Creates profile directory if needed
- Copies and tests the profile

#### B. Advanced Setup Script (`setup-powershell-profile.ps1`)
- Supports current user or all users installation
- Includes system information display
- Administrative privilege checking
- Comprehensive error handling

#### C. Batch File (`install-profile.bat`)
- Windows-friendly installation option
- Handles PowerShell execution policy issues
- User-friendly output and guidance

### 4. Documentation
- Added comprehensive troubleshooting section to README.md
- Included multiple installation methods
- Explained how the fix works
- Provided manual installation steps as backup

## Technical Details

### PSReadLine 2.0 Compatible Configuration
```powershell
Set-PSReadLineOption -EditMode Windows
Set-PSReadLineOption -HistorySearchCursorMovesToEnd:$true
Set-PSReadLineOption -ShowToolTips:$true
Set-PSReadLineOption -MaximumHistoryCount 4000
```

### PSReadLine 2.2+ Enhanced Configuration
```powershell
Set-PSReadLineOption -PredictionSource History
Set-PSReadLineOption -PredictionViewStyle ListView
```

### Error Prevention Strategy
- Dynamic parameter detection using `(Get-Command Set-PSReadLineOption).Parameters.Keys`
- Try-catch blocks for graceful error handling
- Informative user feedback for different scenarios

## Files Created
1. `profile.ps1` - Main PowerShell profile with version-aware configuration
2. `install-profile.ps1` - Simple installation script
3. `setup-powershell-profile.ps1` - Advanced setup with options
4. `install-profile.bat` - Windows batch file installer
5. Updated `README.md` - Documentation and troubleshooting guide

## Testing Results
- ✅ Profile loads successfully without errors
- ✅ Automatically detects PSReadLine 2.0 and uses compatible options
- ✅ Provides user feedback about configuration applied
- ✅ Includes Warp terminal detection and welcome message

## Usage
Users can now run any of these commands to fix the error:
```bash
# PowerShell method
powershell.exe -ExecutionPolicy Bypass -File install-profile.ps1

# Batch file method  
install-profile.bat

# Manual method
# Copy profile.ps1 to PowerShell profile location
```

After installation, users simply need to restart their PowerShell session or Warp terminal, and the error will be eliminated.

## Impact
- Eliminates PSReadLine "PredictionSource" parameter errors
- Maintains PowerShell functionality across different PSReadLine versions
- Provides seamless Warp terminal integration
- Future-proof solution that works with PSReadLine upgrades
