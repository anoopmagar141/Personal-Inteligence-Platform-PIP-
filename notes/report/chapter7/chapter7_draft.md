# CHAPTER 7: CONCLUSION AND RECOMMENDATIONS

## 7.1 Summary

This project designed, built and evaluated PIP, a personal assistant for Windows that runs its language model on the user's own computer and keeps each profile's data in an encrypted database. Its central idea is that the model may only propose what it learns about the user; fixed rules decide. At the end of each chat, every proposed fact must be found in the transcript, be supported by the user's own words, and pass the Constitution's rules, and every learning decision is recorded in an append-only audit log. The system's guarantees were written as nine promises, each with a test seen to fail when its mechanism was weakened, and the whole was then measured.

## 7.2 Conclusion

The general objective has been met: PIP works as a local-first assistant whose learning is controlled by an auditable, rule-based mechanism. Table 7.1 gives the status of each promise at the end of the project.

Table 7.1: The nine promises at the end of the project

| Promise | Status | Evidence |
|---|---|---|
| 1. The Observer writes only through the checks | Holds | TC‑10 |
| 2. The Observer never changes the user's name, language or time zone | Holds; a preference under a different name, such as "language", is not caught | TC‑03, TC‑11 |
| 3. Sensitive fields are written only after the user confirms | Holds for all four kinds of sensitive field | TC‑12 |
| 4. A stored memory is supported by the user's words | Does not hold for the evidence gate alone: 8 of 58 accepted quotes did not support their claim. The Constitution asked about four and discarded three; one true fact was stored in the wrong table | Section 6.6.2 |
| 5. The Observer uses only a model recorded as local | Holds as worded; where a model runs is recorded, not verified | TC‑13 |
| 6. Nothing leaves the computer without recorded consent | Holds at the consent gate, tested by counting what reaches a stand-in server | TC‑14 to TC‑16 |
| 7. Each profile's data is encrypted at rest | Holds for the database and the index text; uploaded file copies, vectors and profile names are not encrypted | TC‑01, TC‑02, TC‑20 |
| 8. Nothing from one profile is served to another | Holds through the program's own mechanisms, within one shared process | TC‑19, TC‑20 |
| 9. Answers reflect the user's current record | Holds for what the model is told; its replies were not measured | TC‑21 |

Eight of the nine promises hold as worded, with their limits stated. The ninth, Promise 4, does not hold for the gate alone, but the layered design meant that the Constitution behind it caught most of what the gate let through. The strongest result is safety: no trick statement was written on the recordings behind the numbers. The cost is recall, since PIP learns few facts from long, natural conversations. The project also showed the value of measuring: a speed measurement found a two-second wait on every call to the model, and fixing it cut the time to the first word from 4.48 to 0.36 seconds.

## 7.3 Limitations

The limitations listed in Section 1.6 remain. The most important are that PIP learns almost nothing from long conversations (0 of 81 true facts in the test set), that document search rarely finds the answering passage (2 of 54), that where a model runs is taken on trust, and that uploaded files are also kept unencrypted. All results come from one computer, in English, and mostly from conversations written for testing rather than from real users.

## 7.4 Future Enhancements

The following improvements are recommended, with privacy and security first:

1. Keep uploaded documents only inside the encrypted database, writing a file out only when the index must be rebuilt.
2. Check where a configured model actually runs, instead of trusting what was recorded.
3. Judge whether the user's words support a fact by their meaning, not only by known phrases, so that PIP can learn from long, natural conversations; this might also tell reported speech apart (D‑41).
4. Split documents into pieces no longer than the embedding model reads (about 250 tokens), index them again, and measure a new similarity cut-off on more than one kind of document.
5. Evaluate PIP with real users, in other languages and on other computers, and re-check the latest fixes in the real app window.
