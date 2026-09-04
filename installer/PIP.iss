; PIP - Inno Setup script
;
; Compiled by scripts\build_installer.ps1, which builds dist\PIP first and
; then points ISCC at this file. Compiling it directly works too, as long as
; dist\PIP already exists.
;
; WHY THIS INSTALLS PER-USER AND NOT INTO PROGRAM FILES
;
; PIP keeps its state in data\ inside its own folder: the encrypted database,
; the salt, the API token, the instance lock, the startup progress file. A
; standard user cannot write to Program Files, so an installation there would
; produce an application that opens and then cannot create the database it
; exists to protect - and it would ask for an administrator prompt to do it.
;
; So it installs to %LocalAppData%\Programs\PIP with PrivilegesRequired=lowest,
; which is where a per-user application belongs and what several well-known
; desktop applications do for the same reason. No UAC prompt, no admin rights,
; and the data directory is writable by the person who installed it.
;
; WHY UNINSTALLING LEAVES data\ BEHIND
;
; Everything a person has ever told PIP is in there, encrypted under a password
; that cannot be recovered. Uninstalling an application is not consent to
; destroy the data it held, and somebody reinstalling to fix a problem would
; find their memory gone. Inno removes what it installed; data\ was written at
; runtime, so it survives, and the uninstaller says where it is.

#define AppName "PIP"
#define AppVersion "1.0.0"
#define AppPublisher "Anup Magar"
#define AppExeName "pip_flutter_client.exe"
#define DistDir "..\dist\PIP"

[Setup]
; Stable across versions - it is what makes an upgrade replace an install
; rather than sit beside it. Never regenerate this for an existing product.
AppId={{7B3C1E62-9F44-4A57-BD18-2E6C0A9F5D31}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; No admin rights: see the header. This is the setting the whole install
; location decision follows from.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=PIP-Setup
; LZMA2/max because the payload is about a gigabyte of Python and native
; extensions, which compresses well and is downloaded once.
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; The application is 64-bit and so is the interpreter beside it.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\app\{#AppExeName}
; ~1.1 GB extracted. Stated so the wizard can refuse before it fills a disk.
ExtraDiskSpaceRequired=0
DirExistsWarning=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "restoreicon"; Description: "Create a shortcut for &restoring from a backup"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
; The whole portable build. data\ is deliberately not listed: it is created on
; first run, and shipping one would hand every user a copy of the developer's
; database and a salt that will not match the password they are about to
; choose.
Source: "{#DistDir}\python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#DistDir}\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#DistDir}\backend\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#DistDir}\config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#DistDir}\scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#DistDir}\shared\*"; DestDir: "{app}\shared"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; Created empty and left alone by the uninstaller.
Name: "{app}\data"

[Icons]
; Every shortcut goes through launch_pip.ps1 rather than straight to the .exe:
; the application needs its backend, and the launcher is what starts Ollama,
; the backend and the window in that order. -WindowStyle Hidden because the
; launcher's whole premise is that starting PIP shows no console - it no longer
; asks for anything, so there is nothing for a console to be needed for.
Name: "{group}\{#AppName}"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
    Parameters: "-ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\scripts\launch_pip.ps1"""; \
    WorkingDir: "{app}"; IconFilename: "{app}\app\{#AppExeName}"; Comment: "Start PIP"

Name: "{autodesktop}\{#AppName}"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
    Parameters: "-ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\scripts\launch_pip.ps1"""; \
    WorkingDir: "{app}"; IconFilename: "{app}\app\{#AppExeName}"; Comment: "Start PIP"; Tasks: desktopicon

; Deliberately NOT hidden, and deliberately optional. A restore is a
; conversation - it asks for two passwords and prints what it is about to
; replace - and it happens on a machine where PIP is not running, because
; restore_backup.py refuses while PIP holds the database open.
Name: "{group}\Restore {#AppName} from backup"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
    Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\scripts\restore_pip.ps1"""; \
    WorkingDir: "{app}"; Comment: "Rebuild PIP's database from a .pipbak backup file"; Tasks: restoreicon

Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
    Parameters: "-ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\scripts\launch_pip.ps1"""; \
    WorkingDir: "{app}"; Description: "Start {#AppName} now"; Flags: postinstall nowait skipifsilent

; PIP answers with a local model, which means a model runtime. Offered as a
; link rather than a bundled installer: Ollama is a few hundred megabytes that
; would treble this download for everybody, including the people who already
; have it. The application already handles its absence - the launcher reports
; it and still opens the window, and the model browser is what a person uses
; once it is there.
Filename: "https://ollama.com/download"; \
    Description: "Get Ollama, the local model runtime {#AppName} uses"; \
    Flags: postinstall shellexec nowait skipifsilent unchecked

[UninstallDelete]
; Runtime files that are not user data: logs and the progress file the launch
; screen reads. The database, the salt and the profiles are NOT listed - see
; the header for why.
Type: files; Name: "{app}\data\backend.log"
Type: files; Name: "{app}\data\backend.err.log"
Type: files; Name: "{app}\data\startup.jsonl"
Type: files; Name: "{app}\data\pip.lock"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{app}\data');
    if DirExists(DataDir) then
      MsgBox('PIP has been removed.' + #13#10 + #13#10 +
             'Your encrypted data has been left in place:' + #13#10 +
             DataDir + #13#10 + #13#10 +
             'Delete that folder yourself if you want it gone. It cannot be ' +
             'recovered without your password, and nothing else can read it.',
             mbInformation, MB_OK);
  end;
end;
