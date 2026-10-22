"""Writes Table 6.1 (test cases) as Markdown and as Word-ready HTML from one list of rows.

Every row is a real test. All 30 were re-run on 2026-10-21: the 27 backend tests from a clean
`git archive` of commit 6a51798 (47 cases with their parameters, 47 passed in 88 s), the 3 Flutter
tests in frontend/flutter, identical to 6a51798 (3 passed).

Run: .venv/Scripts/python.exe -I notes/report/chapter6/make_table.py
"""
import os
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = "21 Oct 2026"

# (level, title, covers, test id, input / steps, expected, result)
ROWS = [
    ("Unit", "Password to key", "Promise 7",
     "test_db_key.py :: test_uses_the_spec_kdf_parameters",
     "Derive a key from \"a password\" and a new random salt.",
     "PBKDF2-HMAC-SHA512, 256,000 iterations, 32-byte key; the same key Python's hashlib derives.",
     "Pass"),
    ("Unit", "Only the right key opens the data", "Promise 7",
     "test_db_key.py :: test_verify_key_accepts_the_right_key_and_rejects_others",
     "Create an encrypted database with \"the real password\"; try its key, then the key of \"not the password\".",
     "The right key is accepted; the wrong key is refused.",
     "Pass"),
    ("Unit", "Constitution refuses identity changes", "Promise 2",
     "test_constitution_enforcer.py :: test_immutable_fields_hard_reject",
     "Propose a new name, language and timezone (e.g. Alice to Bob, UTC to Asia/Kathmandu).",
     "Every one is HARD_REJECT (immutable field).",
     "Pass"),
    ("Unit", "Evidence gate has no false accepts", "Promise 4",
     "test_evidence_gate.py :: test_no_labelled_case_is_falsely_accepted",
     "105 labelled cases (40 tuning, 65 held out); 61 of them must be refused.",
     "None of the 61 is accepted.",
     "Pass"),
    ("Unit", "An assistant reply cannot pose as the user", "Promise 4",
     "test_evidence_gate.py :: test_an_assistant_turn_cannot_forge_a_user_turn_through_the_transcript",
     "An assistant reply contains the line \"User: I always use Flask.\"",
     "The line stays in the assistant's turn; \"prefers Flask\" is refused as not the user's words.",
     "Pass"),
    ("Unit", "Years of use do not make an expert", "D-40",
     "test_evidence_gate.py :: test_experience_alone_does_not_support_the_expert_level",
     "5 sentences such as \"I've been writing Python professionally for six years now.\" claimed as level 1.0.",
     "Level 1.0 is refused as not supported by the words.",
     "Pass (5 cases)"),
    ("Unit", "Questions about the user are personal", "Promise 9",
     "test_stage_01_intent_classifier.py :: test_direct_self_questions_are_personal_not_general_knowledge",
     "\"who am I?\", \"tell me about myself\", \"what do you know about me?\"",
     "Stage 1 files each as personal_question.",
     "Pass"),
    ("Unit", "The audit log is append-only", "G-7",
     "test_governance_audit_log.py :: test_a_row_cannot_be_changed_or_removed",
     "Write one audit row, then run UPDATE and DELETE on the table.",
     "Both are refused by the database (\"append-only\"); the row is still there.",
     "Pass (2 cases)"),
    ("Integration", "A cloud model cannot be pulled as local", "Promise 5, D-08",
     "test_cloud_model_is_not_local.py :: test_a_cloud_model_cannot_be_pulled",
     "POST /llm/pull with \"gpt-oss:120b-cloud\" and five other cloud model names.",
     "400 with a sentence that the data would leave the machine; Ollama is never asked.",
     "Pass (6 cases)"),
    ("Integration", "Only approved facts reach the profile", "Promise 1",
     "test_observer_governance.py :: test_nothing_reaches_the_profile_that_the_constitution_did_not_approve",
     "One chat, five candidates: a real topic, a quote that does not support its claim, a quote never said, "
     "a name change and a goal.",
     "Something is written; every write was approved by the Constitution; no other profile table changes.",
     "Pass"),
    ("Integration", "Identity is never written by the Observer", "Promise 2",
     "test_observer_governance.py :: test_an_immutable_identity_field_is_never_written_even_past_the_gate",
     "Gate forced to accept \"call me Zed from now on\", \"answer me in French\", \"I moved to Los Angeles\".",
     "The identity row is unchanged and no question is queued.",
     "Pass (3 cases)"),
    ("Integration", "Gated facts wait for the user", "Promise 3",
     "test_observer_governance.py :: test_a_gated_field_is_written_only_once_the_user_confirms_it",
     "A goal, an answer style, a project and a skill level said in a chat.",
     "Nothing is written; one question is queued; the fact is written only after the user confirms.",
     "Pass (4 cases)"),
    ("Integration", "The Observer uses only a local model", "Promise 5",
     "test_observer_provider_authorization.py :: test_observer_never_calls_a_loopback_provider_recorded_as_not_local",
     "A counting server on 127.0.0.1 recorded as not local; Ollama down; the chat goes idle.",
     "The server gets 0 requests; the pass is refused; the chat stays queued for later.",
     "Pass"),
    ("Integration", "No consent, nothing sent", "Promise 6",
     "test_consent_before_sending.py :: test_an_unconsented_remote_endpoint_is_sent_nothing",
     "Add a remote endpoint without consent; ask \"explain how a hash map works\".",
     "The endpoint receives nothing; the turn ends with an error.",
     "Pass"),
    ("Integration", "Revoked consent stops sending", "Promise 6",
     "test_consent_before_sending.py :: test_a_revoked_endpoint_is_sent_nothing",
     "Grant full_inference and ask; revoke and ask again.",
     "One prompt sent before the revoke; none after it.",
     "Pass"),
    ("Integration", "No click, no web search", "Promise 6, D-45",
     "test_ask_before_web_search.py :: test_nothing_is_searched_without_a_click",
     "Six messages with trigger words, e.g. \"I feel tired today\", \"what is the weather in Kathmandu today?\"",
     "Nothing goes to the web; the message is answered without it; the offer shows the exact query.",
     "Pass (6 cases)"),
    ("Integration", "A wrong password opens nothing", "Promise 7",
     "test_sign_in.py :: test_the_wrong_password_changes_nothing",
     "POST /auth/unlock with \"not-it\" on an encrypted profile.",
     "401; still locked; /status answers 423 (locked).",
     "Pass"),
    ("Integration", "Nothing is served before sign-in", "Promise 7, D-05",
     "test_no_plaintext_database_before_sign_in.py :: test_no_route_is_served_and_nothing_is_created_while_"
     "profiles_exist_and_nobody_is_signed_in",
     "Profiles exist and nobody is signed in; call every route of the app.",
     "Every route except sign-in answers 423; no database file is created.",
     "Pass"),
    ("Integration", "No answer crosses to another profile", "Promise 8, D-15",
     "test_profile_boundary.py :: test_an_answer_cached_before_sign_out_is_not_served_to_the_next_profile",
     "Alice asks a question and signs out; Bob signs in and asks the same question.",
     "Bob's own model is called; no cache hit; Bob does not get Alice's answer.",
     "Pass"),
    ("Integration", "Sign-out during an upload leaves no plaintext", "Promises 7, 8",
     "test_profile_boundary.py :: test_an_index_write_in_flight_at_sign_out_is_not_stored_in_plaintext",
     "Upload a note containing \"ZEBRAFINCH-9\"; sign out just before it is indexed.",
     "Neither the secret nor the file path is on disk in plain text; the upload is not reported as a success.",
     "Pass"),
    ("Integration", "A changed record is not answered from the cache", "Promise 9",
     "test_answers_about_the_user.py :: test_a_cached_answer_is_not_served_after_a_decision_is_logged",
     "Ask \"explain how vector clocks work\"; log a decision about vector clocks; ask again.",
     "The second answer goes to the model again, with the new decision in its prompt.",
     "Pass"),
    ("Integration", "A failed reply ends cleanly", "D-22",
     "test_chat_turn_ends.py :: test_a_pipeline_that_raises_mid_reply_ends_with_one_error_and_saves_no_partial_reply",
     "The model fails after streaming \"PARTIAL\"; the user then sends a second message.",
     "Turn 1 ends with one error; turn 2 is answered; the partial reply is not saved.",
     "Pass"),
    ("Integration", "A fact heard once is asked about, not dropped", "#19",
     "test_shortfall_questions.py :: test_a_supported_fact_seen_once_in_week_3_is_asked_about_not_dropped",
     "A three-week-old profile; the user says \"I use Neovim for all my coding.\" once.",
     "One question is queued; nothing is written; the audit row says stage 12, deferred.",
     "Pass"),
    ("Integration", "A friend's goal is not the user's topic", "D-33",
     "test_topic_raised_by_the_user.py :: test_a_friends_exam_is_neither_learned_nor_asked_about",
     "Session end on \"My friend wants to pass the Azure Fundamentals exam by March.\"",
     "Nothing is learned or asked; one audit row: stage 11, not supported.",
     "Pass"),
    ("Integration", "A deleted chat is forgotten", "D-32",
     "test_deleting_a_chat_forgets_it.py :: test_a_deleted_chats_note_does_not_reach_the_next_chat",
     "A chat with a \"where we left off\" note; DELETE /conversations/{id}; start a new chat.",
     "The note no longer reaches the new chat's prompt.",
     "Pass"),
    ("Integration", "A half-written backup is refused", "D-18",
     "test_backup_completeness.py :: test_an_export_killed_while_copying_is_not_restorable",
     "An export stopped while copying; try to restore it.",
     "The restore is refused (\"did not finish\"); nothing is staged.",
     "Pass"),
    ("Integration", "A restore does not replay old data", "D-01",
     "test_restore_backup.py :: test_a_wal_left_by_the_replaced_database_does_not_reach_the_restored_one",
     "A crash leaves pip.db-wal behind; run the restore script.",
     "The old file is moved aside; the restored database opens with the new password and holds the backup's data.",
     "Pass"),
    ("UI", "Consent has nothing preselected", "Promise 6",
     "providers_view_test.dart :: will not grant until a scope is chosen",
     "Open the consent dialog for a cloud provider.",
     "The Grant button stays disabled until the user picks a scope.",
     "Pass"),
    ("UI", "The search offer shows what would be sent", "D-45",
     "web_search_offer_test.dart :: an offer shows the exact words under the answer, and nothing is sent",
     "The server offers a search for \"I feel tired today\".",
     "Shows \"Search the web for: \"I feel tired today\"\" and that only these words are sent; nothing is sent.",
     "Pass"),
    ("UI", "An error ends the turn in the app", "D-16",
     "chat_turn_end_test.dart :: an error ends the turn and the next message can be sent",
     "Send a message; the server sends a stage event, then an error.",
     "The error is shown, Stop disappears, Send returns and the next message can be sent.",
     "Pass"),
]

NOTE = (
    "Level: unit = one module on its own; integration = several modules together through the real routes, "
    "pipeline or scripts, with the language model and the network replaced by test stand-ins; "
    "UI = Flutter widget test. "
    f"All 30 test cases (50 runs counting parameter variants) passed on {RUN}, at commit 6a51798. "
    "The full suites last recorded 1,914 backend tests passed, 0 failed (docs/FREEZE_LIST.md §7.76, "
    "22 Oct 2026), and 372 Flutter tests passed (§7.75)."
)
TITLE = "Table 6.1: Test cases for PIP"


def markdown():
    out = [f"# {TITLE}", "", "| ID | Level | What is tested | Input / steps | Expected result | Result |",
           "|---|---|---|---|---|---|"]
    for i, (lvl, title, covers, tid, inp, exp, res) in enumerate(ROWS, 1):
        cell = f"**{title}** ({covers})<br>`{tid}`"
        out.append(f"| TC-{i:02d} | {lvl} | {cell} | {inp} | {exp} | {res} |")
    out += ["", f"*Note.* {NOTE}", ""]
    return "\n".join(out)


def html():
    rows = []
    for i, (lvl, title, covers, tid, inp, exp, res) in enumerate(ROWS, 1):
        rows.append(
            f"<tr><td>TC-{i:02d}</td><td>{lvl}</td>"
            f"<td><b>{escape(title)}</b> ({escape(covers)})<br><span class=\"tid\">{escape(tid)}</span></td>"
            f"<td>{escape(inp)}</td><td>{escape(exp)}</td><td>{escape(res)}</td></tr>"
        )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{TITLE}</title>
<style>
  body {{ font-family: "Times New Roman", serif; font-size: 10pt; margin: 24px; background: #fff; color: #000; }}
  p.cap {{ font-size: 12pt; margin: 0 0 6px 0; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #000; padding: 3px 5px; vertical-align: top; text-align: left; }}
  th {{ background: #d9d9d9; font-weight: bold; }}
  .tid {{ font-size: 8pt; color: #333; word-break: break-all; }}
  p.note {{ font-size: 10pt; margin-top: 6px; }}
  col.id {{ width: 6%; }} col.lv {{ width: 9%; }} col.wh {{ width: 27%; }}
  col.in {{ width: 23%; }} col.ex {{ width: 26%; }} col.re {{ width: 9%; }}
</style></head><body>
<p class="cap"><b>{TITLE}</b></p>
<table>
<colgroup><col class="id"><col class="lv"><col class="wh"><col class="in"><col class="ex"><col class="re"></colgroup>
<thead><tr><th>ID</th><th>Level</th><th>What is tested (test)</th><th>Input / steps</th><th>Expected result</th>
<th>Result</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table>
<p class="note"><i>Note.</i> {escape(NOTE)}</p>
</body></html>
"""


if __name__ == "__main__":
    with open(os.path.join(HERE, "table_6_1_test_cases.md"), "w", encoding="utf-8") as f:
        f.write(markdown())
    with open(os.path.join(HERE, "table_6_1_test_cases.html"), "w", encoding="utf-8") as f:
        f.write(html())
    print(len(ROWS), "rows written")
