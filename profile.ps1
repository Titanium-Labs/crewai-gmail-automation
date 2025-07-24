# PowerShell Profile for Warp Terminal
# Handles PSReadLine PredictionSource parameter compatibility across PowerShell versions

# Function to safely configure PSReadLine based on available parameters
function Initialize-PSReadLineConfig {
    try {
        # Import PSReadLine module if available
        if (Get-Module -ListAvailable -Name PSReadLine) {
            Import-Module PSReadLine -ErrorAction SilentlyContinue
            
            # Get available parameters for Set-PSReadLineOption
            $availableParams = (Get-Command Set-PSReadLineOption).Parameters.Keys
            
            # Check if PredictionSource parameter is available (PSReadLine >= 2.2)
            if ($availableParams -contains "PredictionSource") {
                # Modern PSReadLine version - can use prediction features
                Write-Host "PSReadLine v2.2+ detected - enabling prediction features" -ForegroundColor Green
                Set-PSReadLineOption -PredictionSource History
                Set-PSReadLineOption -PredictionViewStyle ListView
            } else {
                # Older PSReadLine version - use basic configuration
                Write-Host "PSReadLine v2.0 detected - using basic configuration" -ForegroundColor Yellow
                
                # Set basic options that are available in PSReadLine 2.0
                Set-PSReadLineOption -EditMode Windows
                Set-PSReadLineOption -HistorySearchCursorMovesToEnd:$true
                Set-PSReadLineOption -ShowToolTips:$true
                Set-PSReadLineOption -MaximumHistoryCount 4000
            }
            
            # Common key bindings that work across versions
            Set-PSReadLineKeyHandler -Key Tab -Function Complete
            Set-PSReadLineKeyHandler -Key Ctrl+f -Function ForwardWord
            Set-PSReadLineKeyHandler -Key Ctrl+b -Function BackwardWord
            
        } else {
            Write-Host "PSReadLine module not available" -ForegroundColor Red
        }
    }
    catch {
        Write-Host "Error configuring PSReadLine: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Initialize PSReadLine configuration
Initialize-PSReadLineConfig

# Warp-specific configuration
if ($env:TERM_PROGRAM -eq "WarpBuildAgent" -or $env:WARP_IS_LOCAL_SHELL_SESSION -eq "1") {
    Write-Host "Warp terminal detected - profile loaded successfully" -ForegroundColor Cyan
}

# Additional PowerShell enhancements
$PSDefaultParameterValues['Out-Default:OutVariable'] = '__'
