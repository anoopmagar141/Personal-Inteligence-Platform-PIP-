# CHAPTER 2: LITERATURE REVIEW

## 2.1 Introduction

This chapter reviews the work that PIP builds on and the work it is compared with. PIP is a personal assistant that runs a language model on the user's own computer, remembers facts about the user across conversations, and decides what it may learn through a fixed set of rules called the Constitution. Four areas of research are therefore relevant: long-term memory for language model assistants (Section 2.2.1), the retrieval of stored information (Section 2.2.2), the reliability and safety of model output (Section 2.2.3), and the privacy and security of personal data (Section 2.2.4). Section 2.2.5 describes the language model that PIP uses. Section 2.3 sets out the theoretical framework that links these areas, Section 2.4 identifies the research gap that PIP addresses, and Section 2.5 summarises the chapter.

## 2.2 Review of Related Works

### 2.2.1 Long-term memory for language model assistants

A language model has no memory of its own between conversations: it can use only the text it receives with each request, its context window. Several systems have been proposed to give an assistant a memory that lasts longer than one conversation. Zhang et al. (2024) survey this research for agents built on large language models. They explain why such agents need memory for long and complex interactions, review how memory modules are designed and evaluated, and identify open problems. Their survey is used here to place the systems described below.

MemGPT (Packer et al., 2023) treats the context window like the main memory of a computer. Borrowing the idea of memory tiers from operating systems, it moves information between the limited context and larger external storage, so that the model can work with documents larger than its window and can hold conversations over many sessions. In MemGPT the language model manages this memory itself, by calling functions that save and retrieve information.

Park et al. (2023) describe generative agents: simulated characters whose behaviour is driven by a language model. Each agent records its experiences in natural language, combines them into higher-level reflections, and retrieves them to plan what to do next. In a sandbox world of 25 agents this produced believable individual and social behaviour, and the authors' ablation studies showed that observation, planning and reflection each contributed to it.

MemoryBank (Zhong, Guo, Gao, Ye, & Wang, 2024) is the closest to PIP's purpose, because it is designed for long-term companion and counselling conversations with one user. It stores past conversations, recalls relevant memories and builds a picture of the user's personality. Its update rule is inspired by the Ebbinghaus forgetting curve: a memory fades or is strengthened according to the time that has passed and its significance. The authors built a companion chatbot, SiliconFriend, on it, and used it with both a closed model (ChatGPT) and an open model (ChatGLM).

Mem0 (Chhikara et al., 2025) is a memory layer intended for production assistants. It extracts the important information from ongoing conversations, consolidates it with what is already stored, and retrieves it when it is needed; a variant stores the memories as a graph of relationships. On the LOCOMO benchmark of long conversations, the authors report better answers than several other memory approaches, at a much lower cost in latency and tokens than giving the model the whole conversation history.

Table 2.1 compares these systems with PIP.

Table 2.1: Long-term memory approaches compared

| System | What is stored | What decides what is stored |
|---|---|---|
| MemGPT (Packer et al., 2023) | Information moved between the context window and external storage | The language model, through function calls |
| Generative agents (Park et al., 2023) | A stream of experiences, reflections and plans | The agent records its experiences; the model writes the reflections |
| MemoryBank (Zhong et al., 2024) | Past conversations and a picture of the user, whose strength changes over time | Summaries written by the model; a forgetting-curve rule for strength |
| Mem0 (Chhikara et al., 2025) | Key facts extracted from conversations, optionally as a graph | The model extracts and consolidates the facts |
| PIP (this project) | Facts about the user (skills, preferences, goals, projects, topics), decisions, and a record of each chat | The model only proposes; a fixed evidence gate and the Constitution decide, and the user confirms sensitive facts |

The difference in the last column is the starting point of this project. In the systems reviewed, what an assistant remembers about its user is decided by the language model, or by a fixed decay rule.

### 2.2.2 Retrieval and sentence embeddings

Retrieval-augmented generation (RAG) was introduced by Lewis et al. (2020). Instead of relying only on what a model learned during training, a RAG system retrieves relevant passages from an external collection and gives them to the model together with the question. Lewis et al. showed that this improves results on open-domain question answering and makes generated text more specific and more factual. They also pointed out that it offers a way to update the knowledge a model draws on, and to show where an answer came from. PIP applies the same idea to one person's records: before it answers, it looks up the user's decisions, stored facts and uploaded documents, and adds what it finds to the prompt.

To find relevant passages, text must be compared by meaning rather than by exact words. Reimers and Gurevych (2019) proposed Sentence-BERT, which turns each sentence into a single vector, so that sentences with a similar meaning have similar vectors and can be compared by cosine similarity. This reduced the time needed to find the most similar pair among 10,000 sentences from about 65 hours to about 5 seconds, without losing accuracy. Wang et al. (2020) showed how to compress a large transformer into a much smaller one, MiniLM, by training the small model to imitate the large model's self-attention; it kept over 99% of the accuracy on several benchmarks with half of the parameters and computation. PIP's document index uses a small sentence-embedding model from this family, all-MiniLM-L6-v2, which runs on the processor and leaves the graphics card to the language model.

Retrieving the right information is only half of the problem: the model must also use it. Liu et al. (2024) found that language models use information at the start and at the end of a long input much better than information in the middle, even models designed for long inputs. This matters for an assistant that builds a long prompt from many sources, as PIP does. It is one reason why the order and the amount of context matter as much as the size of the context window.

### 2.2.3 Reliability and safety of model output

Language models can produce text that reads well but is not supported by their input or by the facts. Ji et al. (2023) survey this problem, called hallucination, across summarisation, dialogue, question answering and other tasks, together with the metrics used to measure it and the methods used to reduce it. For a memory system the risk is greater than for a single answer: a hallucinated fact about the user, once stored, is shown to the model again in later conversations and can shape many future answers.

Bai et al. (2022) proposed Constitutional AI, a method of training a model to be harmless using a short list of written principles instead of human labels for harmful outputs. The model critiques and revises its own answers against the principles, and the revised answers, together with preferences judged by an AI model, are then used to train it. The name of PIP's Constitution is similar, but the idea is different. PIP's Constitution is a fixed file of rules that the program checks at run time, every time the model proposes a fact; it is not used to train the model. This makes each decision repeatable, and possible to check afterwards.

Greshake et al. (2023) showed that applications which give a language model retrieved content, such as web pages, can be attacked through that content: an attacker can place instructions in the data, and the model may follow them. They called this indirect prompt injection, demonstrated it on real systems, and noted that effective defences were lacking. Two of PIP's design choices respond to this risk. The transcript that the model reads at the end of a session marks clearly which turns the user wrote, so that text written by the assistant cannot pass as the user's own words; and the web is searched only after the user approves the exact query.

### 2.2.4 Privacy and security of personal data

A personal assistant holds information about one person, so it must protect it. The European Union's General Data Protection Regulation, Regulation (EU) 2016/679 (2016), requires in Article 25 data protection by design and by default: protection must be built into the way a system processes personal data, and by default only the personal data needed for each purpose may be processed. Although the regulation is a European law, its Article 25 states the design principle that PIP follows: the user's data is kept on the user's own computer, and nothing is sent to an outside service without the user's recorded consent, with no consent option chosen in advance. [Check: ask your supervisor whether to add a local law here, such as Nepal's Privacy Act, 2075 (2018), listed in sources.md.]

When data is encrypted with a key made from a password, the way the password is turned into a key decides how hard the password is to guess. The United States National Institute of Standards and Technology recommends password-based key derivation functions such as PBKDF2, which combine the password with a random salt and repeat the computation many times (Turan, Barker, Burr, & Chen, 2010). PIP follows this recommendation: each profile's database key is derived from the profile's password and a random salt with PBKDF2-HMAC-SHA512, using 256,000 iterations.

### 2.2.5 The language model used

PIP runs a model from Qwen2.5, a family of open-weight language models described by the Qwen Team (2024). The models were pre-trained on 18 trillion tokens and then fine-tuned with over one million examples and with reinforcement learning, which improved instruction following and long-text generation. They are released in several sizes, including quantised versions. PIP uses the 7-billion-parameter instruction model through Ollama, which fits on an 8 GB graphics card together with a 16,384-token context window.

## 2.3 Theoretical Framework

Three ideas from the literature above form the framework of this project.

The first is retrieval-augmented generation (Lewis et al., 2020). An assistant that answers from the user's own records is a retrieval-augmented system whose collection is the user's memory, decisions and documents. Its answers can be only as good as what it retrieves and as the model's use of it (Liu et al., 2024).

The second is the difference between grounding and support, which follows from the work on hallucination (Ji et al., 2023). A memory candidate is grounded if its quoted evidence really appears in the conversation, and supported if those words actually state the claim drawn from them. The two are not the same: a user who says "I have been comparing FastAPI and Flask" has said those words, but has not said that they prefer Flask. PIP therefore checks both, in order: first that the quote is in the transcript and was written by the user, and then that the user's own words state the kind of fact being claimed. The second check is deliberately strict and fails towards rejection, because a fact wrongly rejected can still be learned later, while a fact wrongly accepted becomes a false belief about the user.

The third is data protection by design and by default (Regulation (EU) 2016/679, 2016, Art. 25). It leads to rules that the program enforces rather than only promises: the language model and the data stay on the user's machine, consent is recorded for each outside service, and nothing is shared until the user chooses to share it.

## 2.4 Research Gap

The systems reviewed in Section 2.2.1 show that long-term memory makes an assistant more useful over many conversations. In all four of them, however, what is remembered is decided by the language model or by a fixed decay rule (Chhikara et al., 2025; Packer et al., 2023; Park et al., 2023; Zhong et al., 2024). None of them is described as checking, with a fixed and testable rule, that the user's own words support a belief before it is stored; as asking the user before sensitive facts are stored; or as keeping a lasting record of why each belief was accepted or refused. [Check this sentence against each of the four papers as you read them.] At the same time, the work on hallucination (Ji et al., 2023) and on indirect prompt injection (Greshake et al., 2023) shows that a model's output cannot simply be trusted, and a stored belief is model output that is used again and again.

PIP addresses this gap. It is a personal assistant whose memory is controlled by an auditable enforcement mechanism: the language model may only propose what it has learned; a deterministic evidence gate and the Constitution decide whether a fact is stored, asked about, or rejected; and every such decision leaves an append-only record. It also runs entirely on the user's own computer, following the principle of data protection by design and by default. How well this mechanism works is measured in Chapter 6.

## 2.5 Summary

This chapter reviewed four areas of research. Systems such as MemGPT, generative agents, MemoryBank and Mem0 give language model assistants a long-term memory, but leave the choice of what to remember to the model. Retrieval-augmented generation and sentence embeddings provide the method PIP uses to bring the user's records into each answer, with the limits that Liu et al. (2024) describe. The work on hallucination, Constitutional AI and prompt injection shows why a model's output needs to be checked, and how PIP's rule-based Constitution differs from principles used in training. The GDPR and NIST's key-derivation recommendation set the privacy and security requirements. Together they lead to the gap this project addresses: an assistant whose memory is decided by checkable rules rather than by the model alone. Chapter 3 describes the method used to build it.
