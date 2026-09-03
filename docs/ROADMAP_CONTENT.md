
# DSA Roadmap Content Pack

Status: source-backed curriculum synthesis for the DSA Roadmap Learning Workspace
Updated: 2026-09-03
Audience: one beginner-to-interview software-engineering candidate using Python
Parent product specification: [PRD issue #1](https://github.com/rxchitrx/dsa-roadmap/issues/1)

## Executive answer

The roadmap is an ordered, prerequisite-aware progression through 12 Topics and 59 original Concepts. It is intentionally broader than a list of coding patterns:

1. Algorithmic foundations: problem contracts, Python cost model, asymptotic analysis, invariants, and recursion.
2. Arrays and strings: indexed data, scans, prefix techniques, grids, and parsing.
3. Hashing and lookup: maps, sets, frequency, canonicalization, and prefix-state lookup.
4. Two pointers and sliding window: shrinking, partitioning, fixed windows, and variable windows.
5. Linear data structures: linked lists, fast/slow pointers, stacks, queues, deques, and LRU design.
6. Searching, sorting, and selection: binary-search boundaries, answer-space search, merge sort, and quickselect.
7. Intervals, greedy, and heaps: normalization, proofs, priority queues, top-k, and sweep lines.
8. Trees and tries: traversals, recursive DFS, BST ranges, tree paths, and prefix indexes.
9. Graphs and union-find: representations, BFS, DFS/topological order, components, shortest paths, and MSTs.
10. Recursion and backtracking: decision trees, subsets, combinations, and sound pruning.
11. Dynamic programming: state design, one-dimensional/grid DP, subsequence/knapsack, tree/interval DP, and reconstruction.
12. Advanced interview patterns: divide-and-conquer, bits/math, Fenwick/segment trees, string matching, and flow/matching.

This ordering is a synthesis, not a universal academic law. ACM/IEEE curriculum guidance explicitly says that topic groupings and ordering are not prescriptive, while the official MIT and Princeton algorithm courses provide strong coverage signals for the selected foundations, data structures, sorting, searching, graphs, strings, and dynamic programming areas. See the [ACM Algorithms and Complexity guidance](https://csed.acm.org/wp-content/uploads/2022/02/CS2013-Version.htm), [MIT 6.006 syllabus](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/pages/syllabus/), and [Princeton Algorithms booksite](https://algs4.cs.princeton.edu/).

Load the complete manifest with:

~~~text
uv run python manage.py seed_curriculum --full
~~~

The no-argument command remains a three-lesson compatibility seed for the repository's existing fixtures. It is not the complete roadmap.

## Phase progression

| Phase | Topics | Learner outcome | Exit evidence |
| --- | --- | --- | --- |
| 0. Foundations | Algorithmic Foundations | Translate prompts, estimate cost, state invariants, and write/debug Python deliberately. | Explain a brute-force baseline, a scalable alternative, and its invariant/complexity. |
| 1. Linear patterns | Arrays & Strings; Hashing & Lookup; Two Pointers & Sliding Window; Linear Data Structures | Solve common sequence, lookup, window, and pointer problems without pattern guessing. | Independently solve unseen easy and medium variants, including edge cases. |
| 2. Ordered choice | Searching, Sorting & Selection; Intervals, Greedy & Heaps | Exploit order, monotonic predicates, local-choice proofs, and priority frontiers. | Choose between sorting, binary search, greedy, and heap from constraints and prove the choice. |
| 3. Hierarchical structure | Trees & Tries | Traverse, aggregate, validate, and search recursive structures. | Implement traversal/DFS/BST/trie patterns from a blank file and explain height-sensitive cost. |
| 4. Graph reasoning | Graphs & Union-Find | Model relationships and choose BFS, DFS, union-find, shortest path, or MST correctly. | Explain the graph representation, invariant, and algorithm precondition before coding. |
| 5. Exponential search with structure | Recursion & Backtracking; Dynamic Programming | Enumerate when needed, prune safely, and replace repeated subproblems with state. | Define state/transition or decision state and show why no valid branch is lost. |
| 6. Selective depth | Advanced Interview Patterns | Handle less frequent but high-value interview variants and know when not to over-engineer. | Solve with a stated guarantee and identify when a simpler standard-library tool is better. |

The phases are not a promise that every learner needs equal time in every phase. A weak prerequisite should reopen an earlier Concept instead of forcing forward progression.

## Ordered Topic to Concept roadmap

The manifest at [curriculum/roadmap_content.py](/Volumes/NewVolume/Projects/DSA_Roadmap/curriculum/roadmap_content.py) is the source of truth for lesson text, stable slugs, local order, and prerequisite edges.

### 1. Algorithmic Foundations

1. Problem Solving and Cost Models — problem-solving-and-cost-models
2. Python for DSA — python-for-dsa
3. Complexity and Asymptotic Analysis — complexity-and-asymptotic-analysis
4. Invariants and Correctness — invariants-and-correctness
5. Recursion and the Call Stack — recursion-and-call-stack

### 2. Arrays & Strings

1. Array Fundamentals — array-fundamentals
2. Array Traversal and Accumulators — array-traversal
3. Prefix Sums and Difference Arrays — prefix-sums-and-difference-arrays
4. Matrix and Grid Traversal — matrix-and-grid-traversal
5. String Fundamentals and Parsing — string-fundamentals-and-parsing

### 3. Hashing & Lookup

1. Hash Maps and Sets — hash-maps-and-sets
2. Frequency Counting — frequency-counting
3. Grouping and Canonicalization — grouping-and-canonicalization
4. Prefix and Hash Combinations — prefix-and-hash-combinations

### 4. Two Pointers & Sliding Window

1. Two Pointers — two-pointers
2. Partitioning and Three Pointers — partitioning-and-three-pointers
3. Fixed-Size Sliding Window — fixed-size-sliding-window
4. Variable-Size Sliding Window — variable-size-sliding-window

### 5. Linear Data Structures

1. Linked-List Fundamentals — linked-list-fundamentals
2. Fast and Slow Pointers — fast-and-slow-pointers
3. Stacks and Queues — stacks-and-queues
4. Deque and Monotonic Structures — deque-and-monotonic-structures
5. LRU Cache Design — lru-cache-design

### 6. Searching, Sorting & Selection

1. Binary Search — binary-search
2. Boundary Binary Search — boundary-binary-search
3. Binary Search on the Answer — binary-search-on-answer
4. Merge Sort and Inversion Count — merge-sort-and-inversion-count
5. Quicksort and Quickselect — quicksort-and-quickselect

### 7. Intervals, Greedy & Heaps

1. Interval Normalization — interval-normalization
2. Greedy Choice and Proof — greedy-choice-and-proof
3. Priority Queues and Heaps — priority-queues-and-heaps
4. Top-K and Streaming — top-k-and-streaming
5. Sweep-Line Events — sweep-line-events

### 8. Trees & Tries

1. Tree Representation and Traversals — tree-representation-and-traversals
2. Recursive Tree DFS — recursive-tree-dfs
3. Binary Search Trees — binary-search-trees
4. Tree Paths and Ancestors — tree-paths-and-ancestors
5. Trie Prefix Search — trie-prefix-search

### 9. Graphs & Union-Find

1. Graph Representation — graph-representation
2. BFS and Unweighted Shortest Paths — bfs-shortest-unweighted
3. DFS Components and Topological Order — dfs-components-and-topological-order
4. Union-Find — union-find
5. Dijkstra and Minimum Spanning Trees — dijkstra-and-minimum-spanning-trees
6. Grid Graphs and 0-1 BFS — grid-graphs-and-01bfs

### 10. Recursion & Backtracking

1. Backtracking Template — backtracking-template
2. Subsets and Permutations — subsets-and-permutations
3. Combinations and Partitions — combinations-and-partitions
4. Constraint Pruning — constraint-pruning

### 11. Dynamic Programming

1. DP State and Transition — dp-state-and-transition
2. One-Dimensional and State-Machine DP — one-dimensional-state-machine-dp
3. Grid DP — grid-dp
4. Subsequence and Knapsack DP — subsequence-and-knapsack-dp
5. Interval and Tree DP — interval-and-tree-dp
6. DP Optimization and Reconstruction — dp-optimization-and-reconstruction

### 12. Advanced Interview Patterns

1. Divide and Conquer — divide-and-conquer
2. Bit Manipulation and Modular Math — bit-manipulation-modular-math
3. Fenwick and Segment Trees — fenwick-and-segment-trees
4. String Matching and Rolling Hash — string-matching-and-rolling-hash
5. Max Flow and Bipartite Matching — max-flow-bipartite-matching

## Concept lesson contract

Every seeded Concept supplies the fields already supported by the current lesson UI:

- Intuition: one mental model, analogy, or invariant boundary.
- Explanation: the mechanism, when it applies, and the precondition that makes it correct.
- Worked example: input, expected output, trace/walkthrough, and a small Python implementation sketch.
- Complexity: time, auxiliary space, and important assumptions such as expected hashing or nonnegative weights.
- Implementation guidance: a repeatable order for translating the idea into code.
- Common traps: likely wrong turns, edge cases, and misleading success signals.
- Guided practice: a short written trace or prediction before execution.
- Checkpoint: a recall prompt that asks for the concept in the learner's own words.

This lesson shape follows the communication emphasis in MIT 6.006: an algorithm answer should include a description, worked example, correctness indication, and complexity analysis. See the [MIT 6.006 Fall 2011 syllabus](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/pages/syllabus/) and the [MIT lecture notes index](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/pages/lecture-notes/).

The content is original project text. External sources are linked for rationale and further study; source pages are not required at runtime.

## Problem-selection rules

These rules are product policy for the learner's catalog and assignments. They are informed by the official course coverage above, but the exact weights are intentionally heuristics until personal data exists.

### New weekday Problems

- Assign two Problems to the weekday solving block from the Concept studied that day.
- Start with one approachable Problem that isolates the pattern, then one transfer Problem with a changed surface form or edge case.
- Early in a Concept, prefer Easy plus Medium. Once the learner has independent evidence, prefer two Medium Problems. Do not force Hard problems as a proxy for mastery.
- Prefer source-specific records with a reliable statement, constraints, examples, and Python function contract.
- Prefer Problems not attempted in the current week and not seen recently. A familiar Problem can be assigned as a deliberate reactivation task, but it must be labeled as review rather than novelty.
- Avoid assigning two Problems that test the same trick with only renamed variables. Vary input shape, output requirement, or constraint.
- Preserve uncertain Concept mappings as warnings. A low-confidence tag can be used for practice but should not silently drive a recommendation or assessment.
- If the eligible pool is sparse, use the nearest eligible Concept and label the fallback. Never pretend a fallback measured current-week learning.

### Review selection

Review is not a second pass through the newest list. Rank candidates in this order:

1. Overdue Problems.
2. Due Problems with a failed or assisted recent recall.
3. Current-week Problems that have not yet had an independent revisit.
4. Older Problems with stale evidence.
5. Stable Problems only when the review block has spare capacity.

The three learner ratings remain:

- Couldn't solve: schedule the earliest repair and require a correction or smaller prerequisite task.
- Solved with help: schedule sooner and record what kind of help was needed.
- Solved independently: allow a longer interval, but require a correct explanation and edge-case check before treating it as strong evidence.

The app can use an FSRS-style local scheduler, but the exact interval is a product choice until enough personal review history exists. FSRS models difficulty, stability, and retrievability; its maintainers also note that optimization becomes more useful with more review data. See the [FSRS algorithm reference](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm) and the [FSRS optimizer review-log schema](https://github.com/open-spaced-repetition/fsrs-optimizer).

### Source and novelty policy

- Source/provider plus external identifier is the stable identity.
- Private accounts, credentials, personal submissions, and solved-status imports are excluded.
- A Problem snapshot used by an Attempt is immutable even if the catalog later changes.
- Novelty is a planning signal, not a moral score. A learner may intentionally revisit a familiar Problem to test recall.
- Problem difficulty is a starting prior, not proof of difficulty for this learner.

## Weekly operating protocol

The routine is a default operating rhythm, not a requirement to study while ill or to convert rest into failure.

### Monday to Friday

Total planned study time: 180 minutes.

1. 20 minutes — re-solve one old Problem from the due queue. Start with a blank page and predict the pattern before opening code.
2. 30 minutes — learn one Concept lesson. Write the invariant, precondition, and one edge case.
3. 50 minutes — solve one or two new Problems. The first isolates the pattern; the second tests transfer when time permits.
4. 20 minutes — study/rewrite the solution. Compare the learner's approach with the clean version, then write the complexity and one alternative.
5. 30 minutes — Python implementation or project work. Keep it concrete: implement a data structure, add tests, or improve a small module.
6. 30 minutes — DBMS, OS, CN, or OOP. Rotate subjects rather than touching all four superficially in one day.

The app should preserve partial attempts. An unfinished Problem is not automatically a failure; the evidence is the draft, run history, reflection, and later review outcome.

### Saturday

Suggested order:

1. 5 minutes — read all three prompts and choose a starting order.
2. 90 minutes — timed assessment: one Easy and two Medium Problems by default.
3. At the cutoff — save official in-time result and per-Problem state.
4. Optional continuation — allow overtime for learning and save the final result separately.
5. 30–60 minutes — analyse every Problem, including solved ones.
6. 2 hours — project work, preferably a small vertical improvement with tests.

The application should not compress timed performance and eventual understanding into one score. Report current-week, fallback, cutoff, and overtime results separately.

### Sunday

Suggested order:

1. Re-solve five highest-value older Problems by default. Allow the learner to increase the count for a heavy review week.
2. Revise one CS subject using questions and diagrams, not only rereading.
3. Work on the project and record a visible outcome.
4. Review the week: planned versus actual time, new Problems, reviews, Concepts, assessment, mistakes, and unfinished work.
5. Generate a draft next-week plan from weak evidence and due reviews.
6. Edit and save the plan. Keep one or two buffer blocks for reality.

## Saturday assessment design

Default contract:

- Three Problems in 90 minutes.
- One Easy and two Medium.
- Current-week Concepts first.
- Mostly unseen Problems.
- If the pool is sparse, use older Concepts as fallback and mark each fallback item.
- No duplicate Problem identity in one assessment.
- Preserve prompt snapshot and assignment rationale.
- Allow overtime after recording the official cutoff.
- Record per-Problem status, code snapshot, tests, result, time, and post-assessment analysis.

Recommended selection rationale:

1. Determine Concepts with explicit current-week study evidence.
2. Weight by meaningful practice volume, not merely by a Concept appearing in the plan.
3. Exclude recently solved/seen Problems unless the assessment intentionally tests reactivation.
4. Prefer one accessible confidence check and two transfer Problems.
5. Fill missing slots from older ready Concepts, keeping the fallback category visible.

Mistake analysis is mandatory for every assessment Problem. Use these root-cause labels:

- misunderstanding
- approach error
- implementation bug
- edge-case miss
- complexity issue
- time-management issue

Each analysis records:

- what the learner believed,
- the first point where the reasoning diverged,
- the correction,
- one follow-up action,
- optional review date,
- whether the failure was current-week or fallback evidence.

The score is a diagnostic, not a leaderboard. A cutoff failure with a correct overtime solution means “timed execution needs work; conceptual evidence is stronger,” not simply pass or fail.

## Sunday planning and feedback loop

The generated next-week plan should use evidence in this order:

1. Due and overdue review debt.
2. Concepts with missing or weak/stale checkpoint evidence.
3. Problems with assisted or failed independent reviews.
4. Unfinished work carried once, without multiplying backlog.
5. The next prerequisite-ready Concept.
6. A realistic mix of new Problems, CS revision, Python/project work, and rest.

The learner must be able to edit the generated plan before saving. A plan that is theoretically optimal but impossible to execute is a bad plan.

The weekly summary should show:

- target versus actual minutes,
- completed, partial, skipped, canceled, and rest blocks,
- new Problems attempted and completed,
- reviews due, completed, and overdue,
- Concept checkpoint movement,
- assessment cutoff and overtime results,
- mistake categories and follow-up actions,
- unfinished work and next week's first action.

Avoid points, leaderboards, and competitive streaks. Neutral consistency measures are enough: completion ratio, review debt, independent-recall rate, and median time by difficulty.

## Mastery evidence

“Accepted” means the current execution passed its visible tests. “Mastery candidate” means the learner has evidence that should survive a delayed, changed-context recall. They are separate states.

A Concept or Problem should move toward retained mastery only when most of the following are true:

1. The learner can restate the problem or concept without copying the lesson.
2. The learner can predict a trace or next state before running code.
3. The learner can write the core solution from a blank editor or minimal signature.
4. The learner can explain the invariant, precondition, and complexity.
5. The learner handles normal, boundary, adversarial, and empty inputs.
6. The learner can solve a second Problem with a different surface form.
7. The learner records a short approach, blocker, correction, and takeaway.
8. A delayed review is solved independently, not merely recognized from the old code.
9. The learner can say when the pattern does not apply.

Confidence alone is not enough. Karpicke and Roediger found that repeated testing improved delayed recall while repeated studying alone did not, and also reported that learners' predictions were not reliable substitutes for later performance. Butler found repeated testing improved retention and transfer relative to repeated studying. See [The Critical Importance of Retrieval for Learning](https://doi.org/10.1126/science.1152408), [Repeated testing produces superior transfer](https://pubmed.ncbi.nlm.nih.gov/20804289/), and the [distributed-practice synthesis by Cepeda et al.](https://doi.org/10.1037/0033-2909.132.3.354).

Operational status proposal:

| Status | Minimum evidence |
| --- | --- |
| Unseen | No meaningful attempt or study evidence. |
| Exposed | Lesson read or assisted attempt exists, but no independent evidence. |
| Practicing | At least one deliberate attempt plus a trace, note, or checkpoint. |
| Solved with help | Correct or partial solution required a hint, reference, or substantial assistance. |
| Solved independently | Correct solution under visible/custom tests without solution lookup, with complexity and edge-case explanation. |
| Retained / mastery candidate | Independent solution plus a delayed independent revisit and a transfer Problem. |

These are operational product labels, not validated psychological thresholds. The app should expose the evidence behind the label and allow learner override.

## DBMS / OS / CN / OOP study track

This track is part of the weekly routine but remains planning content, not a first-release tracked domain. The PRD explicitly keeps CS-subject tracking out of the initial product scope.

| Subject | Ordered study progression | Practical evidence |
| --- | --- | --- |
| DBMS | Relational model and keys → SQL select/filter/join/grouping → schema design and normalization → indexes and query plans → transactions and ACID → locking/isolation → recovery/logging → distributed/NoSQL awareness. | Design a small schema, write queries, explain an index choice, and reason through a lost update or recovery case. |
| OS | Processes and system calls → threads/context switches → scheduling → synchronization → deadlock → virtual memory/page tables → file systems → I/O and crash recovery. | Explain a process/thread trace, diagnose a race, translate a virtual address, and describe a file write across failure. |
| CN | Layering and packet model → sockets/DNS/HTTP → IP addressing and routing → reliable transport/TCP → flow/congestion control → TLS/basic security → CDN/distributed service behavior. | Trace a browser request, explain retransmission/RTT, and identify the layer responsible for a failure. |
| OOP | Objects/classes → encapsulation and invariants → composition → inheritance/polymorphism/interfaces → design patterns only when useful → testing/refactoring and concurrency boundaries. | Design a small domain model, defend composition versus inheritance, and write tests around an invariant. |

The subject ordering is anchored in official course material: [MIT 6.830 Database Systems](https://ocw.mit.edu/courses/6-830-database-systems-fall-2010/pages/), [MIT 6.1810 Operating System Engineering](https://ocw.mit.edu/courses/6-1810-operating-system-engineering-fall-2023/pages/syllabus/), [MIT 6.02 packet/routing/transport topics](https://ocw.mit.edu/courses/6-02-introduction-to-eecs-ii-digital-communication-systems-fall-2012/pages/syllabus/), and [MIT 6.005 Software Construction](https://ocw.mit.edu/courses/6-005-software-construction-spring-2016/pages/syllabus/). The OOP terminology is also consistent with [Oracle's OOP concepts guide](https://docs.oracle.com/javase/tutorial/java/concepts/) and [Python's classes documentation](https://docs.python.org/3/tutorial/classes.html).

Do not attempt all four subjects every day. A sustainable rotation is:

- Monday: DBMS
- Tuesday: OS
- Wednesday: CN
- Thursday: OOP
- Friday: weakest subject from the week's evidence
- Sunday: one deeper revision block

## Python progression

The Python track supports DSA and the project:

1. Core syntax: control flow, functions, exceptions, modules, and readable formatting.
2. Data model: lists, tuples, dictionaries, sets, slicing, mutability, aliasing, and iterators.
3. DSA implementation: stacks, queues, linked lists, heaps, trees, graphs, and reusable helpers.
4. Testing/debugging: assertions, pytest, fixtures, small experiments, and failure-first debugging.
5. Practical tooling: virtual environments, dependency boundaries, file I/O, JSON/CSV, logging, and profiling.
6. Project Python: modular design, typed boundaries where useful, persistence, HTTP/web integration, and safe configuration.

The official [Python tutorial](https://docs.python.org/3/tutorial/index.html) covers control flow, data structures, modules, and classes. The roadmap deliberately adds interview cost-model and mutation practice around those language features.

## Project progression

Project work is also a scheduled block rather than first-release application data. Use one small, demonstrable outcome per session:

1. CLI or script with one clear input/output contract.
2. Module boundaries and tests around the core logic.
3. Persistence with a documented schema and migration/backup story.
4. Thin web/API surface over a stable domain service.
5. Observability: structured logs, failure states, and a useful local diagnostic.
6. Quality pass: edge cases, performance measurement, security review, and README demo.
7. Portfolio pass: architecture diagram, trade-offs, known limitations, and a short walkthrough.

Project selection should reinforce the current DSA/CS Concept where possible: a queue-backed worker after queues, an indexed search feature after hashing/search, or a small persistence feature after DBMS/recovery.

## Content and source boundaries

- Source-backed claim: official curricula and primary learning studies support the broad coverage, retrieval emphasis, and need to distinguish delayed transfer from rereading.
- Project synthesis: the exact 12-topic order, 59-concept granularity, two-problem weekday assignment, assessment mix, and mastery labels are product decisions informed by those sources.
- The 20/30/50/20/30/30 routine, 90-minute assessment, five Sunday reviews, and 1/3/7-style early intervals are operational defaults, not universal laws.
- The app's current FSRS-style scheduler should not be described as scientifically optimized for this learner until enough personal review logs exist.
- Official university courses often target a full academic term and include more theory than an interview candidate needs. This pack selects the interview-relevant spine and defers specialist topics unless evidence or goals call for them.
- The roadmap targets general software-engineering interviews. Competitive programming, language-specific certification, systems-specialist interviews, and graduate algorithms theory need separate branches.
- The content is not a substitute for current job-specific preparation. Interview formats vary by company and role.

## Compact source ledger

| Source | Publisher/author | Used for | Limitation or reconciliation |
| --- | --- | --- | --- |
| [CS2013 Algorithms and Complexity](https://csed.acm.org/wp-content/uploads/2022/02/CS2013-Version.htm) | ACM/IEEE | Core algorithm/data-structure coverage; complexity; graph and sorting outcomes. | Explicitly says topic order is not prescriptive, so this roadmap supplies its own learner order. |
| [CS2023 knowledge areas](https://csed.acm.org/knowledge-areas/) | ACM/IEEE/AAAI | Positioning algorithms, data management, networking, OS, and software foundations as related areas. | Curriculum guidance is broader than interview preparation. |
| [MIT 6.006 syllabus](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/pages/syllabus/) | MIT OpenCourseWare | Intro algorithm scope, Python/discrete-math prerequisites, data structures, sorting, graph search, DP. | Academic course assumes prerequisites and has more formal breadth. |
| [MIT 6.006 lecture notes](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/pages/lecture-notes/) | MIT OpenCourseWare | Algorithm communication: example, correctness, and complexity; binary trees, BFS/DFS, Dijkstra. | Used as lesson-quality guidance, not copied lesson text. |
| [Princeton Algorithms booksite](https://algs4.cs.princeton.edu/) and [lecture guidance](https://algs4.cs.princeton.edu/lectures/) | Robert Sedgewick and Kevin Wayne | Fundamentals, sorting, priority queues, searching, graphs, strings, max flow, and regular self-study/problem cadence. | Java-centered material; concepts were rewritten for Python. |
| [Python tutorial](https://docs.python.org/3/tutorial/index.html) and [classes](https://docs.python.org/3/tutorial/classes.html) | Python Software Foundation | Control flow, data structures, modules, classes, objects, and aliasing. | Language reference is not an interview curriculum by itself. |
| [MIT 6.830 Database Systems](https://ocw.mit.edu/courses/6-830-database-systems-fall-2010/pages/) | MIT OpenCourseWare | Relational model, schema design, query processing, indexing, transactions, locking, recovery. | Graduate-level course; track is intentionally a lighter interview spine. |
| [MIT 6.1810 Operating System Engineering](https://ocw.mit.edu/courses/6-1810-operating-system-engineering-fall-2023/pages/syllabus/) | MIT OpenCourseWare | Processes, threads, VM, file systems, interrupts, syscalls, IPC. | Implementation-heavy course; this track emphasizes explainable interview evidence. |
| [MIT 6.02 syllabus](https://ocw.mit.edu/courses/6-02-introduction-to-eecs-ii-digital-communication-systems-fall-2012/pages/syllabus/) and [6.829 notes](https://ocw.mit.edu/courses/6-829-computer-networks-fall-2002/pages/lecture-notes/) | MIT OpenCourseWare | Packet switching, routing, reliable transport, sliding windows, congestion, and network services. | Sources span different course levels and years; current protocol details need later refresh. |
| [MIT 6.005 Software Construction](https://ocw.mit.edu/courses/6-005-software-construction-spring-2016/pages/syllabus/) | MIT OpenCourseWare | Specifications, invariants, testing, ADTs, OOP design, concurrency, and refactoring. | Broader software construction than the compact OOP track. |
| [Oracle OOP concepts](https://docs.oracle.com/javase/tutorial/java/concepts/) | Oracle | Objects, classes, encapsulation, inheritance, interfaces, packages. | Java examples; used for language-neutral vocabulary. |
| [Critical Importance of Retrieval](https://doi.org/10.1126/science.1152408) | Karpicke and Roediger, Science, 2008 | Retrieval practice over repeated studying; limits of confidence predictions. | Foreign-language word learning is not identical to coding; applied as a learning principle. |
| [Repeated testing and transfer](https://pubmed.ncbi.nlm.nih.gov/20804289/) | Butler, Journal of Experimental Psychology, 2010 | Delayed retention and transfer support for repeated testing. | Facts/concepts experiments are not a direct DSA trial. |
| [Distributed practice synthesis](https://doi.org/10.1037/0033-2909.132.3.354) | Cepeda, Pashler, Vul, Wixted, and Rohrer, 2006 | Spacing/distributed-practice rationale. | Does not prescribe this app's exact intervals. |
| [FSRS algorithm](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm) and [optimizer](https://github.com/open-spaced-repetition/fsrs-optimizer) | Open Spaced Repetition community | Difficulty/stability/retrievability model and review-log concepts. | Open-source implementation documentation, not a claim that default parameters are optimal for this learner. |

## Verification notes

- Manifest import and Python compilation passed.
- The manifest contains 12 Topics and 59 Concepts.
- Every prerequisite slug resolves to a manifest Concept.
- The seed command supports the complete roadmap via --full.
- Existing tests were not changed.
- No migrations, feature behavior, GitHub issues, or unrelated app files were changed by this content pass.
