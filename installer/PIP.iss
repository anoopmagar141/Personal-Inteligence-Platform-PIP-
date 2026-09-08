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
; Where the built payload is. Overridable with ISCC /DDistDir=..., which is how
; scripts\build_installer.ps1 passes a SHORT path - and it has to.
;
; Windows still limits a path to 260 characters for most callers, ISCC among
; them. torch ships license files for its vendored dependencies nested nine
; directories deep:
;
;   torch-2.13.0.dist-info\licenses\third_party\kineto\libkineto\third_party\
;   dynolog\third_party\prometheus-cpp\3rdparty\civetweb\src\third_party\
;   duktape-1.8.0\LICENSE.txt
;
; That is 272 characters once this project's own directory name and the
; installer\..\dist\PIP\ detour are in front of it, and the compiler fails
; with "The system cannot find the path specified" - which reads like a missing
; file and is not one.
;
; The fix is to stage the payload somewhere short rather than to drop the
; files. They are licences: PIP redistributes torch, so torch's notices travel
; with it.
#ifndef DistDir
  #define DistDir "..\dist\PIP"
#endif

[Setup]
; Stable across versions - it is what makes an upgrade replace an install
; rather than sit beside it. Never regenerate this for an existing product.
;
; AND NEVER TEST-INSTALL A BUILD TO A SECOND DIRECTORY ON A MACHINE THAT HAS A
; REAL ONE. Windows keys the installation off this id, not off the path, so a
; /DIR= install is not a separate copy - it is the same application moved. Its
; uninstaller then owns the registration, and running it strips the program
; files out of the original location. Learned by doing it: the data survived,
; because data\ is not something the uninstaller removes, but the install
; itself had to be put back. Verify test builds in a VM, or accept that the
; machine's own installation is the thing being replaced.
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

; The mark, on the installer itself and on the entry in Apps & Features.
; Generated from installer\pip-iris-blue.svg by scripts\make_icons.py - the
; artwork is the source, and the .ico is checked in beside it so a build never
; depends on regenerating one.
;
; The window and shortcut icons come from the executable instead: Flutter
; compiles windows\runner\resources\app_icon.ico into it, and pointing the
; shortcuts at the exe means a shortcut cannot disagree with the window it
; opens.
SetupIconFile=pip.ico
WizardSmallImageFile=wizard-small.bmp,wizard-small-2x.bmp

; EVERY PAGE THIS WIZARD DOES NOT SHOW, AND WHY
;
; It used to ask four questions before it would install anything: a welcome
; page, where to put it, which shortcuts to make, and a confirmation. Every one
; of them asks something a first-time user has no basis to answer - they do not
; yet know what PIP is, so "where should it go" is not a question they can have
; an opinion about. Four screens of clicking Next is not a choice being offered,
; it is a toll.
;
; So there is one screen: the progress bar, and then the finish page. That last
; one stays because it is the only page that does anything - it starts PIP, and
; it offers Ollama to a machine that has not got it.
;
; Nothing is lost that anybody wanted. The install location is per-user and
; fixed for the reason at the top of this file; a Desktop shortcut is what
; somebody double-clicking an installer expects; and the restore shortcut lives
; in the Start menu where it costs nobody anything. An advanced user can still
; pass /DIR= on the command line, which is where that choice belongs.
DisableWelcomePage=yes
DisableDirPage=yes
DisableReadyPage=yes
; ~1.1 GB extracted. Stated so the wizard can refuse before it fills a disk.
ExtraDiskSpaceRequired=0
DirExistsWarning=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; No [Tasks] section, deliberately - it is what put the shortcuts page in the
; wizard. Both shortcuts are now always created: a Desktop icon is what
; somebody double-clicking an installer is expecting, and the restore shortcut
; sits in the Start menu folder where it is out of the way until the day it is
; the only way back in.

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
    WorkingDir: "{app}"; IconFilename: "{app}\app\{#AppExeName}"; Comment: "Start PIP"

; Deliberately NOT hidden, and deliberately optional. A restore is a
; conversation - it asks for two passwords and prints what it is about to
; replace - and it happens on a machine where PIP is not running, because
; restore_backup.py refuses while PIP holds the database open.
Name: "{group}\Restore {#AppName} from backup"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
    Parameters: "-ExecutionPolicy Bypass -NoProfile -File ""{app}\scripts\restore_pip.ps1"""; \
    WorkingDir: "{app}"; Comment: "Rebuild PIP's database from a .pipbak backup file"

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
