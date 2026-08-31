# Point git at the hooks tracked in this repository.
#
# Run once per clone:
#     powershell -ExecutionPolicy Bypass -File scripts/install_hooks.ps1
#
# Git never runs hooks straight from a clone - that would let any repository you
# clone execute code on checkout - so this has to be a deliberate step. What it
# does NOT do is copy anything into .git/hooks. A copy is a second version that
# drifts: scripts/pre-commit and .git/hooks/pre-commit happened to be identical
# here, but nothing was keeping them that way, and the one git actually ran was
# the untracked one nobody reviews. core.hooksPath makes the tracked file the
# one that runs, so editing it is the whole of updating it.
#
# The hook enforces ADR-025: nothing under backend/stages/ or backend/api/ may
# depend directly on the database, ChromaDB or Ollama drivers.

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

git config core.hooksPath scripts

$stale = Join-Path $repoRoot ".git/hooks/pre-commit"
if (Test-Path $stale) {
    Remove-Item $stale
    Write-Host "Removed the stale copy at .git/hooks/pre-commit - it is bypassed now and would only confuse."
}

Write-Host "core.hooksPath -> $(git config core.hooksPath)"
Write-Host "ADR-025 pre-commit hook active."
