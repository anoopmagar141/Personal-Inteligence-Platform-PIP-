# Chapter 2 sources (checked 22 October 2026)

Fifteen core sources, each checked against its own record (DOI, arXiv, proceedings, NIST, EUR-Lex), plus two optional ones. Read each source's abstract before you write about it: the notes below are short summaries in my words, not quotes.

Use APA 6th edition, as the LUC guide asks. The Word-ready list is `references.html` (alphabetical, hanging indent). APA 6 in-text rule: one or two authors, always both names; three to five, all names the first time and then the first name with et al.; six or more, et al. from the start.

## 2.2.1 Memory for LLM assistants

**1. (Packer et al., 2023)**

- Reference: Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S. G., Stoica, I., & Gonzalez, J. E. (2023). *MemGPT: Towards LLMs as operating systems* (arXiv:2310.08560). Retrieved from https://arxiv.org/abs/2310.08560
- Checked: arXiv record 2310.08560 (7 authors, first version 12 Oct 2023; no journal version listed).
- What it is: Treats the model's context window like computer memory: the model itself moves information between a small working context and larger external stores by calling functions.
- How it fits PIP: The closest design to PIP's long-term memory. Contrast: in MemGPT the model decides what is stored; in PIP the model only proposes, and the evidence gate and the Constitution decide (Stages 11-13).

**2. (Park et al., 2023)**

- Reference: Park, J. S., O'Brien, J., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: Interactive simulacra of human behavior. In *Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology* (pp. 1–22). New York, NY: ACM. doi:10.1145/3586183.3606763
- Checked: Crossref record for the DOI (UIST '23, October 2023, pp. 1-22).
- What it is: Simulated characters keep a stream of memories, retrieve them by how recent, important and relevant they are, and write higher-level reflections; the model itself rates importance.
- How it fits PIP: Shows memory built from conversation. Contrast: their memories are kept because the model judges them important; PIP keeps a fact only when the user's own words support it, and counts evidence across chats.

**3. (Zhong, Guo, Gao, Ye, & Wang, 2024) the first time, then (Zhong et al., 2024)**

- Reference: Zhong, W., Guo, L., Gao, Q., Ye, H., & Wang, Y. (2024). MemoryBank: Enhancing large language models with long-term memory. *Proceedings of the AAAI Conference on Artificial Intelligence, 38*(17), 19724–19731. doi:10.1609/aaai.v38i17.29946
- Checked: Crossref record for the DOI (AAAI 2024, vol. 38, issue 17).
- What it is: A long-term memory for a companion chatbot that summarises past conversations and a user portrait, and lets memories fade or strengthen over time, inspired by the forgetting curve.
- How it fits PIP: Closest to PIP's user model (skills, preferences, goals). Compare its fading memories with PIP's evidence counts, age thresholds and decay flag in the Constitution.

**4. (Chhikara, Khant, Aryan, Singh, & Yadav, 2025) the first time, then (Chhikara et al., 2025)**

- Reference: Chhikara, P., Khant, D., Aryan, S., Singh, T., & Yadav, D. (2025). *Mem0: Building production-ready AI agents with scalable long-term memory* (arXiv:2504.19413). Retrieved from https://arxiv.org/abs/2504.19413
- Checked: arXiv record 2504.19413 (5 authors, 28 Apr 2025). A conference version is claimed only on the company's own page, so the preprint is cited.
- What it is: A memory layer for assistants that extracts facts from conversations and lets the model decide whether to add, update or delete memories, measured on a long-conversation benchmark.
- How it fits PIP: The current industry approach. Contrast: Mem0's model decides the update; PIP's update needs supporting words, the user's confirmation for gated fields, and leaves an audit row for every decision.

**5. (Zhang et al., 2024)**

- Reference: Zhang, Z., Bo, X., Ma, C., Li, R., Chen, X., Dai, Q., . . . Wen, J.-R. (2024). *A survey on the memory mechanism of large language model based agents* (arXiv:2404.13501). Retrieved from https://arxiv.org/abs/2404.13501
- Checked: arXiv record 2404.13501 (9 authors, 21 Apr 2024). One paper list names a journal; not confirmed, so the preprint is cited.
- What it is: A survey that sorts agent memory by where it comes from, what form it takes (text or model weights) and how it is written, managed and read.
- How it fits PIP: Use its terms to place PIP: textual memory, written at the end of a session, read by category per message.

## 2.2.2 Retrieval and embeddings

**6. (Lewis et al., 2020)**

- Reference: Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., . . . Kiela, D. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. In H. Larochelle, M. Ranzato, R. Hadsell, M. F. Balcan, & H. Lin (Eds.), *Advances in Neural Information Processing Systems 33* (pp. 9459–9474). Red Hook, NY: Curran Associates.
- Checked: NeurIPS 2020 proceedings page and its BibTeX (12 authors, pp. 9459-9474, editors as listed).
- What it is: Introduces retrieval-augmented generation: fetch relevant passages and give them to the model with the question, so answers can draw on knowledge outside the model.
- How it fits PIP: The idea behind PIP's Stage 5 (documents) and Stages 3-4 (decisions, memory). Cite with PIP's own result that document search found the answer for only 2 of 54 questions (FREEZE_LIST §7.68).

**7. (Reimers & Gurevych, 2019)**

- Reference: Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence embeddings using Siamese BERT-networks. In *Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing and the 9th International Joint Conference on Natural Language Processing (EMNLP-IJCNLP)* (pp. 3982–3992). Hong Kong, China: Association for Computational Linguistics. doi:10.18653/v1/D19-1410
- Checked: ACL Anthology record D19-1410 (November 2019, pp. 3982-3992).
- What it is: Trains BERT so that each sentence becomes one vector, and similar sentences get nearby vectors, which makes search by cosine similarity fast.
- How it fits PIP: The method behind the sentence-transformers library PIP uses for its document index (vector_store, cosine cut-off 0.60).

**8. (Wang et al., 2020)**

- Reference: Wang, W., Wei, F., Dong, L., Bao, H., Yang, N., & Zhou, M. (2020). MiniLM: Deep self-attention distillation for task-agnostic compression of pre-trained transformers. In H. Larochelle, M. Ranzato, R. Hadsell, M. F. Balcan, & H. Lin (Eds.), *Advances in Neural Information Processing Systems 33* (pp. 5776–5788). Red Hook, NY: Curran Associates.
- Checked: NeurIPS 2020 proceedings page and its BibTeX (6 authors, pp. 5776-5788).
- What it is: Shrinks a large transformer into a small, fast one by teaching it to copy the large model's attention patterns, keeping most of its accuracy.
- How it fits PIP: The family of PIP's embedding model, all-MiniLM-L6-v2, chosen because it runs on the CPU and leaves the GPU to the language model.

**9. (Liu et al., 2024)**

- Reference: Liu, N. F., Lin, K., Hewitt, J., Paranjape, A., Bevilacqua, M., Petroni, F., & Liang, P. (2024). Lost in the middle: How language models use long contexts. *Transactions of the Association for Computational Linguistics, 12*, 157–173. doi:10.1162/tacl_a_00638
- Checked: Crossref record for the DOI (TACL vol. 12, pp. 157-173).
- What it is: Shows that models use information at the start and end of a long prompt better than information in the middle.
- How it fits PIP: Supports PIP's context assembly choices (Stage 7) and helps explain why long chats learned so few true facts (FREEZE_LIST §7.70) even after the window grew to 16k tokens.

## 2.2.3 Trust and safety of LLM output

**10. (Ji et al., 2023)**

- Reference: Ji, Z., Lee, N., Frieske, R., Yu, T., Su, D., Xu, Y., . . . Fung, P. (2023). Survey of hallucination in natural language generation. *ACM Computing Surveys, 55*(12), 1–38. doi:10.1145/3571730
- Checked: Crossref record for the DOI (10 authors, vol. 55, issue 12, pp. 1-38).
- What it is: A survey of hallucination: generated text that is not supported by its source or by facts, its causes, and how it is measured and reduced.
- How it fits PIP: The theory behind PIP's two checks: grounding (the quote was really said) and the evidence gate (the quote supports the claim). Learned memories are a place where hallucination becomes a stored belief.

**11. (Bai et al., 2022)**

- Reference: Bai, Y., Kadavath, S., Kundu, S., Askell, A., Kernion, J., Jones, A., . . . Kaplan, J. (2022). *Constitutional AI: Harmlessness from AI feedback* (arXiv:2212.08073). Retrieved from https://arxiv.org/abs/2212.08073
- Checked: arXiv record 2212.08073 (51 authors, 15 Dec 2022).
- What it is: Trains a model to be harmless using a written list of principles: the model critiques and revises its own answers against them, and the training uses that feedback.
- How it fits PIP: Explain the difference in name: Bai et al.'s constitution shapes a model during training; PIP's Constitution (constitutional.json) is a fixed rule file that code checks at run time, so every decision can be traced.

**12. (Greshake et al., 2023)**

- Reference: Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T., & Fritz, M. (2023). Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection. In *Proceedings of the 16th ACM Workshop on Artificial Intelligence and Security* (pp. 79–90). New York, NY: ACM. doi:10.1145/3605764.3623985
- Checked: Crossref record for the DOI (AISec '23, November 2023, pp. 79-90).
- What it is: Shows that text an application feeds to a model (web pages, documents) can carry hidden instructions that the model then follows.
- How it fits PIP: Supports PIP's choices to treat role headers as a security boundary (an assistant line cannot pose as the user), and to search the web only after the user clicks (D-45).

## 2.2.4 Privacy and security

**13. (Turan, Barker, Burr, & Chen, 2010) the first time, then (Turan et al., 2010)**

- Reference: Turan, M. S., Barker, E., Burr, W., & Chen, L. (2010). *Recommendation for password-based key derivation: Part 1: Storage applications* (NIST Special Publication 800-132). Gaithersburg, MD: National Institute of Standards and Technology. doi:10.6028/NIST.SP.800-132
- Checked: NIST CSRC page (December 2010; still current, NIST plans a revision).
- What it is: NIST's recommendation for turning a password into an encryption key with PBKDF2, a salt and a large iteration count.
- How it fits PIP: The standard behind PIP's database key: PBKDF2-HMAC-SHA512, 256,000 iterations, a random salt per profile (db_key.py).

**14. (Regulation (EU) 2016/679, 2016, Art. 25)**

- Reference: Regulation (EU) 2016/679 of the European Parliament and of the Council of 27 April 2016 on the protection of natural persons with regard to the processing of personal data and on the free movement of such data, and repealing Directive 95/46/EC (General Data Protection Regulation). (2016). *Official Journal of the European Union*, L 119, p. 1. Retrieved from https://eur-lex.europa.eu/eli/reg/2016/679/oj
- Checked: EUR-Lex official text (OJ L 119, 4 May 2016, p. 1; Article 25 read).
- What it is: The EU's data protection law. Article 25 requires data protection by design and by default: protection built into how a system processes data, and by default only the personal data needed for each purpose processed.
- How it fits PIP: The legal form of PIP's design rules: data stays on the machine, nothing is sent without recorded consent, and no consent scope is preselected (Promises 6 and 7).

## 2.2.5 The model PIP uses

**15. (Qwen Team, 2024)**

- Reference: Qwen Team. (2024). *Qwen2.5 technical report* (arXiv:2412.15115). Retrieved from https://arxiv.org/abs/2412.15115
- Checked: arXiv record 2412.15115 (19 Dec 2024; listed first author "Qwen", the team; arXiv shows part of the author list only, so the group author is used).
- What it is: Describes the Qwen2.5 family of open-weight language models, how they were trained, and how they score on standard benchmarks.
- How it fits PIP: The source for the model PIP ships with (qwen2.5:7b), chosen because every thesis number was measured on it and it fits an 8 GB GPU with a 16k window.

## 2.2.4 Privacy and security (local law, optional)

**16. (Privacy Act, 2075 [2018])**

- Reference: Privacy Act, 2075 (2018) (Nepal). Retrieved from https://lpr.adb.org/resource/privacy-act-2075-2018-nepal
- Checked: ADB Law and Policy Reform database page, dated 18 September 2018, with the English translation. The Nepal Law Commission's own page could not be opened from here; check it if you cite the Act.
- What it is: Nepal's law on the right to privacy, including personal data and electronic correspondence, and how personal information may be collected and used.
- How it fits PIP: Local legal context for a personal data system built in Nepal. Ask your supervisor whether a local law is wanted here.

## 2.3 Theoretical framework (optional, NOT verified)

**17. (Cavoukian, 2009)**

- Reference: Cavoukian, A. (2009). *Privacy by design: The 7 foundational principles*. Toronto, Canada: Information and Privacy Commissioner of Ontario.
- Checked: NOT verified from the publisher: ipc.on.ca refused automated access, and the copies found online are different versions (one dated May 2010). Most citations give August 2009, revised January 2011. Open the official PDF yourself and copy its dates before citing it.
- What it is: The original seven principles of privacy by design, such as privacy as the default and privacy built into the design.
- How it fits PIP: The idea that GDPR Article 25 later made law; useful for the theoretical framework if you can confirm its dates.

## The research gap these sources set up (for 2.4)

The memory systems above (MemGPT, Generative Agents, MemoryBank, Mem0) let the language model decide what to remember about the user. None of them checks with a fixed, testable rule that the user's own words support a stored belief, asks the user before writing sensitive fields, or keeps an append-only record of why each belief was accepted or refused. PIP combines a model that runs on the user's own machine, a deterministic evidence gate and Constitution, and an audit log: an auditable enforcement mechanism for what an assistant may learn about its user. Check this claim against each paper as you read it, and soften it where a paper does more than its abstract says.
