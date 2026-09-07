$ErrorActionPreference = 'Stop'
$aivisUrl = if ($env:AIVISSPEECH_URL) { $env:AIVISSPEECH_URL.TrimEnd('/') } else { 'http://127.0.0.1:10101' }
try {
    $version = Invoke-RestMethod "$aivisUrl/version" -TimeoutSec 2
    Write-Host "AivisSpeech Engine ready: $version"
    exit 0
} catch {}
$aivisUri = [uri]$aivisUrl
if ($aivisUri.Host -notin @('127.0.0.1', 'localhost')) { throw 'Start the configured remote AivisSpeech Engine on its host.' }
$aivisCandidates = @(
    $env:AIVISSPEECH_ENGINE,
    "$env:LOCALAPPDATA/Programs/AivisSpeech/AivisSpeech-Engine/run.exe",
    "$env:LOCALAPPDATA/Programs/AivisSpeech/AivisSpeech/AivisSpeech-Engine/run.exe",
    "$env:ProgramFiles/AivisSpeech/AivisSpeech-Engine/run.exe"
)
$aivisExe = $aivisCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
if (-not $aivisExe) { throw 'Install AivisSpeech from https://aivis-project.com/ or set AIVISSPEECH_ENGINE to run.exe.' }
$aivisRunning = Get-CimInstance Win32_Process -Filter "Name='run.exe'" | Where-Object { $_.ExecutablePath -eq $aivisExe }
if (-not $aivisRunning) {
    Start-Process -FilePath $aivisExe -ArgumentList @('--host', '127.0.0.1', '--port', "$($aivisUri.Port)") -WorkingDirectory (Split-Path $aivisExe) -WindowStyle Hidden | Out-Null
}
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
        $version = Invoke-RestMethod "$aivisUrl/version" -TimeoutSec 2
        Write-Host "AivisSpeech Engine ready: $version"
        exit 0
    } catch { Start-Sleep -Milliseconds 500 }
}
throw 'AivisSpeech is still starting. Initial model downloads can take several minutes. Run this command again to check.'
