param(
  [string]$Destination = 'bin'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$destinationPath = [IO.Path]::GetFullPath((Join-Path $root $Destination))
$binRoot = [IO.Path]::GetFullPath((Join-Path $root 'bin'))
$binPrefix = $binRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if ($destinationPath -ne $binRoot -and -not $destinationPath.StartsWith($binPrefix, [StringComparison]::OrdinalIgnoreCase)) {
  throw 'O destino do runtime do navegador precisa permanecer dentro de bin/.'
}

$firefoxVersion = '157.0.1'
$geckoVersion = '0.37.1'
$firefoxInstallerSha512 = '5e9cb7c6b8d00e2eb780350b03a4915f637dce4696205802535bad50b486cb8b4ee9afcfdcafd1b3bb75b31541c68db63a2e0da891c8b5b1248e3b681330ec57'
$geckoZipSha256 = 'dfed9315abe8d2fbc1b6161a2ee8002452e79cf05ee92fdc653a4e26bc35edd8'
$tempRoot = if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) { [IO.Path]::GetTempPath() } else { $env:RUNNER_TEMP }
$work = Join-Path $tempRoot "animecaos-browser-runtime-$PID"
$firefoxDir = Join-Path $destinationPath 'firefox'
$driverPath = Join-Path $destinationPath 'geckodriver.exe'
New-Item -ItemType Directory -Force $work, $destinationPath | Out-Null

try {
  $installer = Join-Path $work "Firefox-Setup-$firefoxVersion-x64.exe"
  $firefoxSums = Join-Path $work 'SHA512SUMS'
  Invoke-WebRequest -Uri "https://archive.mozilla.org/pub/firefox/releases/$firefoxVersion/SHA512SUMS" -OutFile $firefoxSums
  $officialFirefoxLine = Get-Content $firefoxSums | Where-Object { $_ -match "^\s*([0-9a-fA-F]{128})\s+\*?win64/en-US/Firefox Setup $([regex]::Escape($firefoxVersion))\.exe$" } | Select-Object -First 1
  if (-not $officialFirefoxLine) { throw 'SHA-512 oficial do instalador Firefox não foi encontrado.' }
  $officialFirefoxHash = [regex]::Match($officialFirefoxLine, '^\s*([0-9a-fA-F]{128})').Groups[1].Value.ToLowerInvariant()
  if ($officialFirefoxHash -ne $firefoxInstallerSha512) { throw 'O manifesto oficial Firefox divergiu do hash fixado no pipeline.' }
  Invoke-WebRequest -Uri "https://archive.mozilla.org/pub/firefox/releases/$firefoxVersion/win64/en-US/Firefox%20Setup%20$firefoxVersion.exe" -OutFile $installer
  $actualFirefoxHash = (Get-FileHash $installer -Algorithm SHA512).Hash.ToLowerInvariant()
  if ($actualFirefoxHash -ne $firefoxInstallerSha512) { throw "SHA-512 do instalador Firefox divergiu: $actualFirefoxHash" }
  $installerSignature = Get-AuthenticodeSignature $installer
  if ($installerSignature.Status -ne 'Valid' -or $installerSignature.SignerCertificate.Subject -notmatch 'Mozilla') {
    throw 'A assinatura do instalador Firefox não foi validada como Mozilla.'
  }

  if (Test-Path $firefoxDir) { Remove-Item -LiteralPath $firefoxDir -Recurse -Force }
  New-Item -ItemType Directory -Force $firefoxDir | Out-Null
  $extract = Start-Process -FilePath $installer -ArgumentList "/ExtractDir=$firefoxDir" -Wait -PassThru -WindowStyle Hidden
  if ($extract.ExitCode -ne 0) { throw "A extração do Firefox terminou com código $($extract.ExitCode)" }
  $payloadDir = Join-Path $firefoxDir 'core'
  if (-not (Test-Path (Join-Path $payloadDir 'firefox.exe'))) { throw 'O instalador Firefox não extraiu o payload esperado em core/.' }
  Get-ChildItem -LiteralPath $payloadDir -Force | Move-Item -Destination $firefoxDir -Force
  Remove-Item -LiteralPath $payloadDir -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath (Join-Path $firefoxDir 'postSigningData') -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath (Join-Path $firefoxDir 'setup.exe') -Force -ErrorAction SilentlyContinue
  $firefox = Join-Path $firefoxDir 'firefox.exe'
  if (-not (Test-Path $firefox)) { throw 'O MSI não instalou firefox.exe no destino empacotado.' }
  $version = (Get-Item $firefox).VersionInfo.ProductVersion
  if ($version -ne $firefoxVersion) { throw "Firefox instalado na versão inesperada: $version" }
  $firefoxSignature = Get-AuthenticodeSignature $firefox
  if ($firefoxSignature.Status -ne 'Valid' -or $firefoxSignature.SignerCertificate.Subject -notmatch 'Mozilla') {
    throw 'A assinatura do firefox.exe empacotado não foi validada como Mozilla.'
  }

  $driverZip = Join-Path $work "geckodriver-v$geckoVersion-win64.zip"
  $release = Invoke-RestMethod -Uri "https://api.github.com/repos/mozilla/geckodriver/releases/tags/v$geckoVersion" -Headers @{ 'User-Agent' = 'AnimeCaos-release-verifier' }
  $asset = $release.assets | Where-Object { $_.name -eq "geckodriver-v$geckoVersion-win64.zip" } | Select-Object -First 1
  if (-not $asset -or $asset.digest -ne "sha256:$geckoZipSha256") { throw 'Digest da release oficial do GeckoDriver divergiu do hash fixado.' }
  Invoke-WebRequest -Uri "https://github.com/mozilla/geckodriver/releases/download/v$geckoVersion/geckodriver-v$geckoVersion-win64.zip" -OutFile $driverZip
  $actualDriverHash = (Get-FileHash $driverZip -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualDriverHash -ne $geckoZipSha256) { throw "SHA-256 do GeckoDriver divergiu: $actualDriverHash" }
  $driverExtract = Join-Path $work 'geckodriver'
  Expand-Archive -LiteralPath $driverZip -DestinationPath $driverExtract -Force
  $downloadedDriver = Join-Path $driverExtract 'geckodriver.exe'
  $driverSignature = Get-AuthenticodeSignature $downloadedDriver
  if ($driverSignature.Status -ne 'Valid' -or $driverSignature.SignerCertificate.Subject -notmatch 'Mozilla') {
    throw 'A assinatura do geckodriver.exe empacotado não foi validada como Mozilla.'
  }
  Copy-Item -LiteralPath $downloadedDriver -Destination $driverPath -Force
  $driverVersionOutput = (& $driverPath --version | Select-Object -First 1)
  $driverExitCode = $LASTEXITCODE
  if (($null -ne $driverExitCode -and $driverExitCode -ne 0) -or $driverVersionOutput -notmatch [regex]::Escape($geckoVersion)) {
    throw "GeckoDriver respondeu versão inesperada: $driverVersionOutput"
  }
  Write-Output "Firefox $firefoxVersion ($actualFirefoxHash)"
  Write-Output "GeckoDriver $geckoVersion ($actualDriverHash)"
  Write-Output "Firefox bundle: $firefoxDir"
} finally {
  if (Test-Path $work) { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }
}
