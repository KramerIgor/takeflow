#ifndef MyAppVersion
  #error Build this installer through scripts\build_windows_installer.ps1 so MyAppVersion is generated from app.version.
#endif

#define MyAppName "Takeflow"
#define MyAppPublisher "IOKRAMER"
#define MyAppExeName "Takeflow.exe"
#define MyAppSourceDir "..\dist\takeflow"

[Setup]
AppId={{F28E45B4-3E55-4F17-9D7C-A0C2F0010100}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Takeflow
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=no
OutputDir=..\dist\installer
OutputBaseFilename=TakeflowSetup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: checkedonce

[Files]
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
