; Script Inno Setup para Tardis
; Requiere Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
;
; Uso:
;   1. Ejecutar primero: python build.py
;   2. Luego compilar con: iscc installer\tardis_setup.iss
;   O usar: python build.py --installer
;
; NOTA: MyAppVersion se pasa dinámicamente desde build.py mediante /d.
;       Si se compila manualmente sin /d, se usa el valor por defecto.

#define MyAppName "Tardis"
#ifndef MyAppVersion
# define MyAppVersion "0.1.0"
#endif
#define MyAppPublisher "Tardis"
#define MyAppURL "https://tardis.app"
#define MyAppExeName "Tardis.exe"

[Setup]
AppId={{B8F7A3D2-1C4E-4F5A-9B6C-7D8E9F0A1B2C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=
OutputDir=..\dist\installer
OutputBaseFilename=Tardis-v{#MyAppVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\Tardis\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\.env.example"; DestDir: "{app}"; DestName: ".env.example"; Flags: ignoreversion

[Icons]
Name: "{group}\Tardis"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar Tardis"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Tardis"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Ejecutar Tardis ahora"; Flags: postinstall nowait skipifsilent
