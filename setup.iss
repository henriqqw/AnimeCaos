[Setup]
AppName=AnimeCaos
AppVersion=0.1.3
AppPublisher=AnimeCaos
AppPublisherURL=https://animecaos.vercel.app
DefaultDirName={autopf}\AnimeCaos
DefaultGroupName=AnimeCaos
OutputDir=installer
OutputBaseFilename=Setup_AnimeCaos_v0.1.3
Compression=lzma2/ultra
SolidCompression=yes
SetupIconFile=public\icon.ico
UninstallDisplayIcon={app}\AnimeCaos.exe
WizardStyle=modern
PrivilegesRequired=lowest

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\AnimeCaos\AnimeCaos.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\AnimeCaos\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\AnimeCaos"; Filename: "{app}\AnimeCaos.exe"; IconFilename: "{app}\_internal\public\icon.ico"
Name: "{group}\{cm:UninstallProgram,AnimeCaos}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\AnimeCaos"; Filename: "{app}\AnimeCaos.exe"; Tasks: desktopicon; IconFilename: "{app}\_internal\public\icon.ico"

[Run]
Filename: "{app}\AnimeCaos.exe"; Description: "{cm:LaunchProgram,AnimeCaos}"; Flags: nowait postinstall skipifsilent
