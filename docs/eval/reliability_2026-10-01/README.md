# Reliability validation harness (2026-10-01)

Evidence for `docs/eval/reliability_validation_2026-10-01.md`. Not part of
the suite: the probe files are named `probe_*.py`, so neither
`pytest backend/tests` nor a bare `pytest` collects them. Several are
**expected to fail** on the current code — each failure is a recorded
defect (D-xx), and the probe becomes that defect's regression test once a
fix is authorized.

Every run uses isolated data directories (the suite's own
`isolated_data_dir` fixture, or a fresh root per journey). Nothing here
reads or writes the contents of the real `data/`; the
migration harness lists its file names, sizes and times before and after
each run, to show it was untouched. Passwords and names are synthetic.

`pip_embed_shim.py` replaces `sentence_transformers` with a hashed
bag-of-words encoder, because Smart App Control blocks torch on the machine
this ran on (D-02). Results about retrieval quality are invalid under it.

Run from the repository root (PowerShell; `$H` is this folder):

```
$env:PYTHONPATH = "$H"
.venv\Scripts\python.exe -m pytest -c pytest.ini --rootdir=. -p pip_embed_shim -s -q `
    $H\probes\probe_consent.py $H\probes\probe_boundaries.py `
    $H\probes\probe_provider_failures.py $H\probes\probe_reintroduction.py
```

Real-process journeys (need Ollama with `qwen2.5:7b`; each takes a fresh
root directory as its argument):

```
.venv\Scripts\python.exe $H\journey_AE.py <empty dir>   # new user, stop, force-kill, recovery
.venv\Scripts\python.exe $H\journey_R.py  <empty dir>   # D-05
.venv\Scripts\python.exe $H\journey_CD.py <empty dir>   # profiles, export, restore x2 (D-01, D-07)
```

The migration re-run of 2026-10-03 (`docs/eval/migration_rerun_2026-10-03.md`,
FREEZE_LIST §7.24) lives in `migration/`. Unlike `journey_CD.py`, each
computer there is a throwaway *installation* built from one pinned commit
(`git archive`), with its own interpreter, and the export and the shortcut
restore go through the real launchers (`export_pip.ps1`, `restore_pip.ps1`).
`migration/sitecustomize.py` is a test hook loaded only by those throwaway
interpreters: it answers `getpass` prompts from `PIP_TEST_ANSWERS`, because
`getpass` reads the console, not a pipe.

```
.venv\Scripts\python.exe $H\migration\journey_migration.py <variant> <empty dir> [commit]
.venv\Scripts\python.exe $H\migration\probe_export_while_running.py <empty dir> [commit]   # D-17
```

Variants: `main-killed`, `main-graceful`, `shortcut`, `shortcut-shipped`
(D-21), `multi-profile-export`, `restore-over-used` (D-20), `same-machine`
(D-07), `inputs-and-delete` (D-11, D-18, D-14), `staging` (D-18, D-19). Each
writes `results.json` with every check and the commit it ran at. Give a
commit before a fix to see the harness catch it (`405b10b` for D-03,
`044fafc` for D-14). The record's tenth run, main-killed under a path with
spaces, parentheses and non-ASCII characters, is `main-killed` given such
an `<empty dir>` (for example `...\run path (é ü)`).

`probe_restore_wal.py` (D-01) needs a backup made by `journey_CD.py`:
set `PIP_PROBE_BACKUP=<dir>\zarqa-1.pipbak` (backup password
`backup-pw-zz9`).

| File | Covers | Expected on `f66a309` |
|---|---|---|
| `probe_consent.py` | Promise 6 through the real pipeline | C4, C5 fail (D-04); 8 pass. Since the D-04 fix (FREEZE_LIST §7.21): C4 passes, and C5 stops at `add_endpoint` with the new refusal of a built-in id - reported as a failure only because this probe predates the refusal. The permanent tests are in `backend/tests/test_consent_before_sending.py` |
| `probe_boundaries.py` | route auth census, WS, traversal, ownership, document delete | D1 fails (D-06); 28 pass |
| `probe_provider_failures.py` | missing model, Ollama down, Ollama hung | 3 pass |
| `probe_reintroduction.py` | dismissed / duplicate pending questions | RI1 ×4 fail (D-12); RI2 ×4 pass |
| `probe_restore_wal.py` | restore over a stale `-wal` | stale-wal fails (D-01); control passes |
| `probe_cache_race.py` (added 2026-10-02) | an answer written to the cache after sign-out cleared it (D-15, FREEZE_LIST §7.19) | Before the D-15 fix: write-delayed-1s fails every run (the next profile is served the signed-out profile's answer), and no-delay fails intermittently, as the §7.9 test does. Since the fix (FREEZE_LIST §7.20) both pass |
| `d03_make_profile.py`, `d03_run_export.py` | D-03: copy `scripts/`, `backend/`, `shared/`, `config/` to an empty root, `d03_make_profile.py <root>` registers one profile, set `last_used` to it, then run `export_backup.py` with the arguments `export_pip.ps1:62` would pass (none, for one profile) through `d03_run_export.py` | `ERROR: no database at <root>\data\pip.db`; with `--db-path` and `PIP_SALT_PATH` the backup is written |
| `migration/journey_migration.py` (added 2026-10-03) | the supported migration end to end through the real launchers (FREEZE_LIST §7.24) | At `9968e8c`: `main-*`, `multi-profile-export` and the non-ASCII path pass; an export taken while the app commits rows can fail verification (D-17, timing-dependent); `shortcut-shipped` fails for D-21, `restore-over-used` for D-20, `same-machine` for D-07; `inputs-and-delete` fails for the empty file (D-18) and three 500s (D-11); `staging` fails for D-18 and D-19 |
| `migration/probe_export_while_running.py` (added 2026-10-03) | an export with one row written by the running app during the backup-password prompt (D-17) | At `5cc54df` and `9968e8c`: the control verifies; the write case exits 1 saying "Nothing was written" and leaves a valid backup; a retry the same day succeeds |
