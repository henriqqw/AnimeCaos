#ifndef PackageDir
  #error Defina PackageDir para o stage produzido por go run ./cmd/package
#endif
#ifndef AppVersion
  #define AppVersion "3.0.0-dev"
#endif
[Setup]
AppId=com.animecaos.App
AppName=AnimeCaos
AppVersion={#AppVersion}
AppPublisher=AnimeCaos
DefaultDirName={localappdata}\Programs\AnimeCaos
DefaultGroupName=AnimeCaos
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#SourcePath}..\..\release
OutputBaseFilename=AnimeCaos-{#AppVersion}-windows-setup
SetupIconFile={#PackageDir}\icon.ico
UninstallDisplayIcon={app}\AnimeCaos.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
[Files]
Source: "{#PackageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\AnimeCaos"; Filename: "{app}\AnimeCaos.exe"
Name: "{group}\Desinstalar AnimeCaos"; Filename: "{uninstallexe}"
[Run]
Filename: "{app}\bin\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; Flags: waituntilterminated; Check: NeedsWebView2; StatusMsg: "Preparando WebView2…"
Filename: "{app}\AnimeCaos.exe"; Description: "Abrir AnimeCaos"; Flags: nowait postinstall skipifsilent

[Code]
function NeedsWebView2(): Boolean;
var Version: String;
begin
  Result := True;
  if RegQueryStringValue(HKLM32, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) then
    if (Version <> '') and (Version <> '0.0.0.0') then Result := False;
  if RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) then
    if (Version <> '') and (Version <> '0.0.0.0') then Result := False;
end;
