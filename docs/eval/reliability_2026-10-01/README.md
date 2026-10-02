# Reliability validation harness (2026-10-01)

Evidence for `docs/eval/reliability_validation_2026-10-01.md`. Not part of
the suite: the probe files are named `probe_*.py`, so neither
`pytest backend/tests` nor a bare `pytest` collects them. Several are
**expected to fail** on the current code — each failure is a recorded
defect (D-xx), and the probe becomes that defect's regression test once a
fix is authorized.

Every run uses isolated data directories (the suite's own
`isolated_data_dir` fixture, or a fresh root per journey). Nothing here
reads or writes the real `data/`. Passwords and names are synthetic.

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

`probe_restore_wal.py` (D-01) needs a backup made by `journey_CD.py`:
set `PIP_PROBE_BACKUP=<dir>\zarqa-1.pipbak` (backup password
`backup-pw-zz9`).

| File | Covers | Expected on `f66a309` |
|---|---|---|
| `probe_consent.py` | Promise 6 through the real pipeline | C4, C5 fail (D-04); 8 pass |
| `probe_boundaries.py` | route auth census, WS, traversal, ownership, document delete | D1 fails (D-06); 28 pass |
| `probe_provider_failures.py` | missing model, Ollama down, Ollama hung | 3 pass |
| `probe_reintroduction.py` | dismissed / duplicate pending questions | RI1 ×4 fail (D-12); RI2 ×4 pass |
| `probe_restore_wal.py` | restore over a stale `-wal` | stale-wal fails (D-01); control passes |
| `d03_make_profile.py`, `d03_run_export.py` | D-03: copy `scripts/`, `backend/`, `shared/`, `config/` to an empty root, `d03_make_profile.py <root>` registers one profile, set `last_used` to it, then run `export_backup.py` with the arguments `export_pip.ps1:62` would pass (none, for one profile) through `d03_run_export.py` | `ERROR: no database at <root>\data\pip.db`; with `--db-path` and `PIP_SALT_PATH` the backup is written |
