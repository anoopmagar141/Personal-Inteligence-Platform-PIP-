"""Writes the Chapter 2 source list: sources.md (each source, how it was checked, how it fits PIP) and
references.html (the APA 6th reference list, alphabetical, hanging indent, ready to paste into Word).

Every core source was checked on 2026-10-22 against its own record: Crossref for DOIs, the arXiv API, the NeurIPS
proceedings BibTeX, the ACL Anthology, NIST CSRC, EUR-Lex. Text between *stars* is italic in APA.

Run: .venv/Scripts/python.exe -I notes/report/chapter2/make_references.py
"""
import os
import re
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKED = "22 October 2026"

# key, section, APA 6th reference, in-text citation, checked against, what it is, how it fits PIP
SOURCES = [
    ("packer2023", "2.2.1 Memory for LLM assistants",
     "Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S. G., Stoica, I., & Gonzalez, J. E. (2023). "
     "*MemGPT: Towards LLMs as operating systems* (arXiv:2310.08560). Retrieved from https://arxiv.org/abs/2310.08560",
     "(Packer et al., 2023)",
     "arXiv record 2310.08560 (7 authors, first version 12 Oct 2023; no journal version listed)",
     "Treats the model's context window like computer memory: the model itself moves information between a small "
     "working context and larger external stores by calling functions.",
     "The closest design to PIP's long-term memory. Contrast: in MemGPT the model decides what is stored; in PIP the "
     "model only proposes, and the evidence gate and the Constitution decide (Stages 11-13)."),
    ("park2023", "2.2.1 Memory for LLM assistants",
     "Park, J. S., O'Brien, J., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: "
     "Interactive simulacra of human behavior. In *Proceedings of the 36th Annual ACM Symposium on User Interface "
     "Software and Technology* (pp. 1–22). New York, NY: ACM. doi:10.1145/3586183.3606763",
     "(Park et al., 2023)",
     "Crossref record for the DOI (UIST '23, October 2023, pp. 1-22)",
     "Simulated characters keep a stream of memories, retrieve them by how recent, important and relevant they are, "
     "and write higher-level reflections; the model itself rates importance.",
     "Shows memory built from conversation. Contrast: their memories are kept because the model judges them "
     "important; PIP keeps a fact only when the user's own words support it, and counts evidence across chats."),
    ("zhong2024", "2.2.1 Memory for LLM assistants",
     "Zhong, W., Guo, L., Gao, Q., Ye, H., & Wang, Y. (2024). MemoryBank: Enhancing large language models with "
     "long-term memory. *Proceedings of the AAAI Conference on Artificial Intelligence, 38*(17), 19724–19731. "
     "doi:10.1609/aaai.v38i17.29946",
     "(Zhong, Guo, Gao, Ye, & Wang, 2024) the first time, then (Zhong et al., 2024)",
     "Crossref record for the DOI (AAAI 2024, vol. 38, issue 17)",
     "A long-term memory for a companion chatbot that summarises past conversations and a user portrait, and lets "
     "memories fade or strengthen over time, inspired by the forgetting curve.",
     "Closest to PIP's user model (skills, preferences, goals). Compare its fading memories with PIP's evidence counts, "
     "age thresholds and decay flag in the Constitution."),
    ("chhikara2025", "2.2.1 Memory for LLM assistants",
     "Chhikara, P., Khant, D., Aryan, S., Singh, T., & Yadav, D. (2025). *Mem0: Building production-ready AI agents "
     "with scalable long-term memory* (arXiv:2504.19413). Retrieved from https://arxiv.org/abs/2504.19413",
     "(Chhikara, Khant, Aryan, Singh, & Yadav, 2025) the first time, then (Chhikara et al., 2025)",
     "arXiv record 2504.19413 (5 authors, 28 Apr 2025). A conference version is claimed only on the company's own "
     "page, so the preprint is cited",
     "A memory layer for assistants that extracts facts from conversations and lets the model decide whether to add, "
     "update or delete memories, measured on a long-conversation benchmark.",
     "The current industry approach. Contrast: Mem0's model decides the update; PIP's update needs supporting words, "
     "the user's confirmation for gated fields, and leaves an audit row for every decision."),
    ("zhang2024", "2.2.1 Memory for LLM assistants",
     "Zhang, Z., Bo, X., Ma, C., Li, R., Chen, X., Dai, Q., . . . Wen, J.-R. (2024). *A survey on the memory "
     "mechanism of large language model based agents* (arXiv:2404.13501). Retrieved from "
     "https://arxiv.org/abs/2404.13501",
     "(Zhang et al., 2024)",
     "arXiv record 2404.13501 (9 authors, 21 Apr 2024). One paper list names a journal; not confirmed, so the "
     "preprint is cited",
     "A survey that sorts agent memory by where it comes from, what form it takes (text or model weights) and how it "
     "is written, managed and read.",
     "Use its terms to place PIP: textual memory, written at the end of a session, read by category per message."),
    ("lewis2020", "2.2.2 Retrieval and embeddings",
     "Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., . . . Kiela, D. (2020). "
     "Retrieval-augmented generation for knowledge-intensive NLP tasks. In H. Larochelle, M. Ranzato, R. Hadsell, "
     "M. F. Balcan, & H. Lin (Eds.), *Advances in Neural Information Processing Systems 33* (pp. 9459–9474). "
     "Red Hook, NY: Curran Associates.",
     "(Lewis et al., 2020)",
     "NeurIPS 2020 proceedings page and its BibTeX (12 authors, pp. 9459-9474, editors as listed)",
     "Introduces retrieval-augmented generation: fetch relevant passages and give them to the model with the "
     "question, so answers can draw on knowledge outside the model.",
     "The idea behind PIP's Stage 5 (documents) and Stages 3-4 (decisions, memory). Cite with PIP's own result that "
     "document search found the answer for only 2 of 54 questions (FREEZE_LIST §7.68)."),
    ("reimers2019", "2.2.2 Retrieval and embeddings",
     "Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence embeddings using Siamese BERT-networks. In "
     "*Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing and the 9th "
     "International Joint Conference on Natural Language Processing (EMNLP-IJCNLP)* (pp. 3982–3992). Hong Kong, "
     "China: Association for Computational Linguistics. doi:10.18653/v1/D19-1410",
     "(Reimers & Gurevych, 2019)",
     "ACL Anthology record D19-1410 (November 2019, pp. 3982-3992)",
     "Trains BERT so that each sentence becomes one vector, and similar sentences get nearby vectors, which makes "
     "search by cosine similarity fast.",
     "The method behind the sentence-transformers library PIP uses for its document index (vector_store, cosine "
     "cut-off 0.60)."),
    ("wang2020", "2.2.2 Retrieval and embeddings",
     "Wang, W., Wei, F., Dong, L., Bao, H., Yang, N., & Zhou, M. (2020). MiniLM: Deep self-attention distillation "
     "for task-agnostic compression of pre-trained transformers. In H. Larochelle, M. Ranzato, R. Hadsell, "
     "M. F. Balcan, & H. Lin (Eds.), *Advances in Neural Information Processing Systems 33* (pp. 5776–5788). "
     "Red Hook, NY: Curran Associates.",
     "(Wang et al., 2020)",
     "NeurIPS 2020 proceedings page and its BibTeX (6 authors, pp. 5776-5788)",
     "Shrinks a large transformer into a small, fast one by teaching it to copy the large model's attention "
     "patterns, keeping most of its accuracy.",
     "The family of PIP's embedding model, all-MiniLM-L6-v2, chosen because it runs on the CPU and leaves the GPU to "
     "the language model."),
    ("liu2024", "2.2.2 Retrieval and embeddings",
     "Liu, N. F., Lin, K., Hewitt, J., Paranjape, A., Bevilacqua, M., Petroni, F., & Liang, P. (2024). Lost in the "
     "middle: How language models use long contexts. *Transactions of the Association for Computational "
     "Linguistics, 12*, 157–173. doi:10.1162/tacl_a_00638",
     "(Liu et al., 2024)",
     "Crossref record for the DOI (TACL vol. 12, pp. 157-173)",
     "Shows that models use information at the start and end of a long prompt better than information in the "
     "middle.",
     "Supports PIP's context assembly choices (Stage 7) and helps explain why long chats learned so few true facts "
     "(FREEZE_LIST §7.70) even after the window grew to 16k tokens."),
    ("ji2023", "2.2.3 Trust and safety of LLM output",
     "Ji, Z., Lee, N., Frieske, R., Yu, T., Su, D., Xu, Y., . . . Fung, P. (2023). Survey of hallucination in "
     "natural language generation. *ACM Computing Surveys, 55*(12), 1–38. doi:10.1145/3571730",
     "(Ji et al., 2023)",
     "Crossref record for the DOI (10 authors, vol. 55, issue 12, pp. 1-38)",
     "A survey of hallucination: generated text that is not supported by its source or by facts, its causes, and how "
     "it is measured and reduced.",
     "The theory behind PIP's two checks: grounding (the quote was really said) and the evidence gate (the quote "
     "supports the claim). Learned memories are a place where hallucination becomes a stored belief."),
    ("bai2022", "2.2.3 Trust and safety of LLM output",
     "Bai, Y., Kadavath, S., Kundu, S., Askell, A., Kernion, J., Jones, A., . . . Kaplan, J. (2022). *Constitutional "
     "AI: Harmlessness from AI feedback* (arXiv:2212.08073). Retrieved from https://arxiv.org/abs/2212.08073",
     "(Bai et al., 2022)",
     "arXiv record 2212.08073 (51 authors, 15 Dec 2022)",
     "Trains a model to be harmless using a written list of principles: the model critiques and revises its own "
     "answers against them, and the training uses that feedback.",
     "Explain the difference in name: Bai et al.'s constitution shapes a model during training; PIP's Constitution "
     "(constitutional.json) is a fixed rule file that code checks at run time, so every decision can be traced."),
    ("greshake2023", "2.2.3 Trust and safety of LLM output",
     "Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T., & Fritz, M. (2023). Not what you've signed up "
     "for: Compromising real-world LLM-integrated applications with indirect prompt injection. In *Proceedings of the "
     "16th ACM Workshop on Artificial Intelligence and Security* (pp. 79–90). New York, NY: ACM. "
     "doi:10.1145/3605764.3623985",
     "(Greshake et al., 2023)",
     "Crossref record for the DOI (AISec '23, November 2023, pp. 79-90)",
     "Shows that text an application feeds to a model (web pages, documents) can carry hidden instructions that the "
     "model then follows.",
     "Supports PIP's choices to treat role headers as a security boundary (an assistant line cannot pose as the "
     "user), and to search the web only after the user clicks (D-45)."),
    ("turan2010", "2.2.4 Privacy and security",
     "Turan, M. S., Barker, E., Burr, W., & Chen, L. (2010). *Recommendation for password-based key derivation: "
     "Part 1: Storage applications* (NIST Special Publication 800-132). Gaithersburg, MD: National Institute of "
     "Standards and Technology. doi:10.6028/NIST.SP.800-132",
     "(Turan, Barker, Burr, & Chen, 2010) the first time, then (Turan et al., 2010)",
     "NIST CSRC page (December 2010; still current, NIST plans a revision)",
     "NIST's recommendation for turning a password into an encryption key with PBKDF2, a salt and a large iteration "
     "count.",
     "The standard behind PIP's database key: PBKDF2-HMAC-SHA512, 256,000 iterations, a random salt per profile "
     "(db_key.py)."),
    ("gdpr2016", "2.2.4 Privacy and security",
     "Regulation (EU) 2016/679 of the European Parliament and of the Council of 27 April 2016 on the protection of "
     "natural persons with regard to the processing of personal data and on the free movement of such data, and "
     "repealing Directive 95/46/EC (General Data Protection Regulation). (2016). *Official Journal of the European "
     "Union*, L 119, p. 1. Retrieved from https://eur-lex.europa.eu/eli/reg/2016/679/oj",
     "(Regulation (EU) 2016/679, 2016, Art. 25)",
     "EUR-Lex official text (OJ L 119, 4 May 2016, p. 1; Article 25 read)",
     "The EU's data protection law. Article 25 requires data protection by design and by default: protection built "
     "into how a system processes data, and by default only the personal data needed for each purpose processed.",
     "The legal form of PIP's design rules: data stays on the machine, nothing is sent without recorded consent, and "
     "no consent scope is preselected (Promises 6 and 7)."),
    ("qwen2024", "2.2.5 The model PIP uses",
     "Qwen Team. (2024). *Qwen2.5 technical report* (arXiv:2412.15115). Retrieved from "
     "https://arxiv.org/abs/2412.15115",
     "(Qwen Team, 2024)",
     "arXiv record 2412.15115 (19 Dec 2024; listed first author \"Qwen\", the team; arXiv shows part of the author "
     "list only, so the group author is used)",
     "Describes the Qwen2.5 family of open-weight language models, how they were trained, and how they score on "
     "standard benchmarks.",
     "The source for the model PIP ships with (qwen2.5:7b), chosen because every thesis number was measured on it "
     "and it fits an 8 GB GPU with a 16k window."),
]

OPTIONAL = [
    ("nepal2018", "2.2.4 Privacy and security (local law, optional)",
     "Privacy Act, 2075 (2018) (Nepal). Retrieved from https://lpr.adb.org/resource/privacy-act-2075-2018-nepal",
     "(Privacy Act, 2075 [2018])",
     "ADB Law and Policy Reform database page, dated 18 September 2018, with the English translation. The Nepal Law "
     "Commission's own page could not be opened from here; check it if you cite the Act",
     "Nepal's law on the right to privacy, including personal data and electronic correspondence, and how personal "
     "information may be collected and used.",
     "Local legal context for a personal data system built in Nepal. Ask your supervisor whether a local law is "
     "wanted here."),
    ("cavoukian2009", "2.3 Theoretical framework (optional, NOT verified)",
     "Cavoukian, A. (2009). *Privacy by design: The 7 foundational principles*. Toronto, Canada: Information and "
     "Privacy Commissioner of Ontario.",
     "(Cavoukian, 2009)",
     "NOT verified from the publisher: ipc.on.ca refused automated access, and the copies found online are different "
     "versions (one dated May 2010). Most citations give August 2009, revised January 2011. Open the official PDF "
     "yourself and copy its dates before citing it",
     "The original seven principles of privacy by design, such as privacy as the default and privacy built into the "
     "design.",
     "The idea that GDPR Article 25 later made law; useful for the theoretical framework if you can confirm its "
     "dates."),
]


def html_ref(apa):
    out = escape(apa)
    return re.sub(r"\*(.+?)\*", r"<i>\1</i>", out)


def sort_key(src):
    return re.sub(r"[^a-z]", "", src[2].lower())


def write_md():
    lines = ["# Chapter 2 sources (checked 22 October 2026)", "",
             "Fifteen core sources, each checked against its own record (DOI, arXiv, proceedings, NIST, EUR-Lex), "
             "plus two optional ones. Read each source's abstract before you write about it: the notes below are "
             "short summaries in my words, not quotes.", "",
             "Use APA 6th edition, as the LUC guide asks. The Word-ready list is `references.html` (alphabetical, "
             "hanging indent). APA 6 in-text rule: one or two authors, always both names; three to five, all names "
             "the first time and then the first name with et al.; six or more, et al. from the start.", ""]
    section = None
    for i, s in enumerate(SOURCES + OPTIONAL, 1):
        key, sec, apa, cite, checked, what, fit = s
        if sec != section:
            lines += [f"## {sec}", ""]
            section = sec
        lines += [f"**{i}. {cite}**", "", f"- Reference: {apa}", f"- Checked: {checked}.",
                  f"- What it is: {what}", f"- How it fits PIP: {fit}", ""]
    lines += ["## The research gap these sources set up (for 2.4)", "",
              "The memory systems above (MemGPT, Generative Agents, MemoryBank, Mem0) let the language model decide "
              "what to remember about the user. None of them checks with a fixed, testable rule that the user's own "
              "words support a stored belief, asks the user before writing sensitive fields, or keeps an append-only "
              "record of why each belief was accepted or refused. PIP combines a model that runs on the user's own "
              "machine, a deterministic evidence gate and Constitution, and an audit log: an "
              "auditable enforcement mechanism for what an assistant may learn about its user. Check this claim "
              "against each paper as you read it, and soften it where a paper does more than its abstract says.", ""]
    open(os.path.join(HERE, "sources.md"), "w", encoding="utf-8").write("\n".join(lines))


def write_html():
    core = sorted(SOURCES, key=sort_key)
    items = "\n".join(f"<p class=\"ref\">{html_ref(s[2])}</p>" for s in core)
    extra = "\n".join(f"<p class=\"ref\">{html_ref(s[2])}</p>" for s in sorted(OPTIONAL, key=sort_key))
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>References</title>
<style>
  body {{ font-family: "Times New Roman", serif; font-size: 12pt; margin: 32px; background: #fff; color: #000; }}
  h1 {{ font-size: 12pt; text-align: center; font-weight: bold; }}
  p.ref {{ padding-left: 0.5in; text-indent: -0.5in; margin: 0 0 12pt 0; line-height: 2; }}
  p.note {{ font-size: 10pt; color: #444; }}
</style></head><body>
<h1>REFERENCES</h1>
{items}
<p class="note">Optional (see sources.md before using them):</p>
{extra}
</body></html>
"""
    open(os.path.join(HERE, "references.html"), "w", encoding="utf-8").write(html)


if __name__ == "__main__":
    write_md()
    write_html()
    print(len(SOURCES), "core and", len(OPTIONAL), "optional sources written")
