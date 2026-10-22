# EXECUTIVE SUMMARY

Personal AI assistants are more useful when they remember their user, but most send every conversation to a company's servers and let the language model itself decide what to remember. This project designed, built and evaluated PIP (Personal Intelligence Platform), a Windows desktop assistant that runs its language model on the user's own computer and keeps each profile's chats, memory, documents and decisions in a database encrypted with a key derived from the profile's password. In PIP the model only proposes what it has learned; fixed rules decide. Each proposed fact must be quoted from the conversation, supported by the user's own words and allowed by a written Constitution, sensitive facts wait for the user's confirmation, and every decision is recorded in an append-only audit log. Nothing leaves the computer without the user's recorded consent. PIP was built with Flutter, Python, FastAPI, SQLCipher, ChromaDB and Ollama, and its guarantees were written as nine promises, each with a test seen to fail when its mechanism was weakened; 1,914 backend and 372 app tests pass. In evaluation PIP stored none of 237 trick statements, but it learned few true facts from long conversations, and a blind check found that 8 of 58 quotes its evidence check accepted did not support their claim. Fixing a defect found by measurement cut the time to an answer's first word from 4.48 to 0.36 seconds. The project shows that an assistant's memory can be governed by auditable rules, at a cost in what it learns.

[Check: the LUC guide asks for an abstract of at most 250 words, in English and in Malay; the college outline asks for an executive summary of 150-300 words. This one is 249 words, so it fits both. Ask your supervisor whether a Malay version and keywords are needed.]

# ACKNOWLEDGEMENTS

I would like to thank my supervisor, Mr. Dipak Adhikari, for guidance, patience and honest feedback throughout this project. [Check: confirm the name and title, and add a co-supervisor or the head of department if you have one.]

I am grateful to Lincoln University College for the opportunity to carry out this project, and to my lecturers, whose teaching made it possible. [Check: name your programme and faculty.]

I also thank my family and friends for their support and patience during the many long evenings this project took. [Check: add any names you wish.]

Finally, PIP is built on open-source software, and I thank the people who make and maintain Flutter, Python, FastAPI, SQLCipher, ChromaDB, Ollama and the Qwen models.

[Check: your college may require you to state how AI tools were used in the project and in this report. Ask your supervisor, and if it is required, add one honest sentence here or in Chapter 3.]

# LIST OF ABBREVIATIONS

| Abbreviation | Meaning |
|---|---|
| AI | Artificial Intelligence |
| API | Application Programming Interface |
| BERT | Bidirectional Encoder Representations from Transformers |
| CORS | Cross-Origin Resource Sharing |
| D‑nn | Defect number in the project's records (D‑01 to D‑51) |
| DFD | Data Flow Diagram |
| ER | Entity–Relationship |
| EU | European Union |
| FR | Functional Requirement |
| GB | Gigabyte |
| GDPR | General Data Protection Regulation |
| GiB | Gibibyte (1,024 × 1,024 × 1,024 bytes) |
| GPU | Graphics Processing Unit |
| HMAC | Hash-based Message Authentication Code |
| HTTP | Hypertext Transfer Protocol |
| ID | Identifier |
| IPv6 | Internet Protocol version 6 |
| JSON | JavaScript Object Notation |
| NIST | National Institute of Standards and Technology |
| ORM | Object–Relational Mapping |
| PBKDF2 | Password-Based Key Derivation Function 2 |
| PDF | Portable Document Format |
| PIP | Personal Intelligence Platform |
| RAG | Retrieval-Augmented Generation |
| REST | Representational State Transfer |
| SHA | Secure Hash Algorithm (SHA-256, SHA-512) |
| SQL | Structured Query Language |
| TC | Test Case |
| UC | Use Case |
| UI | User Interface |
| UX | User Experience |
