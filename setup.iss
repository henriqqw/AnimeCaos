[Setup]
; Basic setup info
AppName=Animecaos
AppVersion=0.1.0
AppPublisher=Henri
DefaultDirName={autopf}\Animecaos
DefaultGroupName=Animecaos
OutputDir=installer
OutputBaseFilename=Setup_Animecaos
Compression=lzma2/ultra
SolidCompression=yes
SetupIconFile=public\icon.ico
UninstallDisplayIcon={app}\Animecaos.exe

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The main executable block
Source: "dist\Animecaos\Animecaos.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Animecaos\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Animecaos"; Filename: "{app}\Animecaos.exe"; IconFilename: "{app}\public\icon.ico"
Name: "{group}\{cm:UninstallProgram,Animecaos}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Animecaos"; Filename: "{app}\Animecaos.exe"; Tasks: desktopicon; IconFilename: "{app}\public\icon.ico"

[Run]
Filename: "{app}\Animecaos.exe"; Description: "{cm:LaunchProgram,Animecaos}"; Flags: nowait postinstall skipifsilent
