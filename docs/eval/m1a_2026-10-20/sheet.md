# M-1(a) grading sheet

For each item, PIP proposed to remember something about the user, citing the user's own words. Decide whether
those words support it. Answer each item with one letter:

- **S** (SUPPORTS): the user's own words in their message say this about themselves; the claim is a fair reading
  of what they said about themselves, not more.
- **D** (DOES NOT): the words do not say it - they are about someone else, a question, a guess, a plan they have
  not made, something in the past, said the other way round, or the claim says more than they did.
- **U** (UNCLEAR): you cannot tell.

For a topic, S means the user themselves raised it (asking about it counts). For a skill, the words have to show
the skill and roughly that level. Judge each item on its own. Nothing else on this sheet says what PIP did.

## 1
PIP would remember about you: a skill: "CSS", at level 0.5 (0 = none, 1 = expert)
Quote: "The flexbox one from yesterday."
Your message: "The flexbox one from yesterday."
PIP's message just before: "That sounds painful. Is there a specific layout issue?"

## 2
PIP would remember about you: a preference: "answer_style" is "concrete"
Quote: "Right, ignore it."
Your message: "Right, ignore it."
PIP's message just before: "That quote isn't something you said."

## 3
PIP would remember about you: a project of yours: "My build" (slow)
Quote: "My build is slow, any ideas?"
Your message: "My build is slow, any ideas?"

## 4
PIP would remember about you: a preference: "preferred_tools" is "LaTeX"
Quote: "I write all my essays in LaTeX."
Your message: "I write all my essays in LaTeX. My supervisor prefers Word though, which is annoying."

## 5
PIP would remember about you: a preference: "preferred_tools" is "plain Node"
Quote: " Mostly plain Node."
Your message: "Mostly plain Node."
PIP's message just before: "Any framework in particular?"

## 6
PIP would remember about you: a topic you are interested in: "exam preparation"
Quote: "One more thing about me: I want to pass the AWS Solutions Architect Associate exam by March. What is a sensible way to space out revision?"
Your message: "One more thing about me: I want to pass the AWS Solutions Architect Associate exam by March. What is a sensible way to space out revision?"
PIP's message just before: "Both combine work from two branches; they differ in the history they leave. A merge records a new commit with two parents, so the history shows that two lines of work existed and were joined. A rebase replays your commits on top of the other branch as if you had started from its latest commit, which gives a straight line with no merge commit. Rebase is pleasant for a short-lived feature branch that only you have touched: it keeps the main history readable and makes each commit easy to review on its own. The firm rule is never to rebase commits that other people have already pulled, because rebasing rewrites them with new identifiers and everyone else's copy suddenly disagrees with yours. Merge is the safer default for shared branches and for recording that a release branch was folded back in. Many teams combine the two: rebase locally to tidy up, then merge into main through a reviewed pull request, sometimes squashing the branch into one commit."

## 7
PIP would remember about you: a skill: "Python", at level 0.9 (0 = none, 1 = expert)
Quote: "What if I rewrote the whole backend in Elixir?"
Your message: "What if I rewrote the whole backend in Elixir?"

## 8
PIP would remember about you: a skill: "Rust", at level 0.0 (0 = none, 1 = expert)
Quote: "I'm learning Rust in my spare time"
Your message: "I'm learning Rust in my spare time, mostly through small CLI tools."

## 9
PIP would remember about you: a preference: "preferred_tools" is "Neovim"
Quote: "I use Neovim for all my coding, it's the only editor I've kept for years."
Your message: "I use Neovim for all my coding, it's the only editor I've kept for years."

## 10
PIP would remember about you: a project of yours: "PIP" (a personal assistant, final year project)
Quote: "I'm building PIP, a personal assistant, as my final year project."
Your message: "I'm building PIP, a personal assistant, as my final year project."

## 11
PIP would remember about you: a project of yours: "PIP" (a personal assistant)
Quote: "I'm building PIP, a personal assistant, as my final year project."
Your message: "I'm building PIP, a personal assistant, as my final year project."

## 12
PIP would remember about you: a preference: "preferred_tools" is "Obsidian"
Quote: "I keep all my notes in Obsidian these days."
Your message: "I keep all my notes in Obsidian these days."

## 13
PIP would remember about you: a topic you are interested in: "sync"
Quote: "I keep coming back to this because our sync is broken."
Your message: "Right, I keep coming back to this because our sync is broken."
PIP's message just before: "They are concurrent, so you need a merge rule."

## 14
PIP would remember about you: a project of yours: "Lanternfish" (a budgeting app for student hostels)
Quote: "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels."
Your message: "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels. How should I name the tables for shared expenses?"
PIP's message just before: "Both combine work from two branches; they differ in the history they leave. A merge records a new commit with two parents, so the history shows that two lines of work existed and were joined. A rebase replays your commits on top of the other branch as if you had started from its latest commit, which gives a straight line with no merge commit. Rebase is pleasant for a short-lived feature branch that only you have touched: it keeps the main history readable and makes each commit easy to review on its own. The firm rule is never to rebase commits that other people have already pulled, because rebasing rewrites them with new identifiers and everyone else's copy suddenly disagrees with yours. Merge is the safer default for shared branches and for recording that a release branch was folded back in. Many teams combine the two: rebase locally to tidy up, then merge into main through a reviewed pull request, sometimes squashing the branch into one commit."

## 15
PIP would remember about you: a skill: "Rust", at level 0.0 (0 = none, 1 = expert)
Quote: "I'm learning Rust in my spare time, mostly through small CLI tools."
Your message: "I'm learning Rust in my spare time, mostly through small CLI tools."

## 16
PIP would remember about you: a preference: "preferred_tools" is "Fortran"
Quote: "Not mine though."
Your message: "Not mine though."
PIP's message just before: "Fortran still dominates some numerical work."

## 17
PIP would remember about you: a skill: "Swift", at level 0.0 (0 = none, 1 = expert)
Quote: "I might learn Swift someday, not sure yet."
Your message: "I might learn Swift someday, not sure yet."

## 18
PIP would remember about you: a preference: "exam_goals" is "AWS Solutions Architect Associate exam by March"
Quote: "One more thing about me: I want to pass the AWS Solutions Architect Associate exam by March."
Your message: "One more thing about me: I want to pass the AWS Solutions Architect Associate exam by March. What is a sensible way to space out revision?"
PIP's message just before: "TCP gives you a reliable, ordered stream. It sets up a connection with a handshake, numbers every byte, resends anything that is lost, and slows down when the network is congested. The price is latency: a lost packet holds up everything behind it until it is resent. UDP sends independent datagrams with no connection, no ordering and no retransmission; a packet either arrives or it does not, and the application decides what to do about it. TCP suits anything where every byte matters and a short delay is acceptable, such as web pages, file transfers and database connections. UDP suits real-time traffic where a late packet is worse than a missing one: voice and video calls, online games, and DNS lookups that are small enough to simply retry. Modern protocols blur the line. QUIC, which carries HTTP/3, runs over UDP but builds its own reliability and encryption on top, so that one lost packet only delays the stream it belongs to rather than every stream on the connection."

## 19
PIP would remember about you: a skill: "Java", at level 0.6 (0 = none, 1 = expert)
Quote: "My sister is a nurse and she loves Java, she keeps telling me to learn it."
Your message: "My sister is a nurse and she loves Java, she keeps telling me to learn it."

## 20
PIP would remember about you: a project of yours: "sync" (fixing sync issue in our system)
Quote: "our sync is broken"
Your message: "Right, I keep coming back to this because our sync is broken."
PIP's message just before: "They are concurrent, so you need a merge rule."

## 21
PIP would remember about you: a goal: "finish my thesis draft by December"
Quote: "My goal is to finish my thesis draft by December."
Your message: "My goal is to finish my thesis draft by December."

## 22
PIP would remember about you: a preference: "Excalidraw" is "drawing tool"
Quote: "I do all my diagrams in Excalidraw these days, it's the only drawing tool I actually open."
Your message: "Quick aside before the next question: I do all my diagrams in Excalidraw these days, it's the only drawing tool I actually open. Anyway, what makes a good sequence diagram?"
PIP's message just before: "For an array, reading by index is constant time, while searching for a value is linear because in the worst case every element is checked. Appending to a dynamic array is constant on average, though an occasional resize copies everything. Inserting at the front of an array is linear, since every element shifts. A linked list flips some of these: inserting at a known node is constant, but finding that node is linear. A hash table gives constant average time for insert, lookup and delete, with a linear worst case when many keys collide. A balanced binary search tree gives logarithmic time for all three and keeps keys in order, which a hash table does not. A binary heap gives constant time to peek at the smallest element and logarithmic time to insert or remove it, which is why priority queues use one. Sorting by comparison costs n log n at best. These numbers describe growth, not speed: a linear scan over a small array often beats a hash lookup in practice because of memory locality."

## 23
PIP would remember about you: a goal: "run a half marathon in April"
Quote: "I've decided to run a half marathon in April."
Your message: "I've decided to run a half marathon in April."

## 24
PIP would remember about you: a skill: "back-end technology", at level 0.0 (0 = none, 1 = expert)
Quote: "still deciding the back"
Your message: "Flutter on the front, still deciding the back."
PIP's message just before: "Nice. What stack are you using for Halyard?"

## 25
PIP would remember about you: a skill: "Flutter", at level 1.0 (0 = none, 1 = expert)
Quote: "Flutter on the front"
Your message: "Flutter on the front, still deciding the back."
PIP's message just before: "Nice. What stack are you using for Halyard?"

## 26
PIP would remember about you: a skill: "TypeScript", at level 0.8 (0 = none, 1 = expert)
Quote: "I work mostly in TypeScript these days, at work and at home."
Your message: "I work mostly in TypeScript these days, at work and at home."

## 27
PIP would remember about you: a skill: "Python", at level 0.8 (0 = none, 1 = expert)
Quote: "I've been writing Python professionally for six years now."
Your message: "I've been writing Python professionally for six years now."

## 28
PIP would remember about you: a skill: "Flutter", at level 0.8 (0 = none, 1 = expert)
Quote: "Flutter on the front"
Your message: "Flutter on the front, still deciding the back."
PIP's message just before: "Nice. What stack are you using for Halyard?"

## 29
PIP would remember about you: a topic you are interested in: "database indexing"
Quote: "Can you explain how a B-tree index makes lookups faster in a database?"
Your message: "Can you explain how a B-tree index makes lookups faster in a database?"

## 30
PIP would remember about you: a preference: "answer_style" is "French"
Quote: "Please answer me in French from now on."
Your message: "Please answer me in French from now on."

## 31
PIP would remember about you: a skill: "Python", at level 1.0 (0 = none, 1 = expert)
Quote: "I've been writing Python professionally for six years now."
Your message: "I've been writing Python professionally for six years now."

## 32
PIP would remember about you: a skill: "Node", at level 1.0 (0 = none, 1 = expert)
Quote: "Mostly plain Node."
Your message: "Mostly plain Node."
PIP's message just before: "Any framework in particular?"

## 33
PIP would remember about you: a preference: "preferred_tools" is "Neovim"
Quote: "I don't use Emacs, never have, and I don't plan to."
Your message: "I don't use Emacs, never have, and I don't plan to."

## 34
PIP would remember about you: a project of yours: "Halyard" (a scheduling app for sailing clubs)
Quote: "I'm working on Halyard, a scheduling app for sailing clubs."
Your message: "I'm working on Halyard, a scheduling app for sailing clubs."

## 35
PIP would remember about you: a preference: "answer_style" is "concise"
Quote: "Please keep your answers short from now on, I just want the answer."
Your message: "Please keep your answers short from now on, I just want the answer."

## 36
PIP would remember about you: a skill: "Go", at level 0.9 (0 = none, 1 = expert)
Quote: "I've written Go professionally for four years."
Your message: "Quick background: I'm a backend developer and I've written Go professionally for four years."

## 37
PIP would remember about you: a skill: "Go", at level 1.0 (0 = none, 1 = expert)
Quote: "I'm a backend developer and I've written Go professionally for four years."
Your message: "Quick background: I'm a backend developer and I've written Go professionally for four years."

## 38
PIP would remember about you: a preference: "preferred_tools" is "Word"
Quote: "My supervisor prefers Word though, which is annoying."
Your message: "I write all my essays in LaTeX. My supervisor prefers Word though, which is annoying."

## 39
PIP would remember about you: a project of yours: "Payments service" (a backend service for a payments system)
Quote: "A payments service."
Your message: "A payments service. My colleague wants us to move to Java but I'm not convinced."
PIP's message just before: "Nice. What are you working on?"

## 40
PIP would remember about you: a project of yours: "Lanternfish" (a budgeting app for student hostels)
Quote: "my main project this term is Lanternfish, a budgeting app for student hostels."
Your message: "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels. How should I name the tables for shared expenses?"
PIP's message just before: "A B-tree keeps keys sorted in wide, shallow nodes. Each node holds many keys and pointers to children, so a lookup starts at the root, compares the key with the few values in that node, and follows exactly one pointer down. Because every node is wide, even a table with millions of rows is usually only three or four levels deep, which means three or four page reads instead of scanning every row. Range queries are cheap too: once the first matching key is found, the leaves are linked, so the database walks along them in order. The cost is on writes. Every insert or update to an indexed column must also update the tree, and occasionally split a full node. That is why indexing every column is a bad idea: reads on the indexed columns get faster while every write gets slower, and the indexes take disk space. A good rule is to index the columns that appear in frequent WHERE clauses and joins, check the query plan to confirm the index is used, and drop indexes nothing reads."

## 41
PIP would remember about you: a project of yours: "None" (None)
Quote: "I use Vim for everything. Actually no, scratch that, I switched to Helix last year."
Your message: "I use Vim for everything. Actually no, scratch that, I switched to Helix last year."

## 42
PIP would remember about you: a project of yours: "backend services" (services built for backend purposes)
Quote: "Mostly backend services."
Your message: "Mostly backend services."
PIP's message just before: "That's a lot of experience. What do you mostly build?"

## 43
PIP would remember about you: a preference: "answer_style" is "French"
Quote: "Please answer me in French from now on."
Your message: "Please answer me in French from now on."

## 44
PIP would remember about you: a skill: "Docker", at level 1.0 (0 = none, 1 = expert)
Quote: "I deploy everything with Docker Compose on a small VPS."
Your message: "I deploy everything with Docker Compose on a small VPS."

## 45
PIP would remember about you: a preference: "answer_style" is "detailed explanations with worked examples"
Quote: "I really like detailed explanations with worked examples, the short ones lose me."
Your message: "I really like detailed explanations with worked examples, the short ones lose me."

## 46
PIP would remember about you: how PIP should answer you: "concise"
Quote: "I'd like shorter answers by the way."
Your message: "I'd like shorter answers by the way."
PIP's message just before: "It's a hosted LaTeX editor."

## 47
PIP would remember about you: a project of yours: "Pebblebox" (a recipe-sharing app)
Quote: "my cousin's main project is Pebblebox, a recipe-sharing app"
Your message: "My cousin's main project is Pebblebox, a recipe-sharing app, and he asked me how to store ingredients. Is a separate table the right call?"
PIP's message just before: "Plain nouns that match what people say out loud work best: expense, share, member, settlement. Avoid abbreviations and keep one naming style for every table."

## 48
PIP would remember about you: a preference: "main_projects" is "Pebblebox"
Quote: "My cousin's main project is Pebblebox, a recipe-sharing app, and he asked me how to store ingredients. Is a separate table the right call?"
Your message: "My cousin's main project is Pebblebox, a recipe-sharing app, and he asked me how to store ingredients. Is a separate table the right call?"
PIP's message just before: "Plain nouns that match what people say out loud work best: expense, share, member, settlement. Avoid abbreviations and keep one naming style for every table."

## 49
PIP would remember about you: a goal: "building backend services"
Quote: "Mostly backend services."
Your message: "Mostly backend services."
PIP's message just before: "That's a lot of experience. What do you mostly build?"

## 50
PIP would remember about you: a skill: "GraphQL", at level 0.0 (0 = none, 1 = expert)
Quote: "what would it take to add GraphQL?"
Your message: "Startup time, mostly. Also, what would it take to add GraphQL?"
PIP's message just before: "What's your concern?"

## 51
PIP would remember about you: a goal: "Move database to Postgres before the next release"
Quote: "I've decided to move our database to Postgres before the next release."
Your message: "I've decided to move our database to Postgres before the next release."

## 52
PIP would remember about you: a preference: "preferred_tools" is "Obsidian"
Quote: "I keep all my notes in Obsidian these days."
Your message: "I keep all my notes in Obsidian these days."

## 53
PIP would remember about you: a preference: "project_management" is "Lanternfish, a budgeting app for student hostels"
Quote: "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels."
Your message: "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels. How should I name the tables for shared expenses?"
PIP's message just before: "Normalisation organises tables so each fact is stored once, which stops updates from leaving copies that disagree. First normal form asks that every column hold a single value: no lists of phone numbers squeezed into one field, and no repeating groups of columns such as phone1, phone2 and phone3. Second normal form applies to tables with a composite key and asks that every other column depend on the whole key, not on part of it; a course name stored in an enrolment table keyed by student and course depends only on the course, so it belongs in a course table. Third normal form asks that columns depend on the key and nothing else, so a city stored next to a postcode, where the city follows from the postcode, moves into its own table. The practical test is to ask where you would have to change something if a fact changed. If the answer is several rows, the design invites inconsistency. Reporting databases sometimes denormalise on purpose to make reads faster."

## 54
PIP would remember about you: a skill: "Java", at level 0.5 (0 = none, 1 = expert)
Quote: "I used to love Java back in school, but not anymore."
Your message: "I used to love Java back in school, but not anymore."

## 55
PIP would remember about you: a topic you are interested in: "sync"
Quote: "Right, I keep coming back to this because our sync is broken."
Your message: "Right, I keep coming back to this because our sync is broken."
PIP's message just before: "They are concurrent, so you need a merge rule."

## 56
PIP would remember about you: a topic you are interested in: "marathon"
Quote: "My friend says I should do a full marathon"
Your message: "Not yet. My friend says I should do a full marathon but that's crazy."
PIP's message just before: "Great goal. Do you have a training plan?"

## 57
PIP would remember about you: a goal: "finish thesis draft by December"
Quote: "My goal is to finish my thesis draft by December."
Your message: "My goal is to finish my thesis draft by December."

## 58
PIP would remember about you: a goal: "finish my thesis draft by December"
Quote: "My goal is to finish my thesis draft by December."
Your message: "My goal is to finish my thesis draft by December."

## 59
PIP would remember about you: a skill: "Big-O notation", at level 0.6 (0 = none, 1 = expert)
Quote: "Could you summarise the Big-O costs of the common data structure operations?"
Your message: "Could you summarise the Big-O costs of the common data structure operations?"
PIP's message just before: "A unit test checks one small piece of code in isolation, usually a single function or class, with anything slow or external replaced by a stand-in. It runs in milliseconds and points straight at the line that broke. An integration test checks that several real parts work together: the code talking to an actual database, two services calling each other, or a request going through the whole web stack. Integration tests are slower and when one fails you have more places to look, but they catch the bugs that unit tests structurally cannot, such as a query that is valid in the test double and wrong against the real schema. A healthy suite has many unit tests for logic, a smaller number of integration tests for the seams where components meet, and a handful of end-to-end tests for the most important user journeys. The danger with heavy mocking is testing the mocks: if every collaborator is faked, the tests can pass while the real system is broken, so at least the critical paths deserve a test against the real thing."

## 60
PIP would remember about you: a project of yours: "Lanternfish" (a budgeting app for student hostels)
Quote: "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels. How should I name the tables for shared expenses?"
Your message: "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels. How should I name the tables for shared expenses?"
PIP's message just before: "For an array, reading by index is constant time, while searching for a value is linear because in the worst case every element is checked. Appending to a dynamic array is constant on average, though an occasional resize copies everything. Inserting at the front of an array is linear, since every element shifts. A linked list flips some of these: inserting at a known node is constant, but finding that node is linear. A hash table gives constant average time for insert, lookup and delete, with a linear worst case when many keys collide. A balanced binary search tree gives logarithmic time for all three and keeps keys in order, which a hash table does not. A binary heap gives constant time to peek at the smallest element and logarithmic time to insert or remove it, which is why priority queues use one. Sorting by comparison costs n log n at best. These numbers describe growth, not speed: a linear scan over a small array often beats a hash lookup in practice because of memory locality."

## 61
PIP would remember about you: a preference: "answer_style" is "concise"
Quote: "I'd like shorter answers by the way."
Your message: "I'd like shorter answers by the way."
PIP's message just before: "It's a hosted LaTeX editor."

## 62
PIP would remember about you: a preference: "main_projects" is "Lanternfish"
Quote: "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels. How should I name the tables for shared expenses?"
Your message: "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels. How should I name the tables for shared expenses?"
PIP's message just before: "TCP gives you a reliable, ordered stream. It sets up a connection with a handshake, numbers every byte, resends anything that is lost, and slows down when the network is congested. The price is latency: a lost packet holds up everything behind it until it is resent. UDP sends independent datagrams with no connection, no ordering and no retransmission; a packet either arrives or it does not, and the application decides what to do about it. TCP suits anything where every byte matters and a short delay is acceptable, such as web pages, file transfers and database connections. UDP suits real-time traffic where a late packet is worse than a missing one: voice and video calls, online games, and DNS lookups that are small enough to simply retry. Modern protocols blur the line. QUIC, which carries HTTP/3, runs over UDP but builds its own reliability and encryption on top, so that one lost packet only delays the stream it belongs to rather than every stream on the connection."

## 63
PIP would remember about you: a preference: "preferred_tools" is "Helix"
Quote: "Actually no, scratch that, I switched to Helix last year."
Your message: "I use Vim for everything. Actually no, scratch that, I switched to Helix last year."

## 64
PIP would remember about you: a preference: "exam_targets" is "AWS Solutions Architect Associate exam"
Quote: "One more thing about me: I want to pass the AWS Solutions Architect Associate exam by March."
Your message: "One more thing about me: I want to pass the AWS Solutions Architect Associate exam by March. What is a sensible way to space out revision?"
PIP's message just before: "TCP gives you a reliable, ordered stream. It sets up a connection with a handshake, numbers every byte, resends anything that is lost, and slows down when the network is congested. The price is latency: a lost packet holds up everything behind it until it is resent. UDP sends independent datagrams with no connection, no ordering and no retransmission; a packet either arrives or it does not, and the application decides what to do about it. TCP suits anything where every byte matters and a short delay is acceptable, such as web pages, file transfers and database connections. UDP suits real-time traffic where a late packet is worse than a missing one: voice and video calls, online games, and DNS lookups that are small enough to simply retry. Modern protocols blur the line. QUIC, which carries HTTP/3, runs over UDP but builds its own reliability and encryption on top, so that one lost packet only delays the stream it belongs to rather than every stream on the connection."

## 65
PIP would remember about you: a preference: "preferred_tools" is "Helix"
Quote: "I switched to Helix last year."
Your message: "I use Vim for everything. Actually no, scratch that, I switched to Helix last year."

## 66
PIP would remember about you: a project of yours: "Pebblebox" (a recipe-sharing app)
Quote: "My cousin's main project is Pebblebox, a recipe-sharing app, and he asked me how to store ingredients."
Your message: "My cousin's main project is Pebblebox, a recipe-sharing app, and he asked me how to store ingredients. Is a separate table the right call?"
PIP's message just before: "Plain nouns that match what people say out loud work best: expense, share, member, settlement. Avoid abbreviations and keep one naming style for every table."

## 67
PIP would remember about you: a goal: "pass by March"
Quote: "One more thing about me: I want to pass the AWS Solutions Architect Associate exam by March."
Your message: "One more thing about me: I want to pass the AWS Solutions Architect Associate exam by March. What is a sensible way to space out revision?"
PIP's message just before: "Both combine work from two branches; they differ in the history they leave. A merge records a new commit with two parents, so the history shows that two lines of work existed and were joined. A rebase replays your commits on top of the other branch as if you had started from its latest commit, which gives a straight line with no merge commit. Rebase is pleasant for a short-lived feature branch that only you have touched: it keeps the main history readable and makes each commit easy to review on its own. The firm rule is never to rebase commits that other people have already pulled, because rebasing rewrites them with new identifiers and everyone else's copy suddenly disagrees with yours. Merge is the safer default for shared branches and for recording that a release branch was folded back in. Many teams combine the two: rebase locally to tidy up, then merge into main through a reviewed pull request, sometimes squashing the branch into one commit."

## 68
PIP would remember about you: a topic you are interested in: "Git workflow"
Quote: "When should someone use git rebase instead of git merge?"
Your message: "When should someone use git rebase instead of git merge?"
PIP's message just before: "They answer two different questions. Cache-Control tells a browser or proxy how long it may reuse a response without asking the server again: max-age is the number of seconds, no-store forbids keeping it at all, and private means only the user's own browser may keep it, not a shared proxy. An ETag is a label for one version of a resource, often a hash of its content. When the cached copy expires, the browser sends the label back in an If-None-Match header. If the content has not changed, the server replies 304 Not Modified with no body, which saves bandwidth even though a round trip still happens. Used together they give fast pages without stale data: long max-age for files whose names change when their content changes, such as bundled scripts with a hash in the file name, and short max-age plus an ETag for pages that change in place. The most common mistake is caching a personalised page in a shared proxy, which is exactly what private exists to prevent."

## 69
PIP would remember about you: how PIP should answer you: "concise"
Quote: "Please keep your answers short from now on, I just want the answer."
Your message: "Please keep your answers short from now on, I just want the answer."

## 70
PIP would remember about you: a preference: "answer_style" is "detailed explanations with worked examples"
Quote: "I really like detailed explanations with worked examples, the short ones lose me."
Your message: "I really like detailed explanations with worked examples, the short ones lose me."

## 71
PIP would remember about you: a topic you are interested in: "concurrency"
Quote: "I keep coming back to this because our sync is broken."
Your message: "Right, I keep coming back to this because our sync is broken."
PIP's message just before: "They are concurrent, so you need a merge rule."

## 72
PIP would remember about you: a preference: "tool_preferred" is "Lucidchart"
Quote: "My supervisor does all her diagrams in Lucidchart and won't touch anything else."
Your message: "My supervisor does all her diagrams in Lucidchart and won't touch anything else. Do diagram tools matter much for a thesis?"
PIP's message just before: "Keep one diagram per scenario, put the actor who starts it on the left, and label every arrow with the message rather than the method name. Number the steps if people will discuss them in a review."

## 73
PIP would remember about you: a skill: "Kotlin", at level 0.0 (0 = none, 1 = expert)
Quote: "I don't write Kotlin at all, it's someone else's code, but thanks."
Your message: "I don't write Kotlin at all, it's someone else's code, but thanks."
PIP's message just before: "Since you write Kotlin every day, you will spot this quickly: the value is read before it is initialised."

## 74
PIP would remember about you: a project of yours: "CLI tools" ()
Quote: "small CLI tools"
Your message: "I'm learning Rust in my spare time, mostly through small CLI tools."

## 75
PIP would remember about you: a preference: "desired_exams" is "Azure Fundamentals exam"
Quote: "My friend wants to pass the Azure Fundamentals exam by March. Is two months enough for an entry-level cloud exam?"
Your message: "My friend wants to pass the Azure Fundamentals exam by March. Is two months enough for an entry-level cloud exam?"
PIP's message just before: "Spaced practice beats cramming: short sessions several times a week, a practice test every two weeks, and the last fortnight on weak areas only."

## 76
PIP would remember about you: a project of yours: "release" (a software release before the database migration)
Quote: "before the next release"
Your message: "I've decided to move our database to Postgres before the next release."

## 77
PIP would remember about you: a skill: "TypeScript", at level 1.0 (0 = none, 1 = expert)
Quote: "I work mostly in TypeScript these days, at work and at home."
Your message: "I work mostly in TypeScript these days, at work and at home."

## 78
PIP would remember about you: a goal: "finish my thesis draft by December"
Quote: "My goal is to finish my thesis draft by December."
Your message: "My goal is to finish my thesis draft by December."

## 79
PIP would remember about you: a goal: "ship the beta"
Quote: "I'm aiming to ship the beta in March."
Your message: "I'm aiming to ship the beta in March. Sorry, I mean May - March was the old plan."

## 80
PIP would remember about you: a preference: "preferred_tools" is "pytest"
Quote: "I always write my tests with pytest, it fits how I think."
Your message: "I always write my tests with pytest, it fits how I think."

## 81
PIP would remember about you: a topic you are interested in: "marathon"
Quote: "My friend says I should do a full marathon but that's crazy."
Your message: "Not yet. My friend says I should do a full marathon but that's crazy."
PIP's message just before: "Great goal. Do you have a training plan?"

## 82
PIP would remember about you: a preference: "exam" is "Azure Fundamentals"
Quote: "My friend wants to pass the Azure Fundamentals exam by March. Is two months enough for an entry-level cloud exam?"
Your message: "My friend wants to pass the Azure Fundamentals exam by March. Is two months enough for an entry-level cloud exam?"
PIP's message just before: "Spaced practice beats cramming: short sessions several times a week, a practice test every two weeks, and the last fortnight on weak areas only."

## 83
PIP would remember about you: a project of yours: "Lanternfish" (a budgeting app for student hostels)
Quote: "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels."
Your message: "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels. How should I name the tables for shared expenses?"
PIP's message just before: "TCP gives you a reliable, ordered stream. It sets up a connection with a handshake, numbers every byte, resends anything that is lost, and slows down when the network is congested. The price is latency: a lost packet holds up everything behind it until it is resent. UDP sends independent datagrams with no connection, no ordering and no retransmission; a packet either arrives or it does not, and the application decides what to do about it. TCP suits anything where every byte matters and a short delay is acceptable, such as web pages, file transfers and database connections. UDP suits real-time traffic where a late packet is worse than a missing one: voice and video calls, online games, and DNS lookups that are small enough to simply retry. Modern protocols blur the line. QUIC, which carries HTTP/3, runs over UDP but builds its own reliability and encryption on top, so that one lost packet only delays the stream it belongs to rather than every stream on the connection."

## 84
PIP would remember about you: a goal: "fixing sync"
Quote: "I keep coming back to this because our sync is broken."
Your message: "Right, I keep coming back to this because our sync is broken."
PIP's message just before: "They are concurrent, so you need a merge rule."

## 85
PIP would remember about you: a project of yours: "Halyard" (a scheduling app for sailing clubs)
Quote: "I'm working on Halyard, a scheduling app for sailing clubs."
Your message: "I'm working on Halyard, a scheduling app for sailing clubs."

## 86
PIP would remember about you: a preference: "preferred_tools" is "Helix"
Quote: "I switched to Helix last year."
Your message: "I use Vim for everything. Actually no, scratch that, I switched to Helix last year."

## 87
PIP would remember about you: a project of yours: "Halyard" (scheduling app for sailing clubs)
Quote: "a scheduling app for sailing clubs"
Your message: "I'm working on Halyard, a scheduling app for sailing clubs."

## 88
PIP would remember about you: a skill: "Unit testing", at level 0.7 (0 = none, 1 = expert)
Quote: "What is the difference between unit tests and integration tests?"
Your message: "What is the difference between unit tests and integration tests?"
PIP's message just before: "Long-running services with many concurrent connections, because it runs on the Erlang virtual machine and its processes are cheap and isolated."

## 89
PIP would remember about you: a preference: "preferred_tools" is "Neovim"
Quote: "I use Neovim for all my coding, it's the only editor I've kept for years."
Your message: "I use Neovim for all my coding, it's the only editor I've kept for years."

## 90
PIP would remember about you: a topic you are interested in: "exam"
Quote: "One more thing about me: I want to pass the AWS Solutions Architect Associate exam by March."
Your message: "One more thing about me: I want to pass the AWS Solutions Architect Associate exam by March. What is a sensible way to space out revision?"
PIP's message just before: "Most languages store decimals as binary floating point numbers, and many simple decimal fractions have no exact binary representation, in the same way that one third has no exact decimal one. The values stored for 0.1 and 0.2 are therefore very slightly off, and their sum lands on a binary value that prints as 0.30000000000000004. The error is tiny but it matters in two places. Comparisons should not test floats for exact equality; check that the difference is smaller than a small tolerance instead. And money should not be stored as floats at all, because rounding errors add up across many transactions and auditors expect exact cents. The usual choices for money are integers counting the smallest unit, such as cents, or a decimal type that stores numbers in base ten. Very large and very small values also lose precision in floating point, so summing many numbers of different sizes is more accurate if the small ones are added first."

## 91
PIP would remember about you: a preference: "exam_goal" is "AWS Solutions Architect Associate exam by March"
Quote: "One more thing about me: I want to pass the AWS Solutions Architect Associate exam by March."
Your message: "One more thing about me: I want to pass the AWS Solutions Architect Associate exam by March. What is a sensible way to space out revision?"
PIP's message just before: "TCP gives you a reliable, ordered stream. It sets up a connection with a handshake, numbers every byte, resends anything that is lost, and slows down when the network is congested. The price is latency: a lost packet holds up everything behind it until it is resent. UDP sends independent datagrams with no connection, no ordering and no retransmission; a packet either arrives or it does not, and the application decides what to do about it. TCP suits anything where every byte matters and a short delay is acceptable, such as web pages, file transfers and database connections. UDP suits real-time traffic where a late packet is worse than a missing one: voice and video calls, online games, and DNS lookups that are small enough to simply retry. Modern protocols blur the line. QUIC, which carries HTTP/3, runs over UDP but builds its own reliability and encryption on top, so that one lost packet only delays the stream it belongs to rather than every stream on the connection."

## 92
PIP would remember about you: a goal: "ship the beta in May"
Quote: "I'm aiming to ship the beta in March. Sorry, I mean May - March was the old plan."
Your message: "I'm aiming to ship the beta in March. Sorry, I mean May - March was the old plan."

## 93
PIP would remember about you: a project of yours: "Lanternfish" (a budgeting app for student hostels)
Quote: "my main project this term is Lanternfish, a budgeting app for student hostels."
Your message: "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels. How should I name the tables for shared expenses?"
PIP's message just before: "A B-tree keeps keys sorted in wide, shallow nodes. Each node holds many keys and pointers to children, so a lookup starts at the root, compares the key with the few values in that node, and follows exactly one pointer down. Because every node is wide, even a table with millions of rows is usually only three or four levels deep, which means three or four page reads instead of scanning every row. Range queries are cheap too: once the first matching key is found, the leaves are linked, so the database walks along them in order. The cost is on writes. Every insert or update to an indexed column must also update the tree, and occasionally split a full node. That is why indexing every column is a bad idea: reads on the indexed columns get faster while every write gets slower, and the indexes take disk space. A good rule is to index the columns that appear in frequent WHERE clauses and joins, check the query plan to confirm the index is used, and drop indexes nothing reads."

## 94
PIP would remember about you: a skill: "Go", at level 1.0 (0 = none, 1 = expert)
Quote: "I've written Go professionally for four years."
Your message: "Quick background: I'm a backend developer and I've written Go professionally for four years."

## 95
PIP would remember about you: a skill: "Elixir", at level 0.5 (0 = none, 1 = expert)
Quote: "If I ever had a free summer I might look at Elixir, but honestly that is not going to happen. What is it actually good at?"
Your message: "If I ever had a free summer I might look at Elixir, but honestly that is not going to happen. What is it actually good at?"
PIP's message just before: "Usually yes: an ingredient table plus a join table holding the quantity and unit, so the same ingredient can appear in many recipes."

## 96
PIP would remember about you: a skill: "Python", at level 0.9 (0 = none, 1 = expert)
Quote: "I've been writing Python professionally for six years now."
Your message: "I've been writing Python professionally for six years now."

## 97
PIP would remember about you: a preference: "Notepad++" is "plain editor"
Quote: "My flatmate swears by Notepad++ for everything and keeps telling me to switch. Is a plain editor ever enough for a real project?"
Your message: "My flatmate swears by Notepad++ for everything and keeps telling me to switch. Is a plain editor ever enough for a real project?"
PIP's message just before: "Not much. Examiners care that a diagram is readable and consistent, and any tool that exports clean vector images is fine."

## 98
PIP would remember about you: a topic you are interested in: "HTTP headers"
Quote: "What do the Cache-Control and ETag headers actually do in HTTP?"
Your message: "What do the Cache-Control and ETag headers actually do in HTTP?"
PIP's message just before: "Long-running services with many concurrent connections, because it runs on the Erlang virtual machine and its processes are cheap and isolated."

## 99
PIP would remember about you: a goal: "ship the beta in May"
Quote: "I'm aiming to ship the beta in March. Sorry, I mean May - March was the old plan."
Your message: "I'm aiming to ship the beta in March. Sorry, I mean May - March was the old plan."

## 100
PIP would remember about you: a skill: "Java", at level 0.5 (0 = none, 1 = expert)
Quote: "I used to love Java back in school, but not anymore."
Your message: "I used to love Java back in school, but not anymore."

## 101
PIP would remember about you: a skill: "Kotlin", at level 0.9 (0 = none, 1 = expert)
Quote: "I don't write Kotlin at all, it's someone else's code, but thanks."
Your message: "I don't write Kotlin at all, it's someone else's code, but thanks."
PIP's message just before: "Since you write Kotlin every day, you will spot this quickly: the value is read before it is initialised."

## 102
PIP would remember about you: a topic you are interested in: "Swift"
Quote: "I might learn Swift someday, not sure yet."
Your message: "I might learn Swift someday, not sure yet."

## 103
PIP would remember about you: a topic you are interested in: "sync"
Quote: "Right, I keep coming back to this because our sync is broken."
Your message: "Right, I keep coming back to this because our sync is broken."
PIP's message just before: "They are concurrent, so you need a merge rule."

## 104
PIP would remember about you: a skill: "Python", at level 0.9 (0 = none, 1 = expert)
Quote: "How do I reverse a list in Python?"
Your message: "How do I reverse a list in Python?"

## 105
PIP would remember about you: a skill: "Go", at level 1.0 (0 = none, 1 = expert)
Quote: "I've written Go professionally for four years."
Your message: "Quick background: I'm a backend developer and I've written Go professionally for four years."

## 106
PIP would remember about you: a skill: "Elixir", at level 0.0 (0 = none, 1 = expert)
Quote: "What if I rewrote the whole backend in Elixir?"
Your message: "What if I rewrote the whole backend in Elixir?"

## 107
PIP would remember about you: a goal: "running a half marathon"
Quote: "I've decided to run a half marathon in April."
Your message: "I've decided to run a half marathon in April."

## 108
PIP would remember about you: a project of yours: "None" (None)
Quote: "Good, I'll stay put."
Your message: "Good, I'll stay put."
PIP's message just before: "For one VPS, probably not."

## 109
PIP would remember about you: a skill: "Python", at level 0.8 (0 = none, 1 = expert)
Quote: "I do all my diagrams in Excalidraw these days, it's the only drawing tool I actually open."
Your message: "Quick aside before the next question: I do all my diagrams in Excalidraw these days, it's the only drawing tool I actually open. Anyway, what makes a good sequence diagram?"
PIP's message just before: "For an array, reading by index is constant time, while searching for a value is linear because in the worst case every element is checked. Appending to a dynamic array is constant on average, though an occasional resize copies everything. Inserting at the front of an array is linear, since every element shifts. A linked list flips some of these: inserting at a known node is constant, but finding that node is linear. A hash table gives constant average time for insert, lookup and delete, with a linear worst case when many keys collide. A balanced binary search tree gives logarithmic time for all three and keeps keys in order, which a hash table does not. A binary heap gives constant time to peek at the smallest element and logarithmic time to insert or remove it, which is why priority queues use one. Sorting by comparison costs n log n at best. These numbers describe growth, not speed: a linear scan over a small array often beats a hash lookup in practice because of memory locality."

## 110
PIP would remember about you: a skill: "Node", at level 0.8 (0 = none, 1 = expert)
Quote: "Mostly plain Node."
Your message: "Mostly plain Node."
PIP's message just before: "Any framework in particular?"

## 111
PIP would remember about you: a preference: "preferred_tools" is "Docker Compose"
Quote: "I deploy everything with Docker Compose on a small VPS."
Your message: "I deploy everything with Docker Compose on a small VPS."

## 112
PIP would remember about you: a skill: "Vim", at level 0.9 (0 = none, 1 = expert)
Quote: "I use Vim for everything."
Your message: "I use Vim for everything. Actually no, scratch that, I switched to Helix last year."

## 113
PIP would remember about you: a goal: "run a half marathon in April"
Quote: "I've decided to run a half marathon in April."
Your message: "I've decided to run a half marathon in April."

## 114
PIP would remember about you: a project of yours: "Lanternfish" (a budgeting app for student hostels)
Quote: "my main project this term is Lanternfish, a budgeting app for student hostels"
Your message: "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels. How should I name the tables for shared expenses?"
PIP's message just before: "A B-tree keeps keys sorted in wide, shallow nodes. Each node holds many keys and pointers to children, so a lookup starts at the root, compares the key with the few values in that node, and follows exactly one pointer down. Because every node is wide, even a table with millions of rows is usually only three or four levels deep, which means three or four page reads instead of scanning every row. Range queries are cheap too: once the first matching key is found, the leaves are linked, so the database walks along them in order. The cost is on writes. Every insert or update to an indexed column must also update the tree, and occasionally split a full node. That is why indexing every column is a bad idea: reads on the indexed columns get faster while every write gets slower, and the indexes take disk space. A good rule is to index the columns that appear in frequent WHERE clauses and joins, check the query plan to confirm the index is used, and drop indexes nothing reads."

## 115
PIP would remember about you: a skill: "backend services", at level 1.0 (0 = none, 1 = expert)
Quote: "Mostly backend services."
Your message: "Mostly backend services."
PIP's message just before: "That's a lot of experience. What do you mostly build?"

## 116
PIP would remember about you: a preference: "answer_style" is "detailed"
Quote: "I really like detailed explanations with worked examples, the short ones lose me."
Your message: "I really like detailed explanations with worked examples, the short ones lose me."
