#ifndef PackageDir
  #error Defina PackageDir para o stage produzido por go run ./cmd/package
#endif
#ifndef AppVersion
  #define AppVersion "3.0.2"
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
Filename: "{app}\AnimeCaos.exe"; Description: "Abrir AnimeCaos"; Flags: nowait postinstall skipifsilent
