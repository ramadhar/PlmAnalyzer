<#!
.SYNOPSIS
  Creates Desktop and Taskbar shortcuts for PLM Log Analyzer.
.DESCRIPTION
  - Desktop: PLM Analyzer.lnk
  - Taskbar: pins the shortcut (Windows 10/11) using Shell COM objects (best effort)
.NOTES
  Run from an elevated PowerShell if taskbar pinning fails due to policy.
#>
param(
  [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\.."),
  [string]$Launcher = (Resolve-Path "$PSScriptRoot/launch_plm_analyzer.bat"),
  [switch]$Force
)

$ErrorActionPreference = 'Stop'
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'PLM Analyzer.lnk'

if(Test-Path $shortcutPath -and -not $Force){
  Write-Host "Desktop shortcut already exists: $shortcutPath (use -Force to overwrite)" -ForegroundColor Yellow
}else{
  $shell = New-Object -ComObject WScript.Shell
  $sc = $shell.CreateShortcut($shortcutPath)
  $sc.TargetPath = $Launcher
  $sc.WorkingDirectory = $ProjectRoot
  $sc.WindowStyle = 1
  $sc.IconLocation = "$ProjectRoot\\icon\\plm.ico,0"
  if(-not (Test-Path "$ProjectRoot/icon/plm.ico")){
    # fallback to shell32 generic icon index 0
    $sc.IconLocation = "$env:WINDIR\\System32\\shell32.dll,0"
  }
  $sc.Description = 'Launch PLM Log Analyzer'
  $sc.Save()
  Write-Host "Created desktop shortcut: $shortcutPath" -ForegroundColor Green
}

# Attempt Taskbar pin (supported via explorer verb in Win10/11). This is best-effort.
try {
  $taskbarVerb = 'Pin to Tas&kbar'
  $file = Get-Item $shortcutPath
  $shellApp = New-Object -ComObject Shell.Application
  $folder = $shellApp.Namespace($file.Directory.FullName)
  $item = $folder.ParseName($file.Name)
  $verbs = $item.Verbs()
  $pinVerb = $null
  foreach($v in $verbs){
    if($v.Name -match 'taskbar' -or $v.Name -like '*Tas*kbar*'){$pinVerb=$v;break}
  }
  if($pinVerb){
    $pinVerb.DoIt()
    Write-Host 'Pinned to taskbar (if supported).' -ForegroundColor Green
  } else {
    Write-Host 'Taskbar pin verb not found (manual pin may be required).' -ForegroundColor Yellow
  }
} catch {
  Write-Host 'Taskbar pin attempt failed: ' $_.Exception.Message -ForegroundColor Yellow
}
