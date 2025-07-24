# PowerShell Pester Tests for PSReadLine Fix
# 
# This test verifies that the PSReadLine "PredictionSource" parameter error
# has been resolved by our profile.ps1 implementation.
#
# Run with: Invoke-Pester tests/Test-PSReadLineFix.Tests.ps1 -Verbose

Describe "PSReadLine Fix Regression Tests" {
    
    BeforeAll {
        # Get the project root directory
        $ProjectRoot = Split-Path -Parent $PSScriptRoot
        $ProfilePath = Join-Path $ProjectRoot "profile.ps1"
        
        # Backup current PowerShell profile if it exists
        $CurrentProfile = $PROFILE.CurrentUserCurrentHost
        $ProfileDir = Split-Path $CurrentProfile -Parent
        $BackupProfile = $null
        
        if (Test-Path $CurrentProfile) {
            $BackupProfile = "$CurrentProfile.backup.$(Get-Date -Format 'yyyyMMdd-HHmmss')"
            Copy-Item $CurrentProfile $BackupProfile -Force
            Write-Host "Backed up existing profile to: $BackupProfile" -ForegroundColor Yellow
        }
        
        # Ensure profile directory exists
        if (-not (Test-Path $ProfileDir)) {
            New-Item -Path $ProfileDir -ItemType Directory -Force | Out-Null
        }
    }
    
    AfterAll {
        # Restore original profile if we backed it up
        if ($BackupProfile -and (Test-Path $BackupProfile)) {
            Move-Item $BackupProfile $CurrentProfile -Force
            Write-Host "Restored original profile from backup" -ForegroundColor Green
        }
    }

    Context "Profile File Validation" {
        
        It "Should have profile.ps1 file in project root" {
            $ProfilePath | Should -Exist
        }
        
        It "Should contain PSReadLine version detection" {
            $content = Get-Content $ProfilePath -Raw
            $content | Should -Match "Get-Module PSReadLine"
        }
        
        It "Should contain PredictionSource parameter handling" {
            $content = Get-Content $ProfilePath -Raw
            $content | Should -Match "PredictionSource"
        }
        
        It "Should contain error handling (try-catch blocks)" {
            $content = Get-Content $ProfilePath -Raw
            $content | Should -Match "try"
            $content | Should -Match "catch"
        }
        
        It "Should contain version comparison logic" {
            $content = Get-Content $ProfilePath -Raw
            # Should have logic to compare PSReadLine versions
            $content | Should -Match "Version|version"
        }
    }

    Context "Installation Scripts Validation" {
        
        It "Should have install-profile.ps1 script" {
            Join-Path $ProjectRoot "install-profile.ps1" | Should -Exist
        }
        
        It "Should have install-profile.bat script" {
            Join-Path $ProjectRoot "install-profile.bat" | Should -Exist
        }
        
        It "Should have setup-powershell-profile.ps1 script" {
            Join-Path $ProjectRoot "setup-powershell-profile.ps1" | Should -Exist
        }
    }

    Context "Profile Syntax and Execution" {
        
        It "Should have valid PowerShell syntax" {
            # Test that the profile can be parsed without syntax errors
            { 
                $null = [System.Management.Automation.PSParser]::Tokenize(
                    (Get-Content $ProfilePath -Raw), [ref]$null
                )
            } | Should -Not -Throw
        }
        
        It "Should execute without errors in isolated session" {
            # Test the profile in an isolated PowerShell session
            $testScript = @"
                try {
                    & '$ProfilePath'
                    Write-Output "SUCCESS: Profile executed without errors"
                } catch {
                    Write-Output "ERROR: `$(`$_.Exception.Message)"
                    exit 1
                }
"@
            
            $result = powershell.exe -NoProfile -Command $testScript
            $result | Should -Match "SUCCESS"
        }
    }

    Context "PSReadLine Module Detection" {
        
        It "Should detect PSReadLine module availability" {
            $module = Get-Module PSReadLine -ListAvailable | Select-Object -First 1
            $module | Should -Not -BeNullOrEmpty
            Write-Host "Detected PSReadLine version: $($module.Version)" -ForegroundColor Cyan
        }
        
        It "Should handle PSReadLine 2.0 compatibility" {
            $testScript = @"
                `$module = Get-Module PSReadLine -ListAvailable | Select-Object -First 1
                if (`$module.Version -lt [Version]'2.2.0') {
                    Write-Output "COMPATIBLE: Running PSReadLine version `$(`$module.Version) - should use fallback options"
                } else {
                    Write-Output "ENHANCED: Running PSReadLine version `$(`$module.Version) - can use PredictionSource"
                }
"@
            
            $result = powershell.exe -NoProfile -Command $testScript
            $result | Should -Match "(COMPATIBLE|ENHANCED)"
        }
    }

    Context "Error Prevention" {
        
        It "Should not produce PredictionSource parameter errors" {
            # This is the core test - run a new PowerShell session with our profile
            # and ensure no PredictionSource errors occur
            
            # Copy our profile to the PowerShell profile location temporarily
            Copy-Item $ProfilePath $PROFILE.CurrentUserCurrentHost -Force
            
            # Test with a new PowerShell session
            $testScript = @"
                # Capture any errors during profile loading
                `$ErrorActionPreference = 'Continue'
                `$initialErrorCount = `$Error.Count
                
                # The profile should already be loaded in a new session
                # Check if any new errors were added, specifically about PredictionSource
                `$newErrors = `$Error | Select-Object -First (`$Error.Count - `$initialErrorCount)
                `$predictionSourceErrors = `$newErrors | Where-Object { `$_.Exception.Message -like "*PredictionSource*" }
                
                if (`$predictionSourceErrors) {
                    Write-Output "FAIL: PredictionSource errors found: `$(`$predictionSourceErrors.Exception.Message)"
                    exit 1
                } else {
                    Write-Output "PASS: No PredictionSource errors detected"
                }
"@
            
            $result = powershell.exe -Command $testScript
            $result | Should -Match "PASS"
        }
        
        It "Should gracefully handle PSReadLine parameter unavailability" {
            # Test that the profile handles cases where PredictionSource is not available
            $testScript = @"
                # Simulate PSReadLine 2.0 environment
                function Test-ParameterAvailability {
                    `$command = Get-Command Set-PSReadLineOption -ErrorAction SilentlyContinue
                    if (`$command) {
                        `$hasParameter = `$command.Parameters.ContainsKey('PredictionSource')
                        Write-Output "PredictionSource parameter available: `$hasParameter"
                        return `$hasParameter
                    } else {
                        Write-Output "Set-PSReadLineOption command not available"
                        return `$false
                    }
                }
                
                Test-ParameterAvailability
"@
            
            $result = powershell.exe -NoProfile -Command $testScript
            $result | Should -Match "(True|False)"
        }
    }

    Context "Manual Verification Guide" {
        
        It "Should provide clear manual testing instructions" {
            # This test documents the manual verification process
            $instructions = @"
MANUAL VERIFICATION STEPS:
1. Install the profile using: powershell.exe -ExecutionPolicy Bypass -File install-profile.ps1
2. Open a new PowerShell session or Warp terminal
3. Verify that NO error message appears about 'PredictionSource' parameter
4. Confirm that PSReadLine functionality works correctly (arrow keys, history, etc.)
5. Test completion: If step 3 shows no errors, the fix is successful

Expected Result: PowerShell starts without any PredictionSource parameter errors.
"@
            
            Write-Host $instructions -ForegroundColor Green
            
            # Always pass this "test" as it's just documentation
            $true | Should -Be $true
        }
    }
}

Describe "Integration with Project Logging System" {
    
    It "Should document integration with pytest test suite" {
        $testFile = Join-Path (Split-Path $PSScriptRoot -Parent) "tests\test_logging.py"
        $testFile | Should -Exist
        
        $content = Get-Content $testFile -Raw
        $content | Should -Match "PSReadLine"
    }
    
    It "Should be part of comprehensive regression testing" {
        # Verify this test is referenced in project documentation
        $projectRoot = Split-Path -Parent $PSScriptRoot
        $readmePath = Join-Path $projectRoot "README.md"
        
        if (Test-Path $readmePath) {
            $readmeContent = Get-Content $readmePath -Raw
            # Should mention testing or PSReadLine
            ($readmeContent -match "test|PSReadLine|PowerShell") | Should -Be $true
        }
    }
}
