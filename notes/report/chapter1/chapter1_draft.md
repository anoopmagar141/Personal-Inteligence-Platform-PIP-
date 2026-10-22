# CHAPTER 1: INTRODUCTION

## 1.1 Background of the Study

Assistants built on large language models are now used every day for writing, studying and programming. Such an assistant becomes more useful when it remembers its user: the projects they are working on, the tools they prefer, and the decisions they have already made. Research systems have added long-term memory to language model assistants (Packer et al., 2023; Zhang et al., 2024), and commercial assistants offer it too: Chhikara, Khant, Aryan, Singh, and Yadav (2025), for example, compare their own memory system with the memory feature of OpenAI's assistant.

Two recent developments make it possible to run such an assistant on the user's own computer instead of on a company's servers. Language models are released as open weights in several sizes, including compressed (quantised) versions small enough for an ordinary computer (Qwen Team, 2024), and local model servers such as Ollama make them easy to run. A model of seven billion parameters now answers at an interactive speed on a laptop graphics card with 8 GB of memory (Chapter 6).

Remembering a user, however, brings two risks. The first is privacy: what an assistant remembers is personal data, and data protection law asks that protection be built into a system by design and by default (Regulation (EU) 2016/679, 2016, Art. 25). The second is accuracy: language models can produce statements that are not supported by what they were given (Ji et al., 2023), and when such a statement is stored as a fact about the user, it is used again in every later conversation.

This project, the Personal Intelligence Platform (PIP), is a personal assistant designed around both risks. It is a desktop application for Windows that runs its language model locally, keeps each user's conversations, memory, documents and decisions in an encrypted database on their own computer, and decides what it may learn about the user through a fixed set of rules, called the Constitution, that the program checks every time.

## 1.2 Problem Statement

An assistant that learns from conversations has to decide what to remember, and most current approaches let the language model make that decision. Three problems follow.

First, the user's personal data leaves their computer. When the assistant and its memory run on a remote service, every conversation and every remembered fact is sent to, and kept by, someone else.

Second, the assistant can learn things the user never said. A quote can be real and still not support the fact drawn from it: a user who says "I have been comparing FastAPI and Flask" has not said that they prefer Flask. In the same way, a sentence about someone else ("My friend wants to pass the Azure Fundamentals exam") can be taken as the user's own goal. Both mistakes happened in this project: the first wrote "prefers Flask" into an early version's memory, and the second was found in a test recording, each before the check that now stops it was added.

Third, the user cannot see or check why the assistant believes something about them. Without a record of each decision, a wrong belief cannot be traced back to the conversation that produced it. Worse, a safety mechanism that has quietly stopped working looks the same as one that works: during this project, the most costly faults were of this kind, such as encryption that was implemented but at first never given a key, and evidence that was collected but never checked.

The problem this project addresses is therefore: how can a personal assistant remember its user while keeping their data on their own computer, learning only what the user's own words support, and making every learning decision possible to check?

## 1.3 Objectives

### 1.3.1 General Objective

To design, build and evaluate a local-first personal AI assistant whose learning about its user is controlled by an auditable, rule-based enforcement mechanism.

### 1.3.2 Specific Objectives

1. To build a Windows desktop assistant that runs its language model on the user's computer and keeps each profile's chats, memory, documents and decisions in an encrypted database, opened only with the profile's password.
2. To learn facts about the user only at the end of a conversation, and only through three checks in order: the quoted evidence is in the transcript and was written by the user; the user's own words support the claim; and the Constitution's rules allow it. The assistant must never change the user's name, language or time zone, and must write sensitive facts only after the user confirms them.
3. To send nothing outside the computer without the user's recorded consent, and to search the web only after the user approves the exact query.
4. To record every learning decision in an append-only audit log.
5. To keep each profile's data separate from every other profile's, and to answer questions about the user from their current record.
6. To write each of these guarantees as a promise with a test that is seen to fail when the mechanism behind it is weakened, and to measure how accurately the assistant learns and how fast it answers.

## 1.4 Scope of the Study

The project covers a desktop assistant for one computer running Windows 11. It consists of a Flutter desktop application and a Python backend (FastAPI) that run on the same computer, and a local language model, qwen2.5:7b, served by Ollama. It was developed and measured on one computer with an Intel Core i9-14900HX processor, 16 GB of memory and an NVIDIA GeForce RTX 4060 Laptop graphics card with 8 GB of memory. Several password-protected profiles can be kept on one computer. The assistant offers chat with answers streamed as they are written; a memory of the user's skills, preferences, goals, projects, topics and preferred style of answer; projects and decisions; uploaded documents that can be searched; a record of each chat; a review screen where the user confirms or dismisses what the assistant has learned; and backup and restore. The backend can also use a cloud model through an OpenAI-compatible interface, only with the user's consent; this version of the app offers no screen for adding one. Conversations are in English.

The following are outside the scope of this project: mobile and web versions (an older web client and a command-line client exist for testing, but the Flutter application is the deliverable), synchronising data between devices, a server shared by many users, voice input, languages other than English, and training or fine-tuning the language model.

## 1.5 Significance of the Study

For users, PIP shows that an assistant can remember them without sending their data away, can ask before it stores sensitive facts, and can show them what it has learned so that they can correct it.

For research, PIP is a working example of governing an assistant's memory with fixed, testable rules and an audit trail instead of leaving the decision to the language model, the approach taken by the memory systems reviewed in Chapter 2. Its learning is measured, not assumed: Chapter 6 reports how often it learns true facts and how often it is fooled by trick statements.

For practice, the development method used here, in which each guarantee is written as a promise and backed by a test that is first seen to fail, can be reused in other projects. Measuring the system in this way also finds problems that do not show up as errors: measuring answer speed for this report found that every answer waited about four seconds while the computer first tried a network address that the model server does not listen on. The fault was then fixed, and the time to the first word fell from 4.5 seconds to 0.4 seconds.

## 1.6 Limitations

The project has the following limitations, discussed further in Chapter 7.

1. The evidence check is deliberately strict, so the assistant learns little from long, natural conversations: on a set of long test conversations it learned none of 81 true facts, while writing none of 162 trick statements.
2. The check is not perfect in the other direction either: in a blind review, 8 of 58 quotes that it accepted did not support their claim. The Constitution then asked the user about four of them, discarded three and stored one.
3. Searching uploaded documents rarely finds the passage that answers a question (2 of 54 questions in a test), because of how documents are divided into pieces and the similarity score required.
4. Whether a configured model runs locally is taken from what the person who configured it recorded; PIP does not verify it.
5. One backend process serves every profile, so profiles are kept apart by the program's own mechanisms rather than by the operating system.
6. Uploaded document files are also kept as ordinary, unencrypted files in the profile's folder; the copy inside the database is encrypted.
7. The system was evaluated on one computer, in English, and mostly on test conversations written for the purpose rather than on real users' conversations.
8. One known defect is left open: a sentence that reports what someone else said about the user (for example, "My friend says I should run a marathon") can still be recorded as the user's topic.

## 1.7 Organization of the Report

The rest of this report is organised as follows. Chapter 2 reviews the literature on memory for language model assistants, retrieval, the reliability of model output, and the protection of personal data, and identifies the research gap. Chapter 3 describes the methodology: the development method, the system requirements, the tools and technologies used, the feasibility study and the system architecture. Chapter 4 presents the system design through use case, data flow, entity-relationship, package, class, sequence and activity diagrams. Chapter 5 describes the implementation of the frontend, the backend, the database and the main algorithms, with screenshots of the system. Chapter 6 presents the test plan, the test cases, unit, integration and system testing, and the evaluation of accuracy and speed. Chapter 7 concludes the report and recommends future work.
