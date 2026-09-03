# PRD: DSA Roadmap Learning Workspace

## Problem Statement

The learner wants to build a complete, honest record of their DSA journey instead of keeping disconnected notes, solved-question lists, timers, and revision reminders. Their routine includes learning concepts, solving new Python problems, revisiting older questions, rewriting solutions, taking weekly assessments, analyzing mistakes, and planning the following week.

Existing coding platforms show submission outcomes, but they do not provide a personal learning system that connects the weekly plan, concept understanding, repeated recall, reflections, and long-term progress. A passing submission can still represent memorization, heavy assistance, or a fragile understanding. The learner needs a system that records that distinction and keeps review work actionable.

## Solution

Build a local-first desktop web application for one learner. The application provides a Today command center, an editable DSA weekly routine, a seeded and editable Topic-to-Concept curriculum, a local Python solving workspace, meaningful attempt history, adaptive problem reviews, weekly timed assessments, detailed analytics, and portable backups.

The first usable milestone proves the complete weekly loop with six foundational DSA topics and a representative problem set. The system then expands to a full public LeetCode catalog, broader curriculum content, and additional source adapters.

## User Stories

1. As a learner, I want to see today’s DSA plan immediately, so that I can start the next useful activity without deciding what to do first.
2. As a learner, I want to see today’s due reviews, so that older questions do not disappear from my routine.
3. As a learner, I want to see the current concept recommendation, so that my next learning step reflects my actual progress.
4. As a learner, I want to start any planned block in any order, so that the application fits real study days.
5. As a learner, I want to create an editable Monday-to-Sunday routine, so that the schedule can evolve with my preparation.
6. As a learner, I want weekday blocks for reviews, concept study, new problems, and solution rewriting, so that my intended DSA routine is explicit.
7. As a learner, I want Saturday to contain a timed assessment and mistake analysis, so that each week ends with an objective test.
8. As a learner, I want Sunday to contain a configurable review batch, weekly reflection, and next-week planning, so that the following week starts intentionally.
9. As a learner, I want each planned block to have a target duration, so that I can compare intended effort with actual effort.
10. As a learner, I want to start, pause, resume, and finish a timer, so that the application records time without requiring manual bookkeeping.
11. As a learner, I want to correct a recorded duration, so that interruptions and timer mistakes do not corrupt my history.
12. As a learner, I want to mark a block completed, partial, skipped, or canceled, so that my history remains honest.
13. As a learner, I want an unfinished block to carry forward once, so that missed work remains visible without multiplying into an impossible backlog.
14. As a learner, I want to mark a day or week as rest, so that intentional breaks are not treated as failures.
15. As a learner, I want rest-day work to carry to the next active day, so that planned DSA work is not silently lost.
16. As a learner, I want to browse the problem library by difficulty, source, topic, concept, status, and review state, so that I can understand what is available.
17. As a learner, I want the first release to include a useful foundational DSA taxonomy, so that I can begin immediately.
18. As a learner, I want each broad Topic to contain specific Concepts, so that progress is more precise than a single topic label.
19. As a learner, I want to view and edit prerequisite relationships, so that the roadmap reflects how I learn.
20. As a learner, I want the application to recommend a next Concept from weak performance, prerequisites, coverage, and review evidence, so that my roadmap adapts over time.
21. As a learner, I want the application to auto-assign its recommended Concept while showing why it was selected, so that automation remains understandable.
22. As a learner, I want to override an automatically assigned Concept, so that I retain control over unusual study goals.
23. As a learner, I want each Concept to have a full lesson, so that I can learn directly inside the application.
24. As a learner, I want each lesson to include intuition, examples, implementation patterns, complexity, common traps, guided practice, and a checkpoint, so that concept study is structured.
25. As a learner, I want to add personal explanations and notes to a Concept, so that the curriculum captures my own understanding.
26. As a learner, I want the application to automatically sync the public LeetCode catalog, so that I do not have to enter every problem manually.
27. As a learner, I want catalog synchronization to run at startup without blocking the application, so that I can study while updates are being fetched.
28. As a learner, I want the last successful catalog to remain available offline, so that a network failure does not interrupt my routine.
29. As a learner, I want sync progress, warnings, and failures to be visible, so that I know whether the catalog is current.
30. As a learner, I want every source listing to retain its platform URL and identifier, so that I can trace imported content back to its source.
31. As a learner, I want problems from different platforms to remain separate by default, so that similar titles do not incorrectly combine histories.
32. As a learner, I want imported source tags to map automatically to the DSA taxonomy, so that classification does not become manual data entry.
33. As a learner, I want uncertain tag mappings to be visibly marked, so that I can judge the quality of recommendations and assessments.
34. As a learner, I want changed problem statements to preserve historical snapshots, so that old attempts remain understandable.
35. As a learner, I want to open a problem and read its statement, constraints, examples, and expected Python contract, so that I can solve without leaving the application.
36. As a learner, I want to write Python in an in-app editor, so that solving is part of the learning record.
37. As a learner, I want the editor to autosave drafts, so that a refresh does not erase work in progress.
38. As a learner, I want to run visible examples and my own custom tests, so that I can experiment before treating a solution as complete.
39. As a learner, I want the application to support LeetCode-style Python function problems first, so that the first catalog has one reliable execution contract.
40. As a learner, I want solution code to use only the Python standard library, so that practice remains close to interview constraints.
41. As a learner, I want every meaningful run to save its code snapshot, tests, output, exception, verdict, duration, and limits, so that later analysis has evidence.
42. As a learner, I want a failed run to remain part of the attempt history, so that mistakes are learning data rather than discarded noise.
43. As a learner, I want to write my own explanation and clean solution rewrite after solving, so that I consolidate the pattern instead of only collecting an accepted answer.
44. As a learner, I want to record my approach, blocker, complexity, and takeaway, so that each problem has a concise reflection.
45. As a learner, I want a problem to distinguish passing execution from retained learning, so that one accepted run does not falsely represent mastery.
46. As a learner, I want a completed problem to enter a review schedule, so that the application actively protects long-term recall.
47. As a learner, I want the review scheduler to use my recall outcome, so that difficult problems return sooner and reliable problems spread out.
48. As a learner, I want three quick review choices—could not solve, solved with help, and solved independently—so that review logging is fast enough to use every day.
49. As a learner, I want weekday reviews to prioritize due and overdue problems, so that review debt remains visible.
50. As a learner, I want Sunday to select the highest-value review problems, so that a five-question block focuses on retention rather than arbitrary order.
51. As a learner, I want to increase Sunday’s review count for heavy weeks, so that the routine can match my workload.
52. As a learner, I want weekday new problems to be assigned automatically from the studied Concept, so that I spend less time choosing questions.
53. As a learner, I want two new problems assigned to the weekday solving block, so that the routine has a clear practice target.
54. As a learner, I want incomplete new problems to retain their partial attempts, so that unfinished work is not mistaken for failure without evidence.
55. As a learner, I want Saturday’s assessment to select problems from Concepts explicitly studied that week, so that the test measures the week’s learning.
56. As a learner, I want practice volume to weight assessment selection, so that Concepts with meaningful study receive appropriate representation.
57. As a learner, I want Saturday’s assessment to be mostly unfamiliar problems, so that it measures transfer rather than memorization.
58. As a learner, I want the default assessment to contain three problems in ninety minutes, so that weeks are comparable.
59. As a learner, I want the fixed assessment mix to be one easy problem and two medium problems, so that the test is challenging but realistic.
60. As a learner, I want the app to fill a sparse assessment from older Concepts, so that a light week can still end with a useful test.
61. As a learner, I want current-week and fallback assessment scores reported separately, so that older retrieval does not distort the week’s learning result.
62. As a learner, I want to continue solving after the assessment timer expires, so that I can finish for learning even when I miss the time target.
63. As a learner, I want the application to preserve both cutoff and final overtime results, so that I can distinguish timed performance from eventual understanding.
64. As a learner, I want to analyze every assessment problem, so that no mistake disappears inside one overall score.
65. As a learner, I want to label a mistake as a misunderstanding, approach error, implementation bug, edge-case miss, complexity issue, or time-management issue, so that recurring patterns become visible.
66. As a learner, I want to write a correction and follow-up action for each mistake, so that analysis turns into future practice.
67. As a learner, I want a weekly summary of time, blocks, new problems, reviews, weak Concepts, and assessment results, so that I know what to change next.
68. As a learner, I want detailed charts and breakdowns below the weekly summary, so that I can investigate trends when useful.
69. As a learner, I want neutral consistency metrics without points or leaderboards, so that the product supports discipline without turning study into a game.
70. As a learner, I want the application to generate a draft next-week plan, so that Sunday planning starts from evidence rather than a blank page.
71. As a learner, I want to edit the generated next-week plan before saving it, so that automation remains aligned with my intentions.
72. As a learner, I want to export the complete journey to versioned JSON, so that my history is portable and recoverable.
73. As a learner, I want to export useful summaries to CSV, so that I can inspect or analyze data outside the application.
74. As a learner, I want restore to create a safety export before replacing local data, so that an accidental restore remains recoverable.
75. As a learner, I want the first release to work completely offline after catalog data is cached, so that my core study flow does not depend on network availability.

## Implementation Decisions

- The application is a personal, single-user, local-first desktop web application. It will use Django, HTMX, SQLite, and a small browser-side code editor. The public repository will contain source code and documentation, never personal study data.
- The first usable milestone is a complete weekly loop using six foundational Topics: arrays and strings, hashing, two pointers, sliding window, stacks and queues, and binary search. Broader catalog and curriculum breadth follows through the same interfaces.
- The weekly domain separates planned Study Blocks from actual Work Sessions. A Work Session records duration, timer events, outcome, linked DSA work, and notes. Blocks are flexible in execution order.
- Weekday DSA defaults are a twenty-minute Review block, thirty-minute Concept lesson, fifty-minute block containing two new Problems, and twenty-minute solution study/rewrite block. Saturday defaults to three Problems in ninety minutes. Sunday defaults to five Reviews, weekly review, and editable next-week planning.
- Planned blocks support completed, partial, skipped, canceled, and rest states. An unfinished block carries once to the next active day, then becomes one overdue item. Rest days carry planned work to the next active day without counting the rest date as a miss.
- Topics contain Concepts. Concepts form a seeded, editable prerequisite graph. Graph cycles are invalid. Concept recommendations prioritize weak evidence and unmet prerequisites before uncovered Concepts.
- Concept Learning Status is derived from explicit study activity, linked Problem evidence, review outcomes, confidence, and prerequisite state. The learner may override status when personal judgment differs.
- Each Concept has curated full-lesson content plus editable personal notes. Lesson content is original project content and does not depend on an external page at runtime.
- A Problem is source-specific. A source/provider and external identifier are stable identity fields. Cross-platform records remain separate by default; any future merge must be explicit.
- A Problem retains current content plus versioned source snapshots. Attempts reference the snapshot used at the time, preventing source updates from rewriting historical evidence.
- The LeetCode provider imports the public catalog only. It may use an available public unauthenticated endpoint, but it must not collect credentials, session cookies, private submissions, or account data. The provider is isolated so later sources can be added independently.
- Catalog sync runs on startup when data is stale, but it is non-blocking. The last successful local catalog remains usable during network failure. Sync reports imported, updated, unchanged, skipped, uncertain, and failed records.
- Source tags map automatically to Topic and Concept through a maintained mapping table. Low-confidence mappings remain usable but are visibly warned in the library, recommendation, and assessment surfaces.
- If a problem lacks a reliable Python signature or runnable examples, the provider makes a best-effort estimate, marks it as estimated, and allows the test schema to be edited before execution.
- The first execution contract is LeetCode-style Python function problems. The runner executes standard-library-only solution code against visible examples and learner-defined custom tests. Stdin/stdout platform adapters are later work.
- The Python runner is a deep module behind a stable execution interface. It runs outside the web request process, captures structured results, autosaves the code before execution, and enforces hard timeout, memory, output, temporary-file, and process-isolation ceilings even when learning limits are relaxed.
- An Attempt contains a meaningful solving session. It can contain autosaved drafts, immutable code snapshots, Run results, timer evidence, hints or reference events, and a required short reflection. Keystroke-level replay and natural-language confusion analysis are later work.
- Passing execution and Learning Status are separate. A passing run records an execution outcome; independent successful Reviews advance retention state.
- Problem Reviews use an FSRS-style scheduler. The three learner-facing ratings map internally to Again, Hard, and Good. Scheduler state is local and included in backups. Parameter optimization is deferred until enough personal review history exists.
- Weekday review selection prioritizes due and overdue Problems. Sunday selects five by default, with a user-configurable increase, prioritizing overdue work, current-week Problems, and weak recent evidence.
- New weekday Problem assignment selects two unsolved Problems from the automatically assigned Concept, using difficulty and recency rules. Insufficient pools use a clearly labeled nearest eligible fallback.
- Saturday selection requires explicit Concept study evidence and weights Concepts by related practice. It prefers mostly unseen Problems and uses one easy plus two medium Problems. When the current-week pool is sparse, older Concepts fill the remaining slots and receive a separate score.
- The assessment timer allows overtime. At the configured deadline, the application records a cutoff snapshot and official in-time result while allowing continued solving. The final result records overtime separately.
- Assessment mistake review requires a result, root-cause label, correction note, and optional follow-up Review date for each Problem.
- The Today command center is the primary entry point. The interface is dark throughout with deep ink surfaces and warm amber focus states. It uses focused density rather than generic card grids and keeps planning, solving, reflection, and analytics distinct.
- The first release is desktop-only. Core editor and assessment interactions are optimized for a laptop screen. Basic keyboard and focus behavior is included as part of functional quality, without a separate accessibility workstream.
- There are no reminders, push notifications, email notifications, gamified points, leaderboards, CS-subject tracking, project tracking, private platform sync, or historical backfill in the first release.
- JSON export is the canonical backup format. Restore validates the version, automatically exports current data, then replaces the local dataset only after confirmation. CSV is a secondary analysis export.
- Public hosting is a later phase. A future hosted deployment must replace SQLite with remote persistence and replace the local runner with a stronger sandbox boundary.

### Deep modules

- Schedule Engine: creates dated Study Blocks from the weekly template, applies rest days and carry-forward rules, and records block state transitions.
- Problem Catalog Provider: normalizes source data, performs idempotent sync, stores source snapshots, classifies tags, and emits warnings without mutating personal history.
- Python Execution Runner: accepts a problem execution contract, code, tests, and limits; returns structured output independent of the web layer.
- Review Scheduler: maps DSA recall outcomes to FSRS scheduling state and produces due dates and review previews.
- Concept Recommendation Engine: traverses the prerequisite graph and evidence to recommend and assign the next Concept with an explanation.
- Assessment Selector: chooses current-week and fallback Problems according to concept evidence, novelty, difficulty, and score category.
- Analytics Service: derives weekly adherence, time, problem, review, concept, mistake, and assessment metrics from recorded events.
- Backup/Restore Service: serializes the complete domain, validates versions, creates safety exports, and restores atomically.

## Testing Decisions

- Tests verify observable behavior and stable domain contracts rather than framework internals or private implementation details.
- The Schedule Engine will be tested for weekly generation, flexible order, block state transitions, one-time carry-forward, rest-day carry-forward, local week boundaries, and actual-versus-target duration.
- The Concept Recommendation Engine will be tested for weak-evidence priority, prerequisite ordering, cycle rejection, explicit study eligibility, explanation output, and manual override.
- The Problem Catalog Provider will be tested for idempotent full and incremental sync, source identity, snapshot preservation, tag mapping confidence, incomplete metadata, rate-limit/failure reporting, and offline fallback.
- The Python Execution Runner will be tested with passing code, failing assertions, syntax errors, runtime exceptions, infinite loops, excessive output, memory pressure, forbidden filesystem access, custom tests, autosave-before-run, and structured result capture.
- The Review Scheduler will be tested for all three DSA ratings, due-date updates, forgotten versus independent recall, state persistence, and deterministic backup/restore behavior.
- The Assessment Selector will be tested for current-week concept eligibility, unseen-problem preference, fixed easy-plus-two-medium selection, insufficient pools, fallback labeling, separate scoring, and no duplicate selection.
- Assessment flows will be tested for cutoff snapshots, overtime results, incomplete code, per-problem review completion, root-cause labels, corrections, and follow-up scheduling.
- The Analytics Service will be tested against known event fixtures for planned-versus-actual time, completion states, review debt, concept movement, mistakes, current-week scores, fallback scores, and neutral consistency metrics.
- The Backup/Restore Service will be tested for complete round trips, schema version validation, invalid data rejection, safety export creation, atomic replacement, and preservation of historical snapshots.
- Django integration tests will cover Today loading, autosave, problem workspace interactions, sync status, assessment navigation, Sunday review, plan generation, export, and restore.
- Browser smoke tests will complete one weekday, one failed and successful run, one review, one timed assessment with overtime, one Sunday report, and one backup/restore flow.
- There is no prior application test suite because this repository started empty. Initial tests will establish the product’s external behavior as the project’s testing precedent.

## Out of Scope

- AI-generated explanations of every attempted edit, confusion inference, or automatic root-cause diagnosis.
- Keystroke-level activity replay and live behavioral telemetry.
- Hidden-test judging, remote submissions, or direct submission to LeetCode.
- HackerRank or other source adapters in the first usable milestone.
- Private platform accounts, credentials, session cookies, solved-status synchronization, or personal submission history import.
- Multi-user accounts, collaboration, sharing, social features, or public learner profiles.
- Cloud hosting, remote database synchronization, and mobile-first layouts.
- DBMS, operating systems, computer networks, OOP, project management, and non-DSA study tracking.
- Reminders, email, push notifications, points, badges, streak rewards, and leaderboards.
- Historical journey backfill before the app launch.
- Full arbitrary package installation inside learner solutions.
- Automatic cross-platform problem merging.

## Further Notes

- The repository is intentionally public, but local databases, backups, environment files, credentials, and generated catalog caches must remain ignored.
- The first public repository milestone is a scaffold plus this PRD. Feature work should be delivered as vertical slices that keep the weekly loop runnable.
- The first seeded curriculum should contain enough original content and representative Problems to exercise Concept recommendations, reviews, assessments, and analytics before full catalog synchronization is complete.
- The later attempt-analysis system should consume the meaningful event history already defined here instead of requiring a storage redesign.
