# PIP Flutter client

PIP is a local-first desktop AI assistant. The Flutter Windows app connects to
the local PIP backend at `http://127.0.0.1:8765`.

## Launch PIP

Run these commands from the project root (`Personal Inteligence Platform (PIP)`).

### Normal user launch

Starts PIP without visible Ollama or backend terminal windows:

```powershell
.\scripts\launch_pip.ps1
```

### Developer launch

Starts the Flutter app in debug mode, with visible backend and Ollama terminals
and backend hot reload:

```powershell
.\scripts\run_dev.ps1
```

The developer terminals are intentional: one runs Ollama and the other runs
the FastAPI backend and its live logs.

## If your terminal is already in `frontend\flutter`

Use either launcher by going up two directories:

```powershell
# Normal user launch
..\..\scripts\launch_pip.ps1

# Developer launch
..\..\scripts\run_dev.ps1
```

The filenames use an underscore: `launch_pip.ps1` and `run_dev.ps1`.

## Signing in

Neither launcher asks for a profile name or a password in PowerShell. PIP opens
locked, then the sign-in screen lets the user choose a profile and enter that
profile's password.
