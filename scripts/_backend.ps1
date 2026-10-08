# Finding PIP's backend, and stopping it (FREEZE_LIST D-09).
#
# WHY THIS EXISTS
# ---------------
# Nothing stops the backend when the window closes. launch_pip.ps1 starts it
# hidden, the Flutter app has no exit hook and the backend has no shutdown
# route, so "close PIP" closes a window and leaves the process, its lock and its
# open database where they were. That broke two things that tell the person to
# "close PIP":
#
#   * An in-app restore is converted at once and installed by the lifespan of
#     the NEXT backend, before anything opens a database. Opening PIP again
#     found the port listening, reported "already running" and started nothing,
#     so the restore waited for a reboot or a crash.
#   * The first-run "Import existing PIP" sends the person to the "Restore PIP
#     from backup" shortcut, and restore_backup.py refuses while the backend
#     holds the lock - on the one machine that screen is shown on, where PIP has
#     just been launched.
#
# HOW A BACKEND IS RECOGNISED
# ---------------------------
# By what owns the port AND what that process was started as: its command line
# has to name backend.api.server, which is how launch_pip.ps1 starts it. The
# port alone is not enough. Port 8765 is a number somebody else's program can
# own, and a script that kills whatever owns it is the kind that is run once.
# Anything that is not recognised is left alone and reported as "not-pip".
#
# WHY THE STOP IS NOT GRACEFUL
# ----------------------------
# There is no route or signal to ask for one: the process is hidden and has no
# console to send Ctrl+C to, and a shutdown route would be a new endpoint that
# ends the process for anybody holding the token. What a hard stop costs is
# bounded and already designed for: SQLite commits are durable per transaction;
# a conversation whose Observer pass had not run is found again at the next
# start (session_lifecycle.recover_unobserved_conversations); and a restore's
# swap moves the replaced database's -wal aside with it (D-01). It is only done
# when somebody has just closed the window and asked for a restore to be
# applied, or answered "yes" to being asked.
#
# The port is read from PIP_PORT when set, which exists for the tests that run
# these scripts against a stand-in; nothing else sets it, and the application's
# own address is fixed at 8765.

function Get-PipPort {
    if ($env:PIP_PORT) { return [int]$env:PIP_PORT }
    return 8765
}

# The process listening on $Port, if it is PIP's backend; otherwise nothing.
function Get-PipBackendProcess {
    param([int]$Port = (Get-PipPort))
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $listener) { return $null }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
    if ($process -and $process.CommandLine -match 'backend\.api\.server') { return $process }
    return $null
}

function Test-PipPortListening {
    param([int]$Port = (Get-PipPort))
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

# Stops PIP's backend and waits for its port to be free. Returns one of:
#   not-running   nothing is listening
#   not-pip       something is, and it is not PIP's backend - left alone
#   stopped       PIP's backend was stopped and the port is free
#   stuck         it was told to stop and the port is still held
function Stop-PipBackend {
    param([int]$Port = (Get-PipPort), [int]$WaitSeconds = 20)

    if (-not (Test-PipPortListening -Port $Port)) { return "not-running" }
    $backend = Get-PipBackendProcess -Port $Port
    if (-not $backend) { return "not-pip" }

    # /T: the venv's python.exe is a launcher that starts the interpreter as a
    # child, and the child is what listens. The tree goes together.
    & taskkill.exe /F /T /PID $backend.ProcessId 2>&1 | Out-Null

    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    while ((Get-Date) -lt $deadline) {
        if (-not (Test-PipPortListening -Port $Port)) { return "stopped" }
        Start-Sleep -Milliseconds 250
    }
    return "stuck"
}

# For launch_pip.ps1: a staged restore is installed by a NEW backend, so a
# running one has to go before the launch decides it can reuse it. Returns
# no-restore-pending when there is nothing to apply (and touches nothing), and
# otherwise whatever Stop-PipBackend returned.
function Restart-PipBackendIfRestorePending {
    param([string]$DataDir, [int]$Port = (Get-PipPort))
    if (-not (Test-Path (Join-Path $DataDir "pending-restore.json"))) { return "no-restore-pending" }
    return (Stop-PipBackend -Port $Port)
}
