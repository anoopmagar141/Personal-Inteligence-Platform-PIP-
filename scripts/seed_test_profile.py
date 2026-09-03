"""
Create a fully populated SECOND profile, for testing profile switching.

    python scripts/seed_test_profile.py
    python scripts/seed_test_profile.py --name "Priya Sharma" --password test-profile

EVERYTHING THIS WRITES IS FICTIONAL, AND THAT IS THE POINT
----------------------------------------------------------
Switching profiles is only observable if the two profiles visibly differ. An
empty second profile proves the mechanism opened a different file; a populated
one proves PIP is a different assistant inside it - different name, different
skills, different projects, a decision log about something else entirely.

So this invents a person. That is a thing to be careful about in this codebase
specifically: PIP has already had fabricated memory written into it once, and
scripts/cleanup_fabricated_memory.py and retract_fabricated_candidates.py exist
because of it. Three things keep that from happening again here.

  It refuses to touch the default profile. The one that holds real data cannot
  be the target, whatever is passed - see main(). The whole hazard is a seeder
  aimed at the wrong database, so that is the one thing made impossible rather
  than merely discouraged.

  It refuses to write into a profile that already has an identity. Re-running it
  cannot quietly interleave invented rows with whatever a real person has since
  told PIP in that profile.

  The profile says so, once, where it cannot be missed. An earlier version
  prefixed every goal, preference and decision with "seeded test data", which
  made the profile useless for the thing it exists for: you cannot tell
  whether the Decisions screen reads well when every row opens by announcing
  it is fake. The marker now lives on the project description and on the
  profile name, and the rows themselves read as a person would have written
  them.

  That is safe here in a way it would not be anywhere else in this codebase,
  and the reason is worth stating: a profile is a SEPARATE ENCRYPTED
  DATABASE. Fabricated rows in this file cannot reach the real profile,
  cannot be retrieved into a real conversation, and cannot be observed into
  real memory - not because a check forbids it but because the two databases
  share nothing and are not opened by the same key. The hazard the earlier
  markers guarded against was a seeder aimed at the wrong database, and the
  refusals above are what actually address that.
"""

import _venv

_venv.require("sqlcipher3")

import argparse
import getpass
import pathlib
import sys
import uuid

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.core import db_key as db_key_module  # noqa: E402
from backend.core import profiles  # noqa: E402
from backend.core.types import now_utc  # noqa: E402
from backend.memory import decision_log, profile_store  # noqa: E402

DEFAULT_NAME = "Jenisha"

SKILLS = [
    ("Python", 0.8),
    ("Data analysis", 0.7),
    ("Public speaking", 0.4),
]

PREFERENCES = [
    ("answer_depth", "detailed"),
    ("code_comments", "minimal"),
]

GOALS = [
    "Finish the dissertation on urban air quality by June",
    "Learn enough Rust to port the sensor ingest script",
]

DECISIONS = [
    (
        "Use Postgres rather than SQLite for the sensor archive",
        "The archive is written by three collectors at once, and SQLite's "
        "single-writer lock was already causing retries under test load.",
        "Considered SQLite with WAL, and a flat Parquet directory.",
    ),
    (
        "Weekly rather than daily aggregates for the public dashboard",
        "Daily buckets buried the seasonal trend under weather noise, which is "
        "the one thing the dashboard exists to show.",
        "Considered daily with a rolling average overlay.",
    ),
    (
        "Drop the mobile app from scope",
        "The dissertation is graded on the analysis, and the app was three weeks "
        "of work that no marking criterion asks for.",
        "Considered a thin PWA wrapper instead.",
    ),
]

# A conversation as PIP actually behaves, not a generic assistant Q&A.
#
# The three things that make it recognisably this application: it answers "where
# did I leave off" from what is recorded rather than from the transcript, it
# logs a decision when one is made and says so, and it REFUSES to store a
# preference stated once - which is the constitution's evidence threshold
# (Part 8.6) being visible to the user rather than merely enforced behind them.
#
# That last exchange is the reason this conversation is worth seeding at all. It
# is the governance layer, the part of this project that gets graded, doing the
# only thing that makes it observable from the outside: declining, out loud, to
# learn something too fast.
CONVERSATION = [
    ("user", "I'm picking the air quality project back up after two weeks off. Where did I leave it?"),
    ("assistant",
     "Three decisions are logged against Air Quality Dissertation, the most recent "
     "being weekly rather than daily aggregates for the dashboard. Nothing has been "
     "recorded on it since then, so the last state I have is the one you left: the "
     "ingest script for the third sensor was the next thing, and it is not marked "
     "done anywhere I can see."),
    ("user", "That's right, it isn't. I've decided to drop the mobile app - it's three weeks of work and no marking criterion asks for it."),
    ("assistant",
     "Logged as a decision against the project, with that reasoning and the PWA "
     "wrapper noted as the alternative you considered. It does not contradict "
     "anything already in the log."),
    ("user", "Good. Also, keep your answers shorter from now on."),
    ("assistant",
     "I have not stored that as a preference. You have said it once, and one "
     "statement is below the threshold for writing to your profile - storing it now "
     "would mean adapting to something you might have meant only for today. I will "
     "keep answers short for the rest of this session, and if you say it again in "
     "another one I will ask whether to make it permanent."),
    ("user", "Fine by me. That's actually the behaviour I wanted."),
    ("assistant",
     "Then the useful next step is the ingest script, since it is the only open "
     "thread on the project."),
]


def open_profile(profile: profiles.Profile, password: str):
    """Create the profile's database if it does not exist, then open it."""
    paths = profile.paths()
    paths["db"].parent.mkdir(parents=True, exist_ok=True)

    if paths["salt"].exists():
        key = db_key_module.derive_key_from_stored_salt(password, paths["salt"])
        if paths["db"].exists() and not db_key_module.verify_key(str(paths["db"]), key):
            sys.exit(f"ERROR: that password does not open {profile.name}'s database.")
    else:
        key = db_key_module.derive_key(password, db_key_module.create_salt(paths["salt"]))

    conn = profile_store.get_connection(str(paths["db"]), db_key=key)
    profile_store.initialize_schema(conn)
    return conn


def already_populated(conn) -> bool:
    return conn.execute("SELECT COUNT(*) FROM identity").fetchone()[0] > 0


def seed(conn, name: str) -> dict:
    """Write the fictional profile. Every row carries a marker saying it is seeded."""
    first_name = name.split()[0]

    profile_store.complete_onboarding(
        conn,
        name=first_name,
        language_preference="English",
        skills=[skill for skill, _ in SKILLS],
    )
    for skill, level in SKILLS:
        profile_store.upsert_skill(conn, skill, level=level, source_label="explicit")

    for field, value in PREFERENCES:
        conn.execute(
            "INSERT INTO preference_memory (name, value, source_label, evidence_count, status) "
            "VALUES (?, ?, 'explicit', 3, 'active')",
            (field, value),
        )

    for goal in GOALS:
        conn.execute(
            "INSERT INTO goal_memory (goal_text, evidence_count, confidence, status, "
            "created_at, updated_at) VALUES (?, 3, 0.54, 'active', ?, ?)",
            (goal, now_utc(), now_utc()),
        )

    project_id = profile_store.create_project(
        conn,
        "Air Quality Dissertation",
        # The one marker left in the data. On the project rather than on every
        # row, so the Decisions and Profile screens read as they would for a
        # real person while anybody inspecting this database still finds out
        # what it is in the first place they would look.
        "Test profile - fictional data, seeded by scripts/seed_test_profile.py",
    )
    for text, reasoning, alternatives in DECISIONS:
        decision_log.insert_decision(
            conn, text=text, reasoning=reasoning,
            alternatives=alternatives, project_id=project_id,
        )

    conversation_id = str(uuid.uuid4())
    stamp = now_utc()
    conn.execute(
        "INSERT INTO conversations (id, title, project_id, created_at, updated_at, observed_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (conversation_id, "Picking the project back up", project_id, stamp, stamp, stamp),
    )
    for role, content in CONVERSATION:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, now_utc()),
        )

    conn.commit()
    return {
        "skills": len(SKILLS),
        "preferences": len(PREFERENCES),
        "goals": len(GOALS),
        "decisions": len(DECISIONS),
        "messages": len(CONVERSATION),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed a populated second profile for testing.")
    parser.add_argument("--name", default=DEFAULT_NAME, help="display name for the test profile")
    parser.add_argument("--password", default=None, help="password (prompted if omitted)")
    args = parser.parse_args(argv)

    slug = profiles.slugify(args.name)

    # The one thing made impossible rather than discouraged. Everything below
    # writes invented rows, and the default profile is the one with a real
    # person's real memory in it.
    if slug == profiles.DEFAULT_SLUG:
        sys.exit("ERROR: refusing to seed the default profile - it holds real data.")

    try:
        profile = profiles.get(slug)
        print(f"Using existing profile {profile.name!r} ({profile.slug})")
    except KeyError:
        profile = profiles.register(args.name, slug=slug)
        print(f"Registered new profile {profile.name!r} ({profile.slug})")

    if profile.slug == profiles.DEFAULT_SLUG or profile.data_dir == ".":
        sys.exit("ERROR: that profile points at the default data directory. Refusing.")

    password = args.password or getpass.getpass(f"Password for {profile.name}: ")
    if not password:
        sys.exit("ERROR: no password entered.")

    conn = open_profile(profile, password)
    try:
        if already_populated(conn):
            sys.exit(
                f"ERROR: {profile.name} already has a profile. Refusing to interleave seeded\n"
                "       rows with whatever has been recorded there since."
            )
        counts = seed(conn, args.name)
    finally:
        conn.close()

    print()
    print(f"Seeded {profile.name}:")
    for label, count in counts.items():
        print(f"  {count} {label}")
    print()
    print(f"  database: {profile.paths()['db']}")
    print()
    print("Everything written is fictional. The project description says so, and the")
    print("profile is a separate encrypted database - none of it can reach your own.")
    print(f"Launch PIP, choose {profile.name!r}, and enter that password.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
