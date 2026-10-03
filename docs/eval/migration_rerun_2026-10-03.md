# Migration journey re-run — 2026-10-03

The end-to-end migration that the 2026-10-01 validation pass found failing
(`reliability_validation_2026-10-01.md` §11, §17; FREEZE_LIST §7.16), run
again after the fixes for D-01 (§7.17), D-03 (§7.18) and D-14 (§7.22).
**Report only: no production code was changed.** Every finding below is a
recommendation; fixing any of it needs a separate owner authorization
(FREEZE_LIST §2.4). The summary is FREEZE_LIST §7.24.

## 1. Summary

**The data round trip works.** In real backend processes at `9968e8c` (and
before that at `5cc54df`), a profile is exported through the script the
Backup screen launches, restored in the app on another installation, and
the backend restarted, cleanly and by force-kill with a chat open. It is
then used, exported again from a one-profile installation and restored on a
third. Each time it arrives with:

- conversations, decisions (with reasoning), projects (with descriptions),
  the active model, profile fields and document names comparing equal;
- every document written back under the new machine's own data folder,
  byte for byte, and found again by retrieval;
- the new password opening it, and the old and the backup's refused;
- the replaced database kept aside with its `-wal`/`-shm`.

D-01 and D-03 hold in real processes, and D-14 holds for the restore its
fix covers. An export from a two-profile installation, taken from the
second profile with the first one's environment inherited, exports the
right person. The desktop-shortcut restore onto a bare installation works,
and so does carrying on from the layout it creates.

**The exit criterion is not met as worded** (§9). "Close PIP and open it
again", the restart the app asks for, does not apply a restore (D-09, open),
and five new defects sit on the backup and restore path:

| ID | Severity | One line |
|---|---|---|
| D-18 | Medium | An empty (0-byte) file is accepted as a backup ("0 rows across 0 tables, checked and ready"), and at the next backend start the profile is replaced by an empty one. A backup is checked only against itself, so a part-written export passes too |
| D-20 | Medium (upper end) | An in-app restore over a profile that already has a document of the same name takes that file instead of the backup's, and the first sign-in overwrites the backup's copy with it |
| D-21 | Medium (low end) | The desktop shortcut, given two backups from one day, restores the older while saying "the newest will be used" |
| D-17 | Low (upper) | An export taken while the app is committing rows fails verification, and the launcher says "Nothing was written" while a valid backup is left, unmarked, at the top of the Backups list |
| D-19 | Low | Staged-restore state is one per installation but is shown, cancelled and replaced as the signed-in profile's: one profile can cancel another's restore, and an orphaned staged copy survives its profile's deletion |

D-11 has two more instances (API-only). D-07 reproduces unchanged.

## 2. Method

Each simulated computer is a throwaway installation built by
`docs/eval/reliability_2026-10-01/migration/journey_migration.py`:

- copies of `backend/`, `shared/`, `config/` and the seven scripts the
  launchers need, all exported from **one pinned commit** with
  `git archive`, never from the working tree (§8);
- its own interpreter in `.venv`, and its own empty `data/`;
- its backend started the way `launch_pip.ps1` starts it: that
  installation's interpreter, the installation root as working directory,
  and only the profile variables `Set-PipProfileEnvironment` sets for the
  last-opened profile. Everything else falls to the module defaults, which
  a copied backend resolves inside its own installation (checked as each
  installation is built).

Driven through:

- **export:** the real `scripts/export_pip.ps1` → `export_backup.py`, run
  directly. Not the Backup screen's button, which starts it through
  `cmd /c start` from the app's own process; the multi-profile variant
  passes down the variables that process would carry;
- **in-app restore:** `POST /backup/restore`, then a backend restart. The
  harness stops and starts the backend itself. The app's own instruction,
  "Close PIP and open it again", reuses the running backend (D-09), so in
  real use the restore applies at the next reboot, crash or logoff;
- **desktop-shortcut restore:** the real `restore_pip.ps1` →
  `restore_backup.py`, both with `--from --yes` and as the shortcut runs it
  (no arguments, typed `yes`);
- **chat:** `/ws/chat` with a live local model (Ollama, `qwen2.5:7b`).

Only the console password prompts are answered by a test hook
(`migration/sitecustomize.py`), because `getpass` reads the console, not a
pipe. Embeddings come from the stand-in (`pip_embed_shim.py`), because Smart
App Control blocks torch here (D-02). Retrieval checks therefore show that a
document's own words come back, not retrieval quality.

**Safety.** No `PIP_*` variable pointed at the repository's `data/`, the
launchers ran with `PIP_*` and `PYTHONPATH` removed (except the variables
the multi-profile variant passes down on purpose, all inside its
installation), and every run fingerprinted the real `data/` (names, sizes,
times; never contents) before and after: untouched in every run.

## 3. Results

At `9968e8c` (HEAD when run):

| Variant | What it does | Checks | Failed | Failures are |
|---|---|---|---|---|
| main-killed | export → in-app restore on machine 2 → force-kill with a chat open → verify → keep using → export from a one-profile installation → restore on machine 3 → verify | 43 | 0 | — |
| main-graceful | the same with a clean stop | 42 | 0 | — |
| main-killed, path | the same under an installation path with spaces, parentheses and `é ü` | 43 | 0 | — |
| multi-profile-export | two profiles; the app launched on the first; export from the second with the first's `PIP_*` inherited; restore | 22 | 0 | — |
| shortcut | export → `restore_pip.ps1 --from --yes` onto a bare installation → verify → keep using → export from the original layout → in-app restore on machine 5 → verify | 37 | 1 | D-17 |
| shortcut-shipped | the shortcut as installed: two backups from one day; then onto an installation with a named profile | 11 | 2 | D-21 |
| same-machine | restore into a second profile beside the original document | 14 | 1 | D-07 |
| restore-over-used | in-app restore over a profile with its own documents | 22 | 3 | D-20 |
| inputs-and-delete | 11 bad backups and passwords, each alone; D-14 with a control | 50 | 5 | D-18 ×2, D-11 ×3 |
| staging | D-18 to its end; staging twice; two profiles; whose restore; an orphan and its profile's deletion; an empty file through the shortcut | 23 | 11 | D-18 ×3, D-19 ×8 |

307 checks, 23 failed, every failure attributed. `probe_export_while_running.py`
(D-17) behaves as at `5cc54df`.

Six of the variants also ran at `5cc54df` (main-killed, main-graceful,
same-machine, inputs-and-delete, staging, and shortcut in its earlier
19-check form without the original-layout leg) and gave the same verdicts,
except D-17's, which depends on timing. multi-profile-export,
shortcut-shipped, restore-over-used and the non-ASCII path ran only at
`9968e8c`.

**Negative controls.** The harness at commits before the fixes:

| Control | Commit | What failed |
|---|---|---|
| D-03: main-killed | `405b10b` (before §7.18) | the first export: no profile chosen, no file written; the journey stops there (3 of 7 checks) |
| D-14: inputs-and-delete | `044fafc` (before §7.22) | "the staged restore went with Zed" and "nothing was installed where Zed was" (a `pip.db` and `salt.bin` appear in the deleted profile's folder), beside the five D-11/D-18 failures also seen at HEAD |

D-01 has no commit with D-03 fixed and D-01 not, so its evidence is the WAL
each restore swapped out (§4).

**Which restores used an export that had failed its own verification
(D-17).** The driver carries on with the file such an export leaves, and
records it. At `9968e8c`, one: the shortcut variant's export from the
original layout failed verification (D-17), and machine 5's restore used
its leftover and compared equal. At `5cc54df`, main-graceful's second
restore used a leftover; in the first, unpinned runs, main-killed's first
restore and main-graceful's second did. Each compared equal.

## 4. What now holds

- **D-01, on every in-app restore that had a WAL to swap** (10 of 13 at
  `9968e8c`; the inputs-and-delete control and two staging restores
  swapped out none, or an empty one). Each of those `pip.db-wal` files held
  committed frames, page 1 included (frame headers read, salts matching):
  271,952 bytes with 16 commits after the force-kill, 964,112 bytes with
  82 commits after the clean stop, which does not checkpoint either. The
  restored profile opened with the new password every time; the old and the
  backup's were refused; the replaced database was kept with its `-wal` and
  `-shm`.
- **D-03.** Exports from one-profile installations chose that profile. An
  export from a two-profile installation, signed into the second while the
  console inherited the first's `PIP_*` (the app launched on the first),
  exported the second, and the restore holds its data and none of the
  first's.
- **D-14, for the restore it covers.** A restore staged for a profile that
  is then deleted goes with it, and nothing is installed after the restart;
  the control survives another profile's deletion and is installed. An
  *orphaned* staged copy does not go with its profile (D-19).
- **Documents across machines.** With the original machine's paths absent
  and the target profile holding no documents of its own, every document is
  written back under the restored profile's documents
  folder (`profiles/<slug>/documents/`, or `data/documents/` in the
  shortcut's original layout), byte for byte, and its text is retrieved,
  after one hop and after two.
- **Continuing.** The restored profile answers a new chat turn, takes a new
  decision and document, and carries them through the next export and
  restore.
- **The original layout.** The shortcut restores into `data/pip.db`; using
  that, exporting it (`export_pip.ps1` resolves it as the profile
  "Default", whose files are `data/pip.db` and `data/salt.bin`; under
  Windows PowerShell 5.1 its original-layout branch does not run, §7.18)
  and restoring it in the app elsewhere compares equal.
- **Paths.** main-killed under an installation path with spaces,
  parentheses and non-ASCII characters (`run path (é ü)`) passes all 43
  checks: the launchers, staging, the marker, the swap and the write-back
  all handle it. (A first attempt stopped at the harness's own reading of
  PowerShell's output, §8.)
- **The shortcut onto an installation with a named profile** adds the
  restored data as "Default" beside it: the new password opens Default,
  Zed's own password still opens Zed (his data was not compared). The
  launcher still starts on Zed, the last opened, so the person has to
  choose Default at sign-in: the limitation §7.16 recorded.
- **The file.** No backup that was scanned contained a plaintext marker
  (document tokens, the profile's name, a decision, or the SQLite header):
  every backup carried between machines in the main, path, shortcut,
  inputs-and-delete, staging and restore-over-used variants. The
  multi-profile, same-machine and shortcut-shipped backups were not
  scanned.
- **Refusals.** A missing file, a text file, a truncated backup, the live
  encrypted database, the wrong backup password, and a short or missing new
  password are each refused with a 422 and a sentence, and nothing is
  staged.

## 5. New defects

Each was put to an independent reviewer told to refute it. Their
corrections are applied below. Two of their claims were then measured (D-19,
parts 5 and 6 of `staging`), and two of the completeness critic's code
readings became D-20 and D-21 once measured.

### D-18 — An empty file is accepted as a backup and replaces the profile
with an empty one (Medium; A)

- **What happens, in the app (measured).** Yara chooses a 0-byte
  `.pipbak`, types any backup password and a new password.
  `POST /backup/restore` answers 200 `{"pending": true, "rows": 0,
  "tables": 0}`, and the Backup screen would say "empty.pipbak - 0 rows
  across 0 tables, checked and ready. Close PIP and open it again to
  finish." (`backup_view.dart:531-534`). At the next backend start the
  empty database is installed in her place: her own password is refused
  (401), the one typed while staging opens it, and her profile is empty
  (name, language and the marker field gone). Her real database survives
  only as `pip.db.superseded-<stamp>` with its salt; getting it back means
  renaming both by hand with the backend stopped, which nothing in the app
  explains.
- **Cause.** `stage_restore` (`restore.py:96-207`) proves the password
  with a read of `sqlite_master`, runs `integrity_check`, and compares the
  restored copy against counts it took from the backup itself. SQLCipher
  opens a zero-length file as a new, empty database under any key, so every
  check passes with nothing in it. The same holds in `restore_backup.py`.
- **The gap is wider than empty files** (the reviewer's own probes, on a
  synthetic source with the same `ATTACH` + `sqlcipher_export` as
  `export_backup.py`; not re-run through the launcher). Because a backup is
  checked only against itself, an export killed part-way also passes with
  the right backup password: `sqlcipher_export` commits table by table, so
  what is left opens with `integrity_check` ok and some tables empty, and
  the real `stage_restore` staged one as `rows: 0, tables: 1`. A check that
  PIP's tables are present would not catch that; a mark written only by a
  completed, verified export would. Staging also opens the chosen file
  read-write, so a leftover journal beside it is rolled back into the
  person's own `.pipbak`.
- **Through the desktop shortcut.** With `--from --yes`, an empty file
  exited 0 saying "Restored ... Your documents were written back ... and
  re-indexed" and installed an empty `pip.db`. The shipped shortcut passes
  neither flag: a person is shown "(0 bytes)", "0 tables, 0 rows" and "0
  rows match", and must type `yes`. On the bare installation used here
  nothing was displaced.
- **When.** At the next *backend* start, which because of D-09 is a reboot
  or a crash, possibly days later, long after the banner (and its Cancel)
  was last seen.
- **Severity.** Medium. The harm is a profile that looks wiped and a
  password that stops working, recoverable only by hand; nothing is
  destroyed. The 0-byte trigger is unlikely (a truncated copy or sync, or a
  mistake), and the screen does show "0 rows across 0 tables" (and "0 B" in the
  Backups list, if the file sits in `data/`).
  What keeps it from low: it is met at the moment someone is already
  recovering from something, the screen calls the file "checked and ready",
  and the wider gap (a partial export) is more plausible than an empty
  file. Under the project's scale, High is a core workflow failing for
  everyone (D-03); this is not that.
- **Recommendation (not implemented):** refuse a backup that is not a
  completed PIP export, before staging or installing it, in both
  installers. At minimum, refuse no tables, no rows or missing core tables
  with a sentence. Properly, `export_backup.py` writes a completion mark
  (table counts and a version) as the last step of a verified export, and
  both restores require it. Open the chosen file read-only.

### D-20 — A restore over a profile with a same-named document reads that
file instead of the backup's (Medium, upper end; A/B)

- **What happens (measured at `9968e8c`).** Zed's profile holds
  `heliotrope.txt` (his note, `ZEDSAME-55`) and `zed-only.txt`
  (`ZEDONLY-77`). Zarqa's backup holds a different `heliotrope.txt`
  (`QUOKKA-7`). Restored over Zed's profile in the app, then a kill and
  restart, and signed in with the new password: the restored record of
  `heliotrope.txt` points at Zed's file in the profile's own `documents/`;
  retrieval does not find `QUOKKA-7` in 120 s, and does find `ZEDSAME-55`.
  `ZEDONLY-77` does not answer. Every API view still compares equal, and
  the Documents screen lists `heliotrope.txt` as before: nothing shows it.
- **And the backup's copy is overwritten** (the reviewer, on a copy of the
  restored database; then confirmed in the code). The first sign-in's
  rebuild re-ingests the file the record was pointed at, and
  `ingest_document` ends by storing that file as the document's blob with
  an upsert (`vector_store.py:446`). The restored database then holds Zed's
  73 bytes under Zarqa's record. The backup's text survives only in the
  `.pipbak`, and a later export would carry Zed's bytes.
- **Cause.** `restore._install` swaps `pip.db`, its sidecars and
  `salt.bin`, not the profile's `documents/` or `chroma/`. At the first
  sign-in, `materialise_documents` (`profile_store.py:509`) finds the
  recorded path missing and a same-named file in the folder, and repoints
  rather than writes: "the copy on disk is the user's, and may be newer than
  the backup's". True on the machine that wrote the backup; here the file
  belongs to the profile being replaced and shares only its name. The
  restore dialog promises the opposite: "Everything in this profile will be
  replaced by what is in the backup: ... and your documents"
  (`backup_view.dart:687-690`).
- **Same root as D-07** (the reviewer's analysis): D-07 is the recorded
  path existing outside the profile (nothing indexed); D-20 is a same-named
  file inside it (the wrong file indexed, and its bytes stored). By the
  code, not run: when the recorded absolute path itself exists inside the
  profile (the same Windows user, the default install folder and the same
  profile name, as when one person migrates), the earlier branch keeps it,
  with the same result.
- **Who reaches it.** An in-app restore over a profile that already holds a
  document of the same name with different bytes, for example a common
  name (`notes.txt`, `resume.pdf`) used on the new machine before
  restoring. A restore into a fresh profile, the shortcut onto a bare
  installation and a rollback on the same machine are unaffected (uploads
  never overwrite a name, `server.py:772-777`).
- **Severity.** Medium, at the upper end: silent wrong content, and the
  backup's copy of the document destroyed in the restored database, against
  an explicit promise. Not High: it needs the name collision.
- **Recommendation (not implemented):** have `_install` move the profile's
  `documents/` and `chroma/` aside with the database, under the same stamp
  and in the same undo list, so the write-back starts from an empty folder
  and writes the backup's bytes. One fix at the restore boundary may close
  D-07 too.

### D-21 — The desktop shortcut restores the first backup of the day, saying
it uses the newest (Medium, low end; A)

- **What happens (measured twice at `9968e8c`).** Two exports on one day
  leave `pip_backup_20261003.pipbak` and, seconds later,
  `pip_backup_20261003-2.pipbak`, with a change made between them. Run as
  installed (no arguments, a typed `yes`), `restore_pip.ps1` lists them
  newest first, `-2` at the top, and says "the newest will be used";
  `restore_backup.py` then prints "Restoring from pip_backup_20261003.pipbak"
  and restores it. The restored profile lacks the change.
- **Cause.** `newest_backup()` (`restore_backup.py:141-145`) takes the last
  name in `sorted()`, and `-` sorts before `.`. The same rule picks any name
  sorting after `pip_backup_` over the dated files whatever their age, and
  `-9` over `-10`. CLI `/restore` with no file shares the default
  (`frontend/cli/pip_cli.py:130`).
- **Not silent, but contradictory.** The name actually used is printed,
  after a listing and a sentence that say otherwise, and both files are the
  same size.
- **Who reaches it.** The shortcut with no `--from` when `data/` holds two
  or more backups and the newest day has more than one: typically the
  machine that wrote them, for example after a lost live password, when the
  in-app restore (which needs sign-in) is not available. A fresh machine
  with an empty `data/` is asked for a path instead, and the in-app restore
  takes an explicit file. (The installer puts this shortcut in the Start
  menu; `install_shortcuts.ps1` puts it on the Desktop.)
- **What is lost** is limited to changes between same-day exports, and is
  recoverable: the newer `.pipbak` stays, the replaced database is kept as
  `.superseded-<stamp>`, and `--from` restores the right one. After a D-17
  retry it loses almost nothing, since that leftover holds the newer rows.
- **Severity.** Medium, low end: a restore of older data reported as
  success, contrary to what the console says. Low (upper) is defensible
  given the printed name and full recoverability.
- **Recommendation (not implemented):** one rule for the listing and the
  pick: the newest by modification time (ties broken by the date and a
  numeric suffix), as the listing and the Backup screen already order them.

### D-17 — An export taken while the app is committing rows fails, and says
nothing was written (Low, upper end; A)

- **What happens.** `export_backup.py` counts each table's rows
  (`main()`, the "N tables, M rows" line), asks for the backup password
  twice, checkpoints, and only then exports. `verify()` requires the
  backup's counts to equal the first count exactly. The Backup screen
  launches the export while the backend runs, and nothing pauses it, so a
  commit in that window that changes a compared table's row count (an
  insert or a delete; updates and the FTS shadow tables do not count) fails
  the export with `ERROR: row counts differ`.
- **What the person is told.** `export_pip.ps1:98-99` prints "The export
  did not complete. Nothing was written." for every non-zero exit. Here
  that is false: the `.pipbak` was written, passed `integrity_check`, holds
  the newer rows, and restored correctly. The Backup screen lists every
  `.pipbak` in `data/`, newest first and unmarked (`backup_view.dart:109-137`),
  so the file it was told does not exist appears at the top of the list,
  and the shortcut's own pick prefers it over a same-day retry (D-21).
- **Broader than the race.** The same message follows any failure after
  the file is written: an `integrity_check` failure, or an error during
  `sqlcipher_export`. There the leftover is not usable, and it is listed
  like any other backup (reasoned from the code, not run).
- **"Complete" is observed, not guaranteed.** In every run seen the source
  had grown, so the backup held more. `verify()` cannot tell that from an
  export that lost rows.
- **Evidence.** `probe_export_while_running.py`, run at `5cc54df` (twice)
  and `9968e8c`: the control verifies; with one decision created through
  the API during the backup-password prompt the export exits 1 with
  `{'decision_candidates_pending': (0, 1)}` and leaves a valid file; a
  retry the same day succeeds and writes `pip_backup_YYYYMMDD-2.pipbak`. On
  its own it happened in 2 of 5 exports taken right after chat in the first
  runs, 1 of 5 at `5cc54df` and 0 of 7 at `9968e8c`; and once at `9968e8c`
  with no chat on that machine at all (below). **That is not a rate for the
  app.** Each
  such failure was an export started seconds after the harness closed the
  chat socket, which starts the Observer's session-end pass
  (`server.py:1663-1680`); the tables that differed are exactly what that
  pass commits (`session_lifecycle.py:204-208`, and a profile's first
  `session_snapshot`). **The once with no chat** is the route a person
  takes: the export from an installation just restored by the shortcut,
  failing with `{'session_snapshot': (0, 1)}`. A copy of that database
  holds one `session_snapshot` row, about the conversation that came with
  the backup, stamped one second before the `.pipbak` was written: the
  sign-in catch-up was observing the restored conversation.
- **How a person reaches it.** Switching to the Backup tab does not close
  the chat socket (`home_shell.dart` keeps every tab alive), so "chat, then
  Export now" alone does not trigger it. It does when the export starts
  while a writer is committing: within a couple of minutes of New chat,
  opening another conversation or signing out (the Observer pass, about
  130 s with a local 7B model); straight after signing in, while the
  catch-up drains queued sessions (measured above, after a restore);
  about ten minutes after the last
  message, when the idle Observer fires; or using the app while the console
  waits. Occasional, and a retry works.
- **Severity.** Low, at the upper end: it fails closed and loudly and loses
  nothing. What keeps it from trivial is that this is the only backup path,
  and a false "Nothing was written" beside an unmarked file in the Backups
  list undermines trust in it. Medium is defensible if the owner weighs that
  above the absence of data loss.
- **Recommendation (not implemented):** take the counts and the export
  from one read snapshot (a read transaction held across both; reasoned,
  not tested), and make the failure message true: remove a file that failed
  verification, or say where it is and that it was not verified.

### D-19 — Staged-restore state is one per installation but treated as the
signed-in profile's (Low; A)

- **Mechanism.** One `pending-restore.json` serves the whole installation
  (`restore.py:80-81`, under `profiles.data_dir()`), but the three routes
  act on it as the signed-in profile's: `GET /backup/restore` reports it to
  whoever is signed in, `DELETE` cancels it for whoever is signed in, and
  `stage_restore()` replaces it without reading it, leaving the earlier
  staging's files behind (`restore.py:154-158`, `197-201`). Nothing else
  looks for `restore-*.tmp.*` files: drain, cancel and
  `cancel_pending_restore_for` touch only what the current marker names.
- **Reachable through the app (backend half measured; the screen half from
  the code):**
  - Zed stages a restore and signs out. Yara signs in: the status route
    gives her `{"pending": true, "source": "export-1.pipbak", ...}`, which
    her Backup screen shows as "Ready to restore on the next start" for
    this profile (`backup_view.dart:514-555`), with Zed's file name. Her
    "Cancel the restore" answers `{"cancelled": true}` and erases Zed's
    staged restore. Zed is not told; his banner is simply gone next time.
  - If she restarts instead, Zed's restore is installed into Zed's profile,
    which is correct.
- **Reachable only through the API or a stale second window.** While a
  restore is pending the Backup screen hides "Choose a .pipbak"
  (`backup_view.dart:514-555`; held by `backup_view_test.dart:179`, `:208`),
  so one window cannot stage twice. Over the API (or from a second app
  window that has not refreshed):
  - **staging twice for one profile** leaves both staged copies, and the
    app's cancel removes only the second;
  - **staging for Yara while Zed's waits** is accepted with no warning. At
    the next start Zed's is never installed (his old password still opens
    his profile; the one he chose is refused), and his staged copy stays in
    his folder.
- **The orphan outlives its profile.** Staged twice for Wren and cancelled,
  then Wren deleted: the delete answers 200 `"deleted": "wren"`, but
  `profiles/wren/` remains holding `restore-<stamp>.tmp.db` and its salt,
  before and after the next start. `profiles.delete()` cancels only the
  marker's staging (§7.22), and its erasable paths do not cover staged
  files, so the folder cannot be removed. That file is a full copy of the
  backup's data, encrypted under a password Wren chose while staging: the
  residue §7.22 set out to prevent, reached by another route.
- **Severity.** Low. No live data is damaged; each profile's database and
  password are untouched, and the `.pipbak` still exists, so a lost restore
  can be staged again. What it costs is a request silently dropped, and a
  full encrypted copy of personal data left behind after "delete my
  account".
- **Recommendation (not implemented):** compare the marker's `target_db`
  with the signed-in profile in all three routes, refusing or explaining
  another profile's staged restore; have staging cancel its own profile's
  earlier staging; have `profiles.delete()` erase `restore-*.tmp.*` in the
  profile's folder.

### D-11, two more instances (Low)

- A folder given as the backup → 500 "unable to open database file".
- An empty backup password → 500 "PRAGMA key requires a key of one or more
  characters".
- A bit-flipped backup → 500 "SQL logic error", as before.

Nothing was staged in any of the three. The first two are reachable only
through the API: the file picker cannot return a folder, and the restore
dialog refuses an empty backup password (`backup_view.dart:427-431`,
`661-663`). Each should be a 422 with a sentence, as the other bad inputs
already are.

## 6. Still open, reproduced

- **D-07.** Restored into a second profile on the same machine, the
  document's record still points into the first profile's `documents/`
  folder, which exists, so it is not written back, and retrieval finds
  nothing. Everything else on that path compares equal.
- **D-09.** Not run (the harness restarts the backend itself), but it now
  decides the exit criterion (§9), and it widens D-18's and D-19's windows.
- **D-11.** A bit-flipped backup is still answered with a 500.

## 7. Not covered

From the completeness critic's list, after the cheap gaps it named were
closed (multi-profile export with the inherited environment, a restore over
a profile with its own documents, the shipped shortcut, the original
layout, paths, negative controls, a run at HEAD):

- **The UI.** The Backup screen's Export button (its `cmd /c start` and the
  quoting of a path with spaces and parentheses), the file picker, the
  restore dialog, the staged banner, the Backups list and sign-in after a
  restore were not driven. The screen's behaviour quoted above is from the
  code.
- **The app's own restart (D-09).** `launch_pip.ps1` never ran, so neither
  did its reuse of a running backend, its stale-lock cleanup, or its start
  of Ollama.
- **A real second machine or user.** One PC and one Windows user stood in
  for every machine, sharing one Ollama with the model already pulled, the
  model caches, and the development environment's packages (not the
  installer's embedded Python). Not tested: the real embedding model
  (D-02), a machine without Ollama or without the profile's model, an
  offline re-index, another user's install path and permissions, another
  SQLCipher or chromadb build.
- **Version skew.** Every machine in a run used one commit; a backup from
  an older build restored into a newer one was not tried.
- **Scale and durability.** Backups of 0.2 MB, at most 66 rows, one or two
  small text documents. No profile of hundreds of MB (staging is a full
  copy and two key derivations inside one request), no power loss between
  staging and restart.
- **Content beyond the compared views.** Conversations with their messages,
  decisions with reasoning, projects with descriptions, the active model,
  profile fields and document names are compared; every other table only
  by the product's own row counts. Snapshots were taken once documents were
  back, which may be before the Observer catch-up finished; whether the
  Observer's queue completes exactly once across a restore was not checked.
- **Documents and passwords.** Only small ASCII `.txt` documents and ASCII
  passwords without quotes. Not tested, and by the code accepted: an in-app
  new password equal to the backup password (`stage_restore` does not
  compare them; `restore_backup.py:222` refuses it).

## 8. Harness and provenance

- **Concurrent edits.** Another session worked in the same checkout during
  these runs, on D-16 (FREEZE_LIST §7.23, committed as `9968e8c`). Its
  change to `backend/core/pipeline.py` landed while the first runs were
  copying `backend/`: comparing each installation's copy afterwards,
  main-killed, main-graceful, shortcut, same-machine, the first
  inputs-and-delete run and the first probe had `5cc54df`'s file exactly;
  the inputs-and-delete re-run (after the cancel-between-cases correction)
  had a mid-edit state, and the first staging run the finished,
  then-uncommitted fix (identical to `9968e8c`'s). The change is
  confined to the "no consented provider" branch, which no variant reaches.
  The harness now builds from a pinned commit, the runs were repeated that
  way at `5cc54df` (same verdicts, check for check, where comparable), and
  every number in §3 comes from pinned runs.
- **Interrupted batch.** The session running the final batch at `9968e8c`
  ended part-way through; the two variants that had finished were kept,
  and the rest were run again from the start.
- **Harness corrections found by the HEAD batch, each re-run:**
  - staged files are named by the second, so two stagings inside one
    second share names and no orphan forms; the staging variant now waits
    over a second between stagings (a person always does);
  - under Windows PowerShell 5.1 a lone legacy profile is named "Default"
    by `export_pip.ps1` (§7.18's observation), not left unnamed; the
    check expects that;
  - a redirected PowerShell writes in the OEM code page, which the harness
    read as cp1252, so a path containing `ü` came back as nothing; the
    profile lookup now asks PowerShell for UTF-8, and the launchers'
    output is decoded tolerantly.
- **Test-design errors, corrected before the numbers above:**
  - the first bad-input run did not cancel between cases, so the empty
    file's staged restore made every later case look like it had staged
    something; and two of its D-14 checks read `GET /backup/restore` after
    a sign-out, when the route is locked. Each case now stands alone, and
    D-14 is read from disk;
  - one staging check was labelled "or both are kept" for a condition that
    tests "or none is left orphaned"; relabelled;
  - a marker read assumed the field exists; it now accepts the route's
    `null`.
- **What differs from a real installation:**
  - the restart (above, and D-09);
  - the export ran `export_pip.ps1` directly with a clean environment,
    except in the multi-profile variant;
  - `getpass` answered by the hook: no real console input, and the probe's
    "write during the prompt" is an API call, not the app's own timing;
  - the embedding stand-in, and one PC, user, volume and Python for every
    "machine" (the other machine is made by renaming the first one's
    folder);
  - the harness closes the chat socket seconds before exporting, which is
    what produced every spontaneous D-17 failure but one (the export just
    after a shortcut restore, which the sign-in catch-up produced, §5); the
    Flutter shell keeps the socket open across tab switches;
  - the driver carries on after a failed export with the file it left
    (recorded per restore, §3).

## 9. Exit criterion

**Not met as worded.** The criterion is "supported migration verified":
export from the Backup screen, restore in the app on another installation,
restart, verify, keep using, export again, restore again.

**What is verified** at `9968e8c`, with the embedding stand-in: the data
round trip through the real export script and the real restore code, in
real backend processes, over two hops, after a clean and a forced restart;
from a one- and a two-profile installation; through the shortcut onto a
bare installation and onward from the layout it creates; under a path with
spaces, parentheses and non-ASCII characters. D-01's condition was present
on 10 of the 13 in-app restores and was
handled each time, and the harness catches D-03 and
D-14 on the commits before their fixes.

**What keeps it from met:**
1. **D-09 (open, Medium):** the restart the app asks for does not apply the
   restore; it waits for the backend's next start. If "restart" means
   "close PIP and open it again", the criterion cannot be met until D-09 is
   fixed.
2. **D-18 (Medium):** an empty or part-written file is accepted and
   replaces the profile.
3. **D-20 (Medium, upper end):** a restore over a profile with a same-named
   document
   silently takes the wrong document and discards the backup's copy.
4. **D-21 (Medium, low end)** on the shortcut, and **D-17 (Low, upper)** on
   the export, which a person meets after restoring and signing in.
5. **D-07** reproduces; **D-02** stops the real backend on this machine
   (environment).
6. The UI legs (the Export button, the picker, the banner, sign-in) and a
   real second machine were not exercised.

Recommended reading: **met with exceptions for the data round trip at
`9968e8c`; not met for the workflow as a person performs it** until D-09,
D-18 and D-20 are decided.

## 10. Reproduce

From the repository root, with Ollama running `qwen2.5:7b`:

```
$H = "docs\eval\reliability_2026-10-01\migration"
.venv\Scripts\python.exe $H\journey_migration.py <variant> <empty dir> [commit]
.venv\Scripts\python.exe $H\probe_export_while_running.py <empty dir> [commit]
```

Each run writes `results.json` (every check, its verdict and detail, and
the commit) into its directory.
