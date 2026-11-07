; Inno Setup script for Vortex.
; Compile with: ISCC.exe Vortex.iss     (the Inno Setup Compiler CLI)
; Or open Vortex.iss in the Inno Setup GUI and press Compile.

#define MyAppName       "Vortex"
#define MyAppVersion    "0.2.0"
#define MyAppPublisher  "FarAbove420"
#define MyAppExeName    "Vortex.exe"

[Setup]
AppId={{D8E5B6F4-8B5A-4D9C-AC55-VORTEX0001000}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}.0
VersionInfoProductVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoProductName={#MyAppName}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=Vortex-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=assets\Vortex.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; PyInstaller is configured for one-file mode (see Vortex-win.spec), so the
; whole app is a single self-contained Vortex.exe at dist\Vortex.exe.
Source: "dist\Vortex.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";          Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}";Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";    Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
