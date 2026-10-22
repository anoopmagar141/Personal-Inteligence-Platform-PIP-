# Report screenshots

Taken on 22 October 2026 from the real Windows app, in a throwaway copy of PIP, never the owner's own PIP or data:

- The copy: `D:\FINAL YEAR PROJECT\pip-work\report-shots` (code from commit ccf9d0b, the Release app built from the
  same commit for the v1b check, its own empty `data\` folder, port 8792, started by its `Start test PIP.cmd`).
  It is stopped. Its made-up profile's password is in that folder's `TEST_PASSWORD.txt`. Delete the folder when
  you no longer need it.
- Everything shown is made up: the profile "Alex Demo", the project Lanternfish (the persona the evaluations
  already use), two decisions and a short design note, all added through the copy's own backend; the chats were
  typed into the app. The model was qwen2.5:7b on the Ollama that was already running. Nothing was sent to the web:
  web search consent was granted in the copy so the offer would show, and the offer was never clicked.
- The pictures are of ccf9d0b, before ff916d7 (D-51: the model is told it saves nothing during a chat) and
  b7759c3 (learning after a 2-minute pause). Neither changes how a screen looks, but the model's replies in the
  chats could now be worded differently.
- Each picture is the app window only (1280 x 800 at 150% scaling, so 1902 x 1191 pixels), captured with the
  Windows PrintWindow call by the window's exact program path, so no other window could appear in it.

| File | Figure | Shows |
|---|---|---|
| shot4-13_dark_theme.png | 4.13 | A chat in the dark theme |
| shot4-14_delete_profile.png | 4.14 | The delete-profile dialog (cancelled, nothing deleted) |
| shot5-1_launch.png | 5.1 | The launch screen while PIP starts |
| shot5-2_sign_in.png | 5.2 | The sign-in screen |
| shot5-3_chat.png | 5.3 | A chat with the step strip and a web search offer |
| shot5-4_chat_record.png | 5.4 | A chat's "where we left off" record |
| shot5-5_review.png | 5.5 | The Review tab with a learned goal waiting |
| shot5-6_profile.png | 5.6 | The Profile tab |
| shot5-7_decisions.png | 5.7 | The Decisions tab |
| shot5-8_documents.png | 5.8 | The Documents tab with a search result |
| shot5-9_consent.png | 5.9 | The consent dialog, nothing chosen |
| shot5-10_backup.png | 5.10 | The Backup tab |
| shot5-11_trace.png | 5.11 | The Trace tab for one message |

Two things the pictures show that are worth knowing before an examiner asks:

1. In Figure 5.3 the answer is "I don't have that in front of me": a weather question cannot be answered without
   the web, and PIP offers the search instead of sending it.
2. A first try at the web offer, "What is the latest stable version of Python?", got no offer, because one of the
   made-up decisions contains the word "version" and PIP treats a question sharing a word with a decision as being
   about a project, which it keeps off the web (D-31's rule). That is the design working, not a fault.
