# Register a per-user scheduled task that scans US market structure
# every 15 minutes on weekdays. No admin required for the task itself.
# Run from PowerShell:  powershell -ExecutionPolicy Bypass -File .\install-windows-task.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python).Source
$action = New-ScheduledTaskAction -Execute $python -Argument "-m msm scan" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask -TaskName "MarketStructureMonitor" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "Scheduled task 'MarketStructureMonitor' installed."
Write-Host "It runs: $python -m msm scan"
Write-Host "Working directory: $root"
Write-Host ""
Write-Host "Start the live dashboard any time with run.bat"
Write-Host "Uninstall: Unregister-ScheduledTask -TaskName MarketStructureMonitor -Confirm:`$false"
