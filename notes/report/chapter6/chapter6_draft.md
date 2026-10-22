# CHAPTER 6: TESTING AND RESULT ANALYSIS

## 6.1 Test Plan

Testing followed the method of Section 3.1: each promise was written first, its test was written before the fix and run against the old code, the guard was then weakened by hand to see the test fail, and only then was the smallest fix made. A test that checks what is stored, sent or written to disk counts as evidence; a comment or a function's name does not.

PIP was tested at four levels:

1. Unit tests check one module on its own, with pytest for the backend and flutter_test for the app.
2. Integration tests run several modules together through the real HTTP routes, the chat WebSocket, the real pipeline or the real PowerShell scripts. The language model and the network are replaced by stand-ins, such as a small server on 127.0.0.1 that counts every request it receives, so that "nothing was sent" is checked by counting what arrived.
3. System tests run the whole product in a throwaway copy, from one commit, with its own data folder, the real launcher and the real model.
4. Evaluations measure how well PIP learns, searches and answers, on made-up chats and documents. The rule for judging each one was written down and committed before it was run, and every result file records the commit, the model's version and the Ollama version.

The full suites were run before each fix was committed. A per-test time limit of 300 seconds makes a hung test report itself instead of stopping the run silently.

## 6.2 Test Cases

Table 6.1 lists 30 test cases chosen from the suites so that every promise and the main fixes are covered. All 30 were run again on 21 October 2026 from a clean copy of one commit, and all passed.

[Include: table_6_1_test_cases.html]

## 6.3 Unit Testing

The backend has 111 test files and the app 35. Unit tests pin the rules that everything else depends on: the key derivation and the check that only the right key opens a database (TC-01, TC-02), the Constitution's refusal to change the user's name, language or time zone (TC-03), and the database's refusal to change or delete an audit row (TC-08).

The evidence gate has its own labelled set of 105 cases, 40 used while it was built and 65 held out; none of the 61 cases that must be refused is accepted (TC-04). On the held-out supported statements it refused 1 in 15, the cost of failing towards rejection. Other unit tests check that an assistant's reply cannot pose as the user (TC-05) and that years of experience alone do not make the user an expert (TC-06). In the app, widget tests check the contrast of the theme's text colours, that a screen reader can name every control, and that the consent dialog grants nothing until a scope is chosen (TC-28).

## 6.4 Integration Testing

Integration tests check each promise from the outside. The privacy tests count what reaches a stand-in server: a remote endpoint without consent receives nothing, a revoked one receives nothing after the revocation (TC-14, TC-15), and the Observer sends nothing to a server recorded as not local (TC-13). The learning tests run a whole session end and then read the database: nothing reaches the profile that the Constitution did not approve (TC-10), the user's identity is never changed (TC-11), and a sensitive fact waits for the user's confirmation (TC-12). The profile tests use two real profiles: an answer cached for one is never served to the next (TC-19), and an upload interrupted by sign-out leaves no readable text on disk (TC-20). Other tests check that every chat turn ends with an answer or one error (TC-22) that a half-written backup is refused (TC-26), and that a restore does not replay old data (TC-27).

Each of these tests was seen failing with its guard weakened by hand. The records list how many such weakenings each set caught; the 23 tests for the web search offer, for example, caught each of 17.

## 6.5 System Testing

Four system-level checks were run, each in a throwaway copy that never touched the user's data.

1. A product-wide validation pass on 1 October 2026 exercised every workflow with the real model. Profile boundaries, consent in ordinary cases, crash recovery and isolation held. It found a critical defect, a restore that replayed an old database journal and left the profile unopenable (D-01), fixed test-first the next day, and several smaller ones.
2. A migration re-run on 3 October made 307 checks over 10 variants of export and restore through the real scripts. The round trip held, and five new defects in backup handling were found and later fixed.
3. A hard stop of the backend in the middle of an answer lost only the answer being written; the saved chat was intact, PIP restarted in 1.8 seconds and the chat continued.
4. A real-window check on 21 October drove the real Windows app: the first-run import, the web search button and the chat record dialog worked as designed. After a backend restart, however, the app's reconnect attempts multiplied (D-47). This was fixed the same day, but the real window has not been re-checked since.

At the end, on 22 October 2026, the full suites passed: 1,914 backend tests and 372 app tests, with none failing.

## 6.6 Performance Evaluation

### 6.6.1 Answer Speed

Table 6.2 shows how long PIP took to answer on the test computer, before and after one fix.

[Include: table_6_2_answer_speed.html]

The first measurement found that every answer waited about four seconds before the model began. PIP called Ollama at "localhost", which Windows resolves first to the IPv6 address ::1, while Ollama listens only on 127.0.0.1; each request waited 2 seconds before falling back, twice per message. This was recorded as defect D-50 and fixed test-first by calling 127.0.0.1 directly. The median time to the first word fell from 4.48 to 0.36 seconds over 24 runs, and once the model is loaded every kind of message starts within half a second. The model writes about 46 tokens per second, so a full answer takes from half a second for a greeting to about nine seconds for a long explanation, and a repeated first message is answered from the cache in 0.01 seconds. Loading the model for the first message adds about 4.3 seconds.

### 6.6.2 Accuracy

Table 6.3 summarises the accuracy evaluations. Each used made-up chats or documents with known answers, the qwen2.5:7b model unless stated, and a rule for success fixed in advance.

Table 6.3: Accuracy evaluations

| Evaluation | Data | Result |
|---|---|---|
| Learning from short chats | 37 chats of 12–60 words with 23 true facts and 25 trick statements, each run 3 times (69 and 75 cases); four recordings, two models (qwen2.5:7b, llama3.1:8b) | Trick statements written or asked about: 0 of 75 on each recording. Learned rows that were true: 36 of 36. True facts learned or asked about: 35 to 49 of 69 |
| Learning from long chats | 27 chats of 1,400–4,800 words, each with the same 3 true facts and 6 trick statements or near-misses (81 and 162 cases) | On the recording used for these numbers: trick statements written 0 of 162; true facts learned or asked about 0 of 81 (1 and 3 of 81 on two other recordings) |
| Blind check of the evidence gate | 58 quotes the gate accepted and 58 it refused, graded by one reviewer, a separate AI session that never saw the verdicts | 8 of 58 accepted quotes did not support their claim (14%; 95% interval 7–25%). 20 of 58 refused quotes did support it (34%; 24–47%) |
| Document search | 54 questions with known answers over 7 documents, and 12 with no answer | The right passage returned for 2 of 54 at the 0.60 cut-off; 1 of 54 answered correctly; no answer invented for the 12 |
| A new user's greeting | 4 new users, 26 greetings each | Replies saying PIP had no record of the user: 0 of 104 |

The results show the trade-off the design chose. PIP almost never stores something the user did not say: on the recordings behind these numbers, none of 237 trick statements and near-misses was written. The price is recall. On short, direct statements PIP learns or asks about 50 to 70 percent of the true facts, but from long, natural chats it learned almost none, because the evidence gate refuses everyday wording it has no support phrase for, and refuses a quote that runs on into a question. The blind check confirms both sides: a third of the refused quotes were true, while 14% of the accepted ones were not. By the rule fixed before the check, Promise 4 therefore does not hold for the gate alone. The Constitution behind it caught most of the eight: four were asked about, three discarded and one written, a true fact in the wrong table. Two of the three causes were fixed afterwards (D-40 and D-42), so six of the eight are now refused, although this has not been measured again; the third (D-41) is open by the owner's choice.

The evaluations also shaped the design. The first end-to-end measurement, on 28 September 2026, found that 88–90% of learned memories were true but that some trick statements, sarcasm among them, got through. The evidence gate was rebuilt in steps after that, and on recorded model answers no trick statement reached the profile.

Document search is the weakest result. Chunks of 500 words are longer than the 256 tokens the embedding model reads, and the 0.60 cut-off sits above where the answering passages score. Lowering the cut-off alone raised the number of wrong answers, so the setting was kept and the problem is stated as a limitation (Section 7.3).
