param(
  [Parameter(Mandatory = $true)][string]$Stage,
  [Parameter(Mandatory = $true)][string]$Version,
  [Parameter(Mandatory = $true)][string]$Platform,
  [Parameter(Mandatory = $true)][string]$Architecture
)

$ErrorActionPreference = "Stop"
$stagePath = (Resolve-Path -LiteralPath $Stage).Path
$manifestPath = Join-Path $stagePath "release-manifest.json"
$files = @(
  Get-ChildItem -LiteralPath $stagePath -File -Recurse |
    Where-Object { $_.FullName -ne $manifestPath } |
    Sort-Object FullName |
    ForEach-Object {
      $relative = [IO.Path]::GetRelativePath($stagePath, $_.FullName).Replace('\', '/')
      [ordered]@{
        path = $relative
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        size = [int64]$_.Length
      }
    }
)
$manifest = [ordered]@{
  version = $Version
  platform = $Platform
  arch = $Architecture
  created = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
  files = $files
}
$json = ConvertTo-Json -InputObject $manifest -Depth 8
[IO.File]::WriteAllText($manifestPath, $json + "`n", [Text.UTF8Encoding]::new($false))
