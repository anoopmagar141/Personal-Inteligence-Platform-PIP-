"""
Build the V-2 part (a) long-chat cases: made-up chats of about 1,400, 2,700 and 4,800 words.

Nothing here is a real chat or about a real person. The filler is general study and programming
Q&A in which the user says nothing about themselves; every statement about the user, or about
someone close to them, is one of the nine planted exchanges below, each labelled.

Planted, per chat (the same nine in every chat, so length, position and profile age are the only
things that change):
  three TRUE facts about the user                     F1 tool, F2 project, F3 goal
  three trick statements                              T1 someone else's tool, T2 a hypothetical,
                                                      T3 the assistant asserting something false
  three NEAR-MISSES: a true fact's sentence shape,    N1 the supervisor's tool, N2 a cousin's
  with a different entity that is not the user's      project, N3 a friend's exam goal

Positions: the nine sit in three blocks of three (F_i, N_i, T_i together, so a near-miss sits
next to the fact it imitates). One block near the start, one in the middle, one near the end.
Three rotations put every block at every position once (a Latin square), so a position effect is
not a fact-type effect.

Profile ages: 7, 21 and 63 days, which the Constitution reads as weeks 1, 3 and 9 (evidence needed
1, 2 and 3; constitution_enforcer.py), the ages the plan's #19 bar uses.

Labels follow backend/tests/observer_cases.py: a "learn" spec is matched by any keyword in a row
of one of its tables; an "avoid" spec likewise, over every table the harness reads, so a trick
statement or near-miss counts if it reaches any belief table at all. Extra keys "position" and
"kind" are carried through to the results.

Run from the repo root; writes long_chat_cases.json next to this file. Deterministic.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

ALL_TABLES = [
    "identity", "skill_memory", "preference_memory", "goal_memory", "interaction_style",
    "active_projects", "topic_interests", "preferred_tools", "document_access_patterns", "decision_log",
]

# (user, assistant) pairs. General questions only: no "I use", no "my project", no names of
# tools, products or exams that the planted labels look for.
FILLER = [
    ("Can you explain how a B-tree index makes lookups faster in a database?",
     "A B-tree keeps keys sorted in wide, shallow nodes. Each node holds many keys and pointers to "
     "children, so a lookup starts at the root, compares the key with the few values in that node, and "
     "follows exactly one pointer down. Because every node is wide, even a table with millions of rows is "
     "usually only three or four levels deep, which means three or four page reads instead of scanning "
     "every row. Range queries are cheap too: once the first matching key is found, the leaves are linked, "
     "so the database walks along them in order. The cost is on writes. Every insert or update to an "
     "indexed column must also update the tree, and occasionally split a full node. That is why indexing "
     "every column is a bad idea: reads on the indexed columns get faster while every write gets slower, "
     "and the indexes take disk space. A good rule is to index the columns that appear in frequent WHERE "
     "clauses and joins, check the query plan to confirm the index is used, and drop indexes nothing reads."),
    ("What do the Cache-Control and ETag headers actually do in HTTP?",
     "They answer two different questions. Cache-Control tells a browser or proxy how long it may reuse a "
     "response without asking the server again: max-age is the number of seconds, no-store forbids keeping "
     "it at all, and private means only the user's own browser may keep it, not a shared proxy. An ETag is "
     "a label for one version of a resource, often a hash of its content. When the cached copy expires, the "
     "browser sends the label back in an If-None-Match header. If the content has not changed, the server "
     "replies 304 Not Modified with no body, which saves bandwidth even though a round trip still happens. "
     "Used together they give fast pages without stale data: long max-age for files whose names change "
     "when their content changes, such as bundled scripts with a hash in the file name, and short max-age "
     "plus an ETag for pages that change in place. The most common mistake is caching a personalised page "
     "in a shared proxy, which is exactly what private exists to prevent."),
    ("When should someone use git rebase instead of git merge?",
     "Both combine work from two branches; they differ in the history they leave. A merge records a new "
     "commit with two parents, so the history shows that two lines of work existed and were joined. A "
     "rebase replays your commits on top of the other branch as if you had started from its latest commit, "
     "which gives a straight line with no merge commit. Rebase is pleasant for a short-lived feature branch "
     "that only you have touched: it keeps the main history readable and makes each commit easy to review "
     "on its own. The firm rule is never to rebase commits that other people have already pulled, because "
     "rebasing rewrites them with new identifiers and everyone else's copy suddenly disagrees with yours. "
     "Merge is the safer default for shared branches and for recording that a release branch was folded "
     "back in. Many teams combine the two: rebase locally to tidy up, then merge into main through a "
     "reviewed pull request, sometimes squashing the branch into one commit."),
    ("What is the difference between unit tests and integration tests?",
     "A unit test checks one small piece of code in isolation, usually a single function or class, with "
     "anything slow or external replaced by a stand-in. It runs in milliseconds and points straight at the "
     "line that broke. An integration test checks that several real parts work together: the code talking "
     "to an actual database, two services calling each other, or a request going through the whole web "
     "stack. Integration tests are slower and when one fails you have more places to look, but they catch "
     "the bugs that unit tests structurally cannot, such as a query that is valid in the test double and "
     "wrong against the real schema. A healthy suite has many unit tests for logic, a smaller number of "
     "integration tests for the seams where components meet, and a handful of end-to-end tests for the most "
     "important user journeys. The danger with heavy mocking is testing the mocks: if every collaborator is "
     "faked, the tests can pass while the real system is broken, so at least the critical paths deserve a "
     "test against the real thing."),
    ("Could you summarise the Big-O costs of the common data structure operations?",
     "For an array, reading by index is constant time, while searching for a value is linear because in "
     "the worst case every element is checked. Appending to a dynamic array is constant on average, though "
     "an occasional resize copies everything. Inserting at the front of an array is linear, since every "
     "element shifts. A linked list flips some of these: inserting at a known node is constant, but finding "
     "that node is linear. A hash table gives constant average time for insert, lookup and delete, with a "
     "linear worst case when many keys collide. A balanced binary search tree gives logarithmic time for "
     "all three and keeps keys in order, which a hash table does not. A binary heap gives constant time to "
     "peek at the smallest element and logarithmic time to insert or remove it, which is why priority "
     "queues use one. Sorting by comparison costs n log n at best. These numbers describe growth, not speed: "
     "a linear scan over a small array often beats a hash lookup in practice because of memory locality."),
    ("How do TCP and UDP differ, and when would each be the better choice?",
     "TCP gives you a reliable, ordered stream. It sets up a connection with a handshake, numbers every "
     "byte, resends anything that is lost, and slows down when the network is congested. The price is "
     "latency: a lost packet holds up everything behind it until it is resent. UDP sends independent "
     "datagrams with no connection, no ordering and no retransmission; a packet either arrives or it does "
     "not, and the application decides what to do about it. TCP suits anything where every byte matters "
     "and a short delay is acceptable, such as web pages, file transfers and database connections. UDP "
     "suits real-time traffic where a late packet is worse than a missing one: voice and video calls, "
     "online games, and DNS lookups that are small enough to simply retry. Modern protocols blur the line. "
     "QUIC, which carries HTTP/3, runs over UDP but builds its own reliability and encryption on top, so "
     "that one lost packet only delays the stream it belongs to rather than every stream on the connection."),
    ("How does garbage collection work in languages that manage memory automatically?",
     "The collector's job is to find objects the program can no longer reach and reuse their memory. Most "
     "collectors start from roots, such as global variables and the local variables on each thread's stack, "
     "and follow every reference to mark what is still reachable; everything unmarked is garbage. Many "
     "runtimes are generational because most objects die young: new objects go into a small young area "
     "that is collected often and cheaply, and the few that survive several collections are promoted to an "
     "old area that is collected rarely. Some collectors stop the whole program while they work, which "
     "shows up as pauses; others do most of the work concurrently with the program at the cost of extra "
     "bookkeeping. Garbage collection removes whole classes of bugs, such as freeing memory twice, but it "
     "does not prevent leaks: an object that is still referenced from a forgotten cache or a listener list "
     "is reachable, so it is never collected even though the program will never use it again."),
    ("What are the trade-offs between REST and GraphQL for an API?",
     "A REST API exposes resources at fixed URLs and uses HTTP methods to act on them. It is simple, works "
     "with ordinary HTTP caching, and every endpoint is easy to reason about on its own. Its weak points "
     "are over-fetching, where an endpoint returns far more fields than a screen needs, and under-fetching, "
     "where one screen needs several requests. GraphQL exposes a single endpoint and a typed schema, and the "
     "client asks for exactly the fields it wants, nested across related objects, in one request. That "
     "suits apps with many different screens built by separate teams. The costs move to the server: one "
     "query can be expensive to resolve, so you need limits on depth and cost, and naive resolvers produce "
     "the classic N plus one query problem against the database. Caching is also harder because every "
     "request is a POST to the same URL. For a small project with a few clients, REST is usually enough; "
     "GraphQL pays off when the number of clients and the variety of data they need keep growing."),
    ("What makes a good commit message?",
     "A good commit message lets someone who was not there understand why the change was made, months "
     "later, from the log alone. The first line is a short summary in the imperative mood, such as Fix "
     "rounding in invoice totals, kept under about fifty characters so it reads well in one-line views. "
     "After a blank line, the body explains the reason: what was wrong, how it showed up, and why this "
     "change fixes it rather than another one that was considered. The diff already shows what changed, so "
     "repeating it line by line adds nothing; the reasoning is the part that is otherwise lost. Mention the "
     "evidence when there is some, such as the test that failed before the change or the error message a "
     "user saw. Keep one logical change per commit, so that reverting it or bisecting through history to "
     "find a regression stays possible. Messages like fix stuff or wip are cheap to write and expensive to "
     "read, because the next person has to reconstruct the reasoning from the code."),
    ("What exactly is a race condition?",
     "A race condition is a bug whose outcome depends on the timing of operations that run at the same "
     "time. The classic example is two threads incrementing the same counter. Each one reads the value, "
     "adds one and writes it back; if both read before either writes, one increment is lost, and the final "
     "count is wrong only sometimes, depending on how the scheduler happened to interleave them. That "
     "intermittency is what makes races hard: the test passes a hundred times and fails on the next run, "
     "or only on a busier machine. Races are not limited to threads. Two web requests updating the same "
     "database row, or a program checking that a file exists and then opening it while another process "
     "deletes it in between, are races too. The usual remedies are making the read and the write a single "
     "atomic step, protecting the shared state with a lock, letting the database enforce the rule with a "
     "constraint or a transaction, or avoiding shared mutable state altogether by passing messages."),
    ("Could you walk through database normalisation and the first three normal forms?",
     "Normalisation organises tables so each fact is stored once, which stops updates from leaving copies "
     "that disagree. First normal form asks that every column hold a single value: no lists of phone "
     "numbers squeezed into one field, and no repeating groups of columns such as phone1, phone2 and "
     "phone3. Second normal form applies to tables with a composite key and asks that every other column "
     "depend on the whole key, not on part of it; a course name stored in an enrolment table keyed by "
     "student and course depends only on the course, so it belongs in a course table. Third normal form "
     "asks that columns depend on the key and nothing else, so a city stored next to a postcode, where the "
     "city follows from the postcode, moves into its own table. The practical test is to ask where you "
     "would have to change something if a fact changed. If the answer is several rows, the design invites "
     "inconsistency. Reporting databases sometimes denormalise on purpose to make reads faster."),
    ("How does DNS turn a domain name into an address?",
     "When a program asks for a name, the operating system first checks its own cache and then asks a "
     "recursive resolver, usually run by the network provider or a public service. If the resolver has no "
     "cached answer, it starts at the top. It asks a root server, which does not know the address but "
     "knows who is responsible for the top-level domain, such as the servers for org. The resolver asks "
     "one of those, which points it at the name servers for the specific domain, and those finally return "
     "the address record. Every answer carries a time to live, and every layer caches it for that long, "
     "which is why most lookups never leave the local network and why changing a record can take a while "
     "to be seen everywhere. Besides plain address records there are records for mail servers, aliases "
     "and text used to prove ownership of a domain. Because classic DNS is unencrypted, newer variants "
     "send the queries over TLS or HTTPS so that the network in between cannot read or alter them."),
    ("When is recursion a better fit than iteration?",
     "Recursion fits problems that are defined in terms of smaller versions of themselves, where the "
     "recursive version mirrors the structure of the data. Walking a tree, parsing nested expressions, "
     "generating permutations and divide-and-conquer algorithms such as merge sort read naturally as a "
     "function that handles one level and calls itself for the rest. Iteration fits straight sequences: "
     "summing a list or processing lines in a file is clearer as a loop. The practical limits of recursion "
     "are the call stack, since each call takes stack space and a deep enough input overflows it, and in "
     "some languages the overhead of the calls themselves. Some compilers turn a call in tail position "
     "into a jump, which removes the stack cost, but many popular languages do not guarantee it. Any "
     "recursive algorithm can be rewritten with an explicit stack, which is the usual fix when inputs can "
     "be deeply nested. A good habit is to write the clearest version first and change it only when the "
     "input sizes show it is needed."),
    ("At a high level, what roles are involved in an OAuth login flow?",
     "There are four. The resource owner is the person whose data is involved. The client is the "
     "application that wants access on that person's behalf. The authorization server is the service that "
     "authenticates the person and asks whether they agree to grant the access. The resource server holds "
     "the data and accepts or refuses requests based on the token it is shown. In the common flow for web "
     "and mobile apps, the client sends the person to the authorization server, the person signs in there "
     "and approves a set of scopes, and the authorization server redirects back with a short-lived code. "
     "The client exchanges that code for an access token, using a verifier it generated at the start so "
     "that an intercepted code is useless to anyone else. The important property is that the client never "
     "sees the person's password, and the access is limited to the approved scopes and can be revoked "
     "without changing the password. Tokens should be short-lived, with a refresh token to obtain new ones."),
    ("Why do long-running programs sometimes leak memory, and how are leaks usually found?",
     "Memory leaks in long-running programs are usually not memory that the runtime lost track of, but "
     "memory the program is still holding on to without meaning to. Common causes are caches that grow "
     "without any eviction rule, event listeners that are registered and never removed, collections that "
     "accumulate one entry per request, and closures that capture a large object they only needed briefly. "
     "The symptom is memory use that climbs steadily under a constant workload instead of levelling off. "
     "The standard way to find the cause is to take two heap snapshots some time apart under the same load "
     "and compare them, looking for object types whose count keeps rising, and then following the "
     "references from those objects back to whatever is keeping them alive. Fixes are usually small once "
     "the culprit is known: give the cache a size limit or a time to live, unregister listeners when their "
     "owner is closed, and avoid storing per-request data in places that outlive the request."),
    ("What does a lookahead do in a regular expression?",
     "A lookahead checks that some pattern follows the current position without consuming it, so the match "
     "itself does not include those characters. A positive lookahead, written with a question mark and an "
     "equals sign inside parentheses, succeeds if the pattern is there; a negative lookahead, with an "
     "exclamation mark instead, succeeds if it is not. A typical use is password rules: a pattern can start "
     "with several lookaheads that each assert the string contains a digit, an upper-case letter and so on, "
     "and then match the whole string, because each lookahead looks ahead from the start without moving "
     "forward. Another use is matching a word only when it is not followed by something, such as a number "
     "not followed by a percent sign. Lookbehinds do the same in the other direction, though some engines "
     "only allow fixed-length patterns inside them. Lookarounds are powerful but make patterns hard to "
     "read, so a short comment or a named group next to them saves the next reader a lot of time."),
    ("What is a hash collision and why does it matter?",
     "A hash function maps inputs of any size to a fixed-size value, so different inputs must sometimes "
     "map to the same value; that is a collision. In a hash table, collisions are normal and handled "
     "either by keeping a small list of entries per bucket or by probing for the next free slot. They only "
     "become a problem when there are many of them, because lookups then degrade from constant time "
     "toward a linear search. That can happen with a poor hash function or deliberately, when an attacker "
     "chooses keys that collide, which is why many languages randomise their string hashing per process. "
     "For cryptographic hash functions the bar is far higher: it must be infeasible to find any two inputs "
     "with the same hash, because signatures and integrity checks rely on a hash standing in for the whole "
     "document. Older functions such as MD5 and SHA-1 failed that test and should not be used for "
     "security, though they are still fine as quick checksums against accidental corruption."),
    ("How should a literature review in a final-year report usually be structured?",
     "A literature review is an argument, not a list of summaries. It should show what is already known "
     "about the problem, where the existing work disagrees or stops, and why that gap justifies the "
     "project. A common structure groups sources by theme or by approach rather than one paragraph per "
     "paper: for example, one section on existing systems, one on the techniques they use, and one on how "
     "they have been evaluated. Each section compares the sources, points out their limitations, and ends "
     "with what that means for the work that follows. Recent and well-cited sources carry more weight, and "
     "primary sources are better than someone else's summary of them. A short closing section should state "
     "the gap plainly and connect it to the aims of the project, so the reader sees why the design choices "
     "later in the report were made. Keeping a table of sources with their method, findings and "
     "weaknesses while reading makes the writing much faster."),
    ("Is the Pomodoro technique a good way to schedule study time?",
     "For many people it works well, mostly because it lowers the barrier to starting. The classic form is "
     "twenty-five minutes of focused work, a five-minute break, and a longer break after four rounds. The "
     "fixed interval makes a large task feel smaller, the breaks limit fatigue, and counting rounds gives a "
     "rough measure of effort spent. It suits tasks that can be split into chunks, such as revision, "
     "reading or working through exercises. It suits deep work less well: writing or debugging sometimes "
     "needs an hour or more to get into, and a timer that interrupts at the wrong moment costs more than it "
     "saves, so many people stretch the interval to fifty minutes. The underlying ideas matter more than "
     "the exact numbers: decide the task before starting, remove distractions during the interval, take "
     "real breaks away from the screen, and review at the end of the day what was actually done."),
    ("What is the difference between a process and a thread?",
     "A process is a running program with its own address space: its own memory, open files and other "
     "resources, isolated from other processes by the operating system. A thread is a path of execution "
     "inside a process, and all the threads of one process share its memory. That sharing is the key "
     "difference. Threads can exchange data simply by reading and writing the same variables, which is fast "
     "but makes races and deadlocks possible, so shared data needs locks or other synchronisation. "
     "Processes must communicate through pipes, sockets or shared memory set up on purpose, which is "
     "slower but means a crash in one does not corrupt the other. Creating a process is also more "
     "expensive than creating a thread. In some language runtimes a global interpreter lock stops threads "
     "from running code in parallel, so programs there use multiple processes for CPU-heavy work and "
     "threads mainly for waiting on input and output."),
    ("How does a browser decide that an HTTPS certificate is valid?",
     "When the connection starts, the server sends its certificate, which states the domain names it is "
     "valid for, a validity period, and the server's public key, all signed by a certificate authority, "
     "usually through one or more intermediate certificates. The browser checks that the name in the "
     "address bar matches one of the names in the certificate, that the current date is inside the "
     "validity period, and that each certificate in the chain is signed by the next one up until it "
     "reaches a root that the operating system or browser already trusts. It may also check whether the "
     "certificate has been revoked. Finally, during the handshake the server proves it holds the private "
     "key matching the public key in the certificate, which stops anyone from simply replaying a copied "
     "certificate. If any step fails, the browser shows a warning, which is why clicking through those "
     "warnings defeats the purpose: the encryption still works, but you no longer know who is on the "
     "other end."),
    ("What do people mean by technical debt?",
     "Technical debt is the future cost of a shortcut taken now. Like financial debt, it is not always "
     "bad: shipping a quick version to learn whether anyone wants a feature can be the right call, as long "
     "as the shortcut is known and paid back later. The interest is the extra effort every later change "
     "costs because of the shortcut, such as duplicated logic that must be fixed in several places, "
     "missing tests that make every change risky, or a design that no longer fits what the system does. "
     "Debt becomes dangerous when it is invisible or never repaid, because the interest compounds until "
     "small changes take days. Practical habits help: record the shortcut where the next person will see "
     "it, such as a ticket or a comment explaining what the proper version would be, leave each part of "
     "the code a little cleaner than you found it, and set aside regular time to pay down the debt that "
     "slows the team most, rather than waiting for a rewrite."),
    ("Why does adding 0.1 and 0.2 not give exactly 0.3 in most languages?",
     "Most languages store decimals as binary floating point numbers, and many simple decimal fractions "
     "have no exact binary representation, in the same way that one third has no exact decimal one. The "
     "values stored for 0.1 and 0.2 are therefore very slightly off, and their sum lands on a binary value "
     "that prints as 0.30000000000000004. The error is tiny but it matters in two places. Comparisons "
     "should not test floats for exact equality; check that the difference is smaller than a small "
     "tolerance instead. And money should not be stored as floats at all, because rounding errors add up "
     "across many transactions and auditors expect exact cents. The usual choices for money are integers "
     "counting the smallest unit, such as cents, or a decimal type that stores numbers in base ten. Very "
     "large and very small values also lose precision in floating point, so summing many numbers of "
     "different sizes is more accurate if the small ones are added first."),
    ("How does a load balancer decide where to send each request?",
     "A load balancer sits in front of several servers and spreads incoming requests across them, so that "
     "no single server is overwhelmed and one can fail without taking the service down. The simplest "
     "strategy is round robin, sending each request to the next server in turn. Least connections sends "
     "each request to the server currently handling the fewest, which copes better when requests vary a "
     "lot in cost. Hash-based strategies send requests with the same key, such as the same client address "
     "or session, to the same server, which helps when servers keep per-user state in memory. Weights let "
     "a more powerful server take a larger share. Whatever the strategy, the balancer also runs health "
     "checks and stops sending traffic to a server that fails them. Layer four balancers route by address "
     "and port only, while layer seven balancers read the HTTP request and can route by path or header, "
     "terminate TLS, and retry a failed request on another server."),
]

# One block per index: the true fact, its near-miss, then a trick statement.
BLOCKS = [
    {
        "fact": ("F1", "Quick aside before the next question: I do all my diagrams in Excalidraw these days, it's "
                       "the only drawing tool I actually open. Anyway, what makes a good sequence diagram?",
                 "Keep one diagram per scenario, put the actor who starts it on the left, and label every arrow "
                 "with the message rather than the method name. Number the steps if people will discuss them in "
                 "a review."),
        "fact_spec": {"tables": ["preference_memory", "preferred_tools", "topic_interests", "skill_memory"],
                      "keywords": ["excalidraw"]},
        "near": ("N1", "My supervisor does all her diagrams in Lucidchart and won't touch anything else. Do "
                       "diagram tools matter much for a thesis?",
                 "Not much. Examiners care that a diagram is readable and consistent, and any tool that exports "
                 "clean vector images is fine."),
        "near_keywords": ["lucidchart"],
        "trap": ("T1", "My flatmate swears by Notepad++ for everything and keeps telling me to switch. Is a "
                       "plain editor ever enough for a real project?",
                 "For small scripts, yes. Once a project has many files, search across files, refactoring and a "
                 "debugger start to matter more than how fast the editor opens."),
        "trap_keywords": ["notepad"],
    },
    {
        "fact": ("F2", "Context for the next bit: my main project this term is Lanternfish, a budgeting app for "
                       "student hostels. How should I name the tables for shared expenses?",
                 "Plain nouns that match what people say out loud work best: expense, share, member, settlement. "
                 "Avoid abbreviations and keep one naming style for every table."),
        "fact_spec": {"tables": ["active_projects", "goal_memory"], "keywords": ["lanternfish"]},
        "near": ("N2", "My cousin's main project is Pebblebox, a recipe-sharing app, and he asked me how to store "
                       "ingredients. Is a separate table the right call?",
                 "Usually yes: an ingredient table plus a join table holding the quantity and unit, so the same "
                 "ingredient can appear in many recipes."),
        "near_keywords": ["pebblebox"],
        "trap": ("T2", "If I ever had a free summer I might look at Elixir, but honestly that is not going to "
                       "happen. What is it actually good at?",
                 "Long-running services with many concurrent connections, because it runs on the Erlang virtual "
                 "machine and its processes are cheap and isolated."),
        "trap_keywords": ["elixir"],
    },
    {
        "fact": ("F3", "One more thing about me: I want to pass the AWS Solutions Architect Associate exam by "
                       "March. What is a sensible way to space out revision?",
                 "Spaced practice beats cramming: short sessions several times a week, a practice test every two "
                 "weeks, and the last fortnight on weak areas only."),
        "fact_spec": {"tables": ["goal_memory", "active_projects"], "keywords": ["solutions architect"]},
        "near": ("N3", "My friend wants to pass the Azure Fundamentals exam by March. Is two months enough for an "
                       "entry-level cloud exam?",
                 "For an entry-level exam, two months of steady study is usually plenty, especially with the "
                 "free practice questions."),
        "near_keywords": ["azure"],
        # The assistant asserts something false about the user; the user corrects it. A third line, so
        # the trap is the assistant's claim, not a user statement.
        "trap": ("T3", "Can you look at this null pointer error from the Android build?",
                 "Since you write Kotlin every day, you will spot this quickly: the value is read before it is "
                 "initialised.",
                 "I don't write Kotlin at all, it's someone else's code, but thanks."),
        "trap_keywords": ["kotlin"],
    },
]

# How many filler exchanges each length uses, and where the three blocks go (insert before the filler
# index given). Chosen so "start" is inside the first ~15% of words and "end" inside the last ~15%.
LENGTHS = {
    "S": {"filler": 5, "insert_before": [1, 3, 5]},
    "M": {"filler": 12, "insert_before": [1, 6, 11]},
    "L": {"filler": 24, "insert_before": [1, 12, 23]},
}
ROTATIONS = [[0, 1, 2], [1, 2, 0], [2, 0, 1]]  # block placed at start, middle, end
POSITIONS = ["start", "middle", "end"]
AGES_DAYS = [7, 21, 63]


def _block_lines(block):
    lines = []
    for key in ("fact", "near", "trap"):
        turn = block[key]
        lines.append(f"User: {turn[1]}")
        lines.append(f"Assistant: {turn[2]}")
        if len(turn) > 3:
            lines.append(f"User: {turn[3]}")
    return lines


def _check_filler():
    banned = ["excalidraw", "lanternfish", "solutions architect", "lucidchart", "pebblebox", "azure",
              "notepad", "elixir", "kotlin", " aws", " i use", "my project", " i'm ", "i am "]
    for user, assistant in FILLER:
        text = f" {user.lower()} {assistant.lower()} "
        hits = [b for b in banned if b in text]
        assert not hits, (user, hits)


def build():
    _check_filler()
    cases = []
    for length, spec in LENGTHS.items():
        filler = FILLER[: spec["filler"]]
        for r, rotation in enumerate(ROTATIONS):
            lines, learn, avoid = [], [], []
            placed = dict(zip(spec["insert_before"], rotation))
            position_of = {block: POSITIONS[i] for i, block in enumerate(rotation)}
            for i in range(len(filler) + 1):
                if i in placed:
                    lines += _block_lines(BLOCKS[placed[i]])
                if i < len(filler):
                    lines += [f"User: {filler[i][0]}", f"Assistant: {filler[i][1]}"]
            for b, block in enumerate(BLOCKS):
                pos = position_of[b]
                learn.append({**block["fact_spec"], "position": pos, "kind": "fact", "id": block["fact"][0]})
                avoid.append({"tables": ALL_TABLES, "keywords": block["near_keywords"], "position": pos,
                              "kind": "near_miss", "id": block["near"][0]})
                avoid.append({"tables": ALL_TABLES, "keywords": block["trap_keywords"], "position": pos,
                              "kind": "trap", "id": block["trap"][0]})
            transcript = "\n".join(lines) + "\n"
            for days in AGES_DAYS:
                cases.append({
                    "id": f"long_{length}_r{r}_d{days}",
                    "category": "long",
                    "length": length,
                    "rotation": r,
                    "profile_age_days": days,
                    "words": len(transcript.split()),
                    "transcript": transcript,
                    "learn": learn,
                    "avoid": avoid,
                })
    return cases


if __name__ == "__main__":
    cases = build()
    with open(os.path.join(HERE, "long_chat_cases.json"), "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=1)
    for c in cases[::3]:
        print(c["id"][:-4], c["words"], "words")
    print(len(cases), "cases written")
