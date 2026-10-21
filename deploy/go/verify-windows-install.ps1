param(
  [Parameter(Mandatory = $true)][string]$Installer,
  [Parameter(Mandatory = $true)][string]$PortableZip,
  [Parameter(Mandatory = $true)][string]$UpdateZip
)

$ErrorActionPreference = "Stop"
$root = Join-Path $env:RUNNER_TEMP "animecaos-installed-e2e"
$installDir = Join-Path $root "installed"
$portableDir = Join-Path $root "portable"
$portableData = Join-Path $root "portable-data"
$installData = Join-Path $root "installed-data"
New-Item -ItemType Directory -Force -Path $root, $portableData, $installData | Out-Null
# Exercise the real legacy-import path with disposable data before the first
# launch of the packaged portable app.
'{"Migrated Anime":[[[["https://legacy.invalid/video/12"],"animefire"]],0]}' |
  Set-Content -LiteralPath (Join-Path $portableData "history.json") -Encoding utf8

function Stop-AppProcesses([string]$path) {
  $fullPath = [IO.Path]::GetFullPath($path)
  Get-CimInstance Win32_Process -Filter "Name='AnimeCaos.exe'" |
    Where-Object { $_.ExecutablePath -and $_.ExecutablePath.Equals($fullPath, [StringComparison]::OrdinalIgnoreCase) } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  $runtime = [IO.Path]::GetFullPath((Join-Path (Split-Path $fullPath) 'bin/webview2')) + [IO.Path]::DirectorySeparatorChar
  Get-CimInstance Win32_Process -Filter "Name='msedgewebview2.exe'" |
    Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($runtime, [StringComparison]::OrdinalIgnoreCase) } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

  $deadline = [DateTime]::UtcNow.AddSeconds(15)
  do {
    $appStillRunning = Get-CimInstance Win32_Process -Filter "Name='AnimeCaos.exe'" |
      Where-Object { $_.ExecutablePath -and $_.ExecutablePath.Equals($fullPath, [StringComparison]::OrdinalIgnoreCase) } |
      Select-Object -First 1
    $webViewStillRunning = Get-CimInstance Win32_Process -Filter "Name='msedgewebview2.exe'" |
      Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($runtime, [StringComparison]::OrdinalIgnoreCase) } |
      Select-Object -First 1
    if (-not $appStillRunning -and -not $webViewStillRunning) { return }
    if ($appStillRunning) { Stop-Process -Id $appStillRunning.ProcessId -Force -ErrorAction SilentlyContinue }
    if ($webViewStillRunning) { Stop-Process -Id $webViewStillRunning.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Milliseconds 250
  } while ([DateTime]::UtcNow -lt $deadline)

  if ($appStillRunning -or $webViewStillRunning) { throw "Os processos do app/WebView2 não encerraram: $fullPath" }
}

function Start-AppAndWaitForDatabase([string]$appPath, [string]$dataDir) {
  $env:ANIMECAOS_DATA_DIR = $dataDir
  $process = Start-Process -FilePath $appPath -PassThru
  $database = Join-Path $dataDir "state.db"
  $deadline = [DateTime]::UtcNow.AddSeconds(35)
  while ([DateTime]::UtcNow -lt $deadline) {
    if (Test-Path -LiteralPath $database) { break }
    if ($process.HasExited) {
      $log = Join-Path $dataDir "startup-error.log"
      $detail = if (Test-Path -LiteralPath $log) { Get-Content -LiteralPath $log -Raw } else { "sem startup-error.log" }
      throw "AnimeCaos encerrou antes de criar o banco de dados. $detail"
    }
    Start-Sleep -Milliseconds 500
  }
  if (-not (Test-Path -LiteralPath $database)) { throw "AnimeCaos não criou state.db em 35 segundos" }
  Start-Sleep -Seconds 3
  $runtimeExe = [IO.Path]::GetFullPath((Join-Path (Split-Path ([IO.Path]::GetFullPath($appPath))) 'bin/webview2/msedgewebview2.exe'))
  $runtimeProcess = Get-CimInstance Win32_Process -Filter "Name='msedgewebview2.exe'" |
    Where-Object { $_.ExecutablePath -and $_.ExecutablePath.Equals($runtimeExe, [StringComparison]::OrdinalIgnoreCase) } |
    Select-Object -First 1
  if (-not $runtimeProcess) { throw "O app iniciou sem carregar o WebView2 empacotado: $runtimeExe" }
  Stop-AppProcesses $appPath
  return (Get-FileHash -LiteralPath $database -Algorithm SHA256).Hash
}

if (-not (Test-Path -LiteralPath $Installer)) { throw "Instalador ausente: $Installer" }
if (-not (Test-Path -LiteralPath $PortableZip)) { throw "Pacote portátil ausente: $PortableZip" }
if (-not (Test-Path -LiteralPath $UpdateZip)) { throw "Pacote de atualização ausente: $UpdateZip" }

$webViewKey = 'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
$webViewPresent = $false
foreach ($key in @($webViewKey, $webViewKey.Replace('HKLM:\', 'HKCU:\'))) {
  $version = (Get-ItemProperty -LiteralPath $key -Name pv -ErrorAction SilentlyContinue).pv
  if ($version -and $version -ne '0.0.0.0') { $webViewPresent = $true }
}
Write-Output "WebView2 Runtime já presente antes do teste: $webViewPresent"

New-Item -ItemType Directory -Force -Path $portableDir | Out-Null
Expand-Archive -LiteralPath $PortableZip -DestinationPath $portableDir -Force
$portableApp = Join-Path $portableDir "AnimeCaos.exe"
if (-not (Test-Path -LiteralPath $portableApp)) { throw "O ZIP portátil não contém AnimeCaos.exe" }
if (-not (Test-Path -LiteralPath (Join-Path $portableDir 'bin/webview2/msedgewebview2.exe'))) { throw 'O ZIP portátil não contém o runtime WebView2 fixo.' }
$null = Start-AppAndWaitForDatabase $portableApp $portableData
Write-Output "Pacote portátil abriu com WebView2 empacotado e criou dados isolados."
Stop-AppProcesses $portableApp
$portableCLI = Join-Path $portableDir "animecaos-cli.exe"
$historyOutput = & $portableCLI history --data $portableData 2>&1
if ($LASTEXITCODE -ne 0) { throw "CLI empacotado não leu o histórico migrado: $historyOutput" }
$history = ($historyOutput -join "`n") | ConvertFrom-Json
if (-not ($history | Where-Object { $_.anime.title -eq 'Migrated Anime' -and $_.episode.number -eq 12 })) {
  throw "O pacote não importou a posição de histórico legada: $historyOutput"
}
if (-not (Test-Path -LiteralPath (Join-Path $portableData "legacy-backup/history.json"))) {
  throw "A migração não preservou backup do histórico legado"
}
Write-Output "CLI empacotado carregou o episódio legado e preservou o arquivo de origem."

$installArgs = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=$installDir")
$install = Start-Process -FilePath $Installer -ArgumentList $installArgs -PassThru -Wait
if ($install.ExitCode -ne 0) { throw "Instalador retornou código $($install.ExitCode)" }
$installedApp = Join-Path $installDir "AnimeCaos.exe"
if (-not (Test-Path -LiteralPath $installedApp)) { throw "O instalador não criou $installedApp" }
$beforeUpdate = Start-AppAndWaitForDatabase $installedApp $installData

$updaterErrorPath = Join-Path $installDir 'updater-error.log'
$startupErrorPath = Join-Path $installData 'startup-error.log'
Remove-Item -LiteralPath $updaterErrorPath, $startupErrorPath -Force -ErrorAction SilentlyContinue
$psi = [Diagnostics.ProcessStartInfo]::new($installedApp)
$psi.UseShellExecute = $false
foreach ($argument in @('--apply-update', $UpdateZip, '--target', $installDir, '--parent', '2147483647')) {
  [void]$psi.ArgumentList.Add($argument)
}
$helper = [Diagnostics.Process]::Start($psi)
if (-not $helper.WaitForExit(120000)) { $helper.Kill(); throw "Updater não concluiu em 120 segundos" }
if ($helper.ExitCode -ne 0) { throw "Helper do updater retornou código $($helper.ExitCode)" }
if (Test-Path -LiteralPath $updaterErrorPath) {
  $detail = Get-Content -LiteralPath $updaterErrorPath -Raw
  throw "O helper do updater falhou: $detail"
}
$markerPath = Join-Path $installDir "THIRD-PARTY-NOTICES.md"
if (-not (Test-Path -LiteralPath $markerPath)) { throw "O updater não instalou os arquivos do pacote novo" }
$deadline = [DateTime]::UtcNow.AddSeconds(60)
$running = $null
while ([DateTime]::UtcNow -lt $deadline) {
  $running = Get-CimInstance Win32_Process -Filter "Name='AnimeCaos.exe'" |
    Where-Object { $_.ExecutablePath -and $_.ExecutablePath.Equals([IO.Path]::GetFullPath($installedApp), [StringComparison]::OrdinalIgnoreCase) } |
    Select-Object -First 1
  if ($running) { break }
  if (Test-Path -LiteralPath $updaterErrorPath) {
    $detail = Get-Content -LiteralPath $updaterErrorPath -Raw
    throw "O helper do updater falhou ao reiniciar o aplicativo: $detail"
  }
  if (Test-Path -LiteralPath $startupErrorPath) {
    $detail = Get-Content -LiteralPath $startupErrorPath -Raw
    throw "O aplicativo atualizado falhou ao iniciar: $detail"
  }
  Start-Sleep -Milliseconds 500
}
if (-not $running) {
  $details = @()
  if (Test-Path -LiteralPath $updaterErrorPath) { $details += "updater-error.log: $(Get-Content -LiteralPath $updaterErrorPath -Raw)" }
  if (Test-Path -LiteralPath $startupErrorPath) { $details += "startup-error.log: $(Get-Content -LiteralPath $startupErrorPath -Raw)" }
  $suffix = if ($details.Count) { " $($details -join '; ')" } else { '' }
  throw "O aplicativo atualizado não permaneceu aberto em até 60 segundos.$suffix"
}
Stop-AppProcesses $installedApp
$databasePath = Join-Path $installData "state.db"
$afterUpdate = (Get-FileHash -LiteralPath $databasePath -Algorithm SHA256).Hash
if ($afterUpdate -ne $beforeUpdate) { throw "O updater alterou ou perdeu o banco de dados do usuário" }
Write-Output "Instalação, atualização do diretório, reinício e preservação de state.db passaram."

$uninstaller = Get-ChildItem -LiteralPath $installDir -Filter 'unins*.exe' -File | Select-Object -First 1
if (-not $uninstaller) { throw "O instalador não criou o desinstalador" }
$remove = Start-Process -FilePath $uninstaller.FullName -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -PassThru -Wait
if ($remove.ExitCode -ne 0) { throw "Desinstalador retornou código $($remove.ExitCode)" }
if (Test-Path -LiteralPath $installedApp) { throw "O desinstalador deixou o aplicativo instalado" }
if (-not (Test-Path -LiteralPath $databasePath)) { throw "A desinstalação removeu dados do usuário" }
if ((Get-FileHash -LiteralPath $databasePath -Algorithm SHA256).Hash -ne $beforeUpdate) { throw "A desinstalação alterou os dados do usuário" }
Write-Output "Desinstalação removeu os binários e preservou os dados."
