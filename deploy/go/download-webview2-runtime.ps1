param(
  [string]$Destination = 'bin'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$destinationPath = [IO.Path]::GetFullPath((Join-Path $root $Destination))
$binRoot = [IO.Path]::GetFullPath((Join-Path $root 'bin'))
$binPrefix = $binRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if ($destinationPath -ne $binRoot -and -not $destinationPath.StartsWith($binPrefix, [StringComparison]::OrdinalIgnoreCase)) {
  throw 'O destino do WebView2 precisa permanecer dentro de bin/.'
}

# The Microsoft download page lists this exact x64 Fixed Version runtime.
# Update the version and official URL together for a later release train.
$version = '155.0.4283.62'
$cabUrl = 'https://msedge.sf.dl.delivery.mp.microsoft.com/filestreamingservice/files/232cf50b-3980-4531-afbb-779f446d7de1/Microsoft.WebView2.FixedVersionRuntime.155.0.4283.62.x64.cab'
$tempRoot = if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) { [IO.Path]::GetTempPath() } else { $env:RUNNER_TEMP }
$work = Join-Path $tempRoot "animecaos-webview2-$PID"
$cab = Join-Path $work "webview2-$version-x64.cab"
$expanded = Join-Path $work 'expanded'
$runtimeDir = Join-Path $destinationPath 'webview2'
New-Item -ItemType Directory -Force $work, $expanded, $destinationPath | Out-Null

try {
  Invoke-WebRequest -Uri $cabUrl -OutFile $cab
  & "$env:SystemRoot\System32\expand.exe" '-F:*' $cab $expanded | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Não foi possível extrair o pacote CAB WebView2 (código $LASTEXITCODE)." }

  $browser = Get-ChildItem -LiteralPath $expanded -Filter 'msedgewebview2.exe' -File -Recurse | Select-Object -First 1
  if (-not $browser) { throw 'O CAB oficial não contém msedgewebview2.exe.' }
  $actualVersion = (Get-Item -LiteralPath $browser.FullName).VersionInfo.ProductVersion.Trim()
  if (-not $actualVersion.StartsWith($version, [StringComparison]::Ordinal)) {
    throw "Versão do WebView2 extraído divergiu: esperado $version, recebido $actualVersion."
  }
  $signature = Get-AuthenticodeSignature -LiteralPath $browser.FullName
  if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft') {
    throw 'A assinatura Microsoft do executável WebView2 não foi validada.'
  }
  $signedBinaries = Get-ChildItem -LiteralPath $browser.DirectoryName -File -Recurse |
    Where-Object { $_.Extension -in '.exe', '.dll' }
  foreach ($binary in $signedBinaries) {
    $binarySignature = Get-AuthenticodeSignature -LiteralPath $binary.FullName
    if ($binarySignature.Status -ne 'Valid' -or $binarySignature.SignerCertificate.Subject -notmatch 'Microsoft') {
      throw "A assinatura Microsoft do componente WebView2 não foi validada: $($binary.Name)"
    }
  }
  foreach ($required in @('msedge.dll', 'msedgewebview2.exe', 'resources.pak', 'icudtl.dat', "$version.manifest")) {
    if (-not (Test-Path -LiteralPath (Join-Path $browser.DirectoryName $required))) {
      throw "Arquivo obrigatório do WebView2 ausente: $required"
    }
  }

  if (Test-Path -LiteralPath $runtimeDir) {
    $resolvedRuntime = [IO.Path]::GetFullPath($runtimeDir)
    if (-not $resolvedRuntime.StartsWith($binPrefix, [StringComparison]::OrdinalIgnoreCase)) {
      throw 'O destino existente do runtime WebView2 não está dentro de bin/.'
    }
    Remove-Item -LiteralPath $resolvedRuntime -Recurse -Force
  }
  New-Item -ItemType Directory -Force $runtimeDir | Out-Null
  Get-ChildItem -LiteralPath $browser.DirectoryName -Force | Copy-Item -Destination $runtimeDir -Recurse -Force
  Set-Content -LiteralPath (Join-Path $runtimeDir 'version.txt') -Value $actualVersion -NoNewline -Encoding ascii

  $bundledBrowser = Join-Path $runtimeDir 'msedgewebview2.exe'
  $bundledSignature = Get-AuthenticodeSignature -LiteralPath $bundledBrowser
  if ($bundledSignature.Status -ne 'Valid' -or $bundledSignature.SignerCertificate.Subject -notmatch 'Microsoft') {
    throw 'A assinatura do WebView2 copiado para o bundle não passou na validação.'
  }
  Write-Output "WebView2 Fixed Version $actualVersion (x64)"
  Write-Output "Origem oficial: $cabUrl"
  Write-Output "Runtime empacotado: $runtimeDir"
} finally {
  if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }
}
