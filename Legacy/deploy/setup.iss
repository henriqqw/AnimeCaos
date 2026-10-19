; This script lives in deploy/, but dist/, installer/ and public/ are all at
; the repo root — RepoRoot resolves that regardless of what directory ISCC
; is invoked from (SourcePath is the directory containing this .iss file).
#define RepoRoot SourcePath + "..\"

[Setup]
AppName=AnimeCaos
AppVersion=2.0.0
AppPublisher=AnimeCaos
AppPublisherURL=https://animecaos.vercel.app
DefaultDirName={autopf}\AnimeCaos
DefaultGroupName=AnimeCaos
OutputDir={#RepoRoot}installer
OutputBaseFilename=Setup_AnimeCaos_v2.0.0
Compression=lzma2/ultra
SolidCompression=yes
SetupIconFile={#RepoRoot}public\icon.ico
UninstallDisplayIcon={app}\AnimeCaos.exe
WizardStyle=modern
PrivilegesRequired=lowest

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#RepoRoot}dist\AnimeCaos\AnimeCaos.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}dist\AnimeCaos\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\AnimeCaos"; Filename: "{app}\AnimeCaos.exe"; IconFilename: "{app}\_internal\public\icon.ico"
Name: "{group}\{cm:UninstallProgram,AnimeCaos}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\AnimeCaos"; Filename: "{app}\AnimeCaos.exe"; Tasks: desktopicon; IconFilename: "{app}\_internal\public\icon.ico"

[Run]
Filename: "{app}\AnimeCaos.exe"; Description: "{cm:LaunchProgram,AnimeCaos}"; Flags: nowait postinstall skipifsilent
