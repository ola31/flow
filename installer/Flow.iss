; Inno Setup script for Flow — wraps PyInstaller --onedir output into Setup.exe.
;
; Inputs (passed via /D on iscc command line):
;   AppVersion  e.g. "0.1.0"  — version string shown in 제어판
;   SourceDir   e.g. "..\dist\Flow"  — folder produced by PyInstaller (--onedir)
;   OutputDir   e.g. "..\dist"  — where Setup.exe is written
;
; Run example:
;   iscc /DAppVersion=0.1.0 /DSourceDir="..\dist\Flow" /DOutputDir="..\dist" Flow.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\Flow"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif

#define AppName       "Flow"
#define AppPublisher  "Flow"
#define AppExeName    "Flow.exe"

[Setup]
AppId={{B0A1F4F8-3F3D-4A6A-9F2D-FLOW00000001}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=Flow-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
LicenseFile=..\LICENSE
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#AppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Recursively copy entire PyInstaller --onedir output into install dir.
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent
