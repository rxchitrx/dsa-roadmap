# Start here: first two weeks

Updated: 2026-09-03  
Audience: a beginner preparing to start the DSA Roadmap in Python

The application now includes a 14-day **Start here** runway at `/curriculum/start-here/`. It is linked from Today and the Curriculum page. The runway is deliberately a launchpad, not a claim that Python, discrete mathematics, or algorithms can be mastered in two weeks.

## Research-backed sequence

The order follows the dependency that shows up in the sources:

1. Python control flow, functions, built-in data structures, mutation, errors, and tracebacks.
2. Algorithmic problem contracts, a brute-force baseline, asymptotic growth, and Python operation costs.
3. Invariants and correctness reasoning before more pattern-heavy problem solving.
4. Recursion, call-stack tracing, and a small implementation habit.
5. A light introduction to sets, logic, functions, induction, and recurrence language.
6. Retrieval, implementation, testing, explanation, and spaced revisit evidence before launch.

MIT's 6.006 syllabus names a firm grasp of Python and a solid discrete-mathematics background as prerequisites, and its newer syllabus describes a prerequisite problem set. This app turns those prerequisites into a finite diagnostic runway; it does not replace the underlying courses.

## Source versus product decision

Sourced guidance is used for the prerequisite areas, the Python topics, the role of invariants/proofs/complexity, and the value of retrieval and spacing. The exact day boundaries, time budgets, exercises, readiness wording, and “repeat a weak day, then launch when evidence is good enough” rule are product heuristics for this single-user app. The sources do not prescribe this exact 14-day schedule or a universal readiness threshold.

The app's existing review scheduler is also a product implementation. Research supports retrieval and distributed practice, while exact intervals and scoring remain personal-data-dependent decisions. The page therefore links to the research without presenting its intervals as scientifically mandatory.

## Source ledger

| Source | Publisher / author | What it supports | Access |
| --- | --- | --- | --- |
| [The Python Tutorial](https://docs.python.org/3/tutorial/) | Python Software Foundation | The beginner sequence for expressions, control flow, functions, and core language fluency. | Official documentation; accessed 2026-09-03 |
| [Data Structures](https://docs.python.org/3/tutorial/datastructures.html) | Python Software Foundation | Lists, tuples, sets, dictionaries, comprehensions, and built-in structure behavior. | Official documentation; accessed 2026-09-03 |
| [More Control Flow Tools](https://docs.python.org/3/tutorial/controlflow.html) | Python Software Foundation | `if`, `for`, `while`, `range`, function definitions, and local scope. | Official documentation; accessed 2026-09-03 |
| [Errors and Exceptions](https://docs.python.org/3/tutorial/errors.html) | Python Software Foundation | Syntax errors, exceptions, traceback reading, and deliberate error handling. | Official documentation; accessed 2026-09-03 |
| [MIT 6.006 syllabus, Spring 2020](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/pages/syllabus/) | MIT OpenCourseWare | Python and discrete mathematics as prerequisites; algorithmic thinking, performance measures, and a prerequisite check. | Official course material; accessed 2026-09-03 |
| [MIT 6.006 resources](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/download/) | MIT OpenCourseWare | Python Cost Model, algorithmic-thinking material, and recursion/tree recitation material used as follow-up study. | Official course material; accessed 2026-09-03 |
| [MIT 6.042J Mathematics for Computer Science](https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-spring-2015/) | MIT OpenCourseWare | Sets, functions, relations, proofs, discrete structures, and probability as CS foundations. | Official course material; accessed 2026-09-03 |
| [MIT 6.042J lecture notes](https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-fall-2005/pages/lecture-notes/) | MIT OpenCourseWare | Propositions, predicate logic, induction, relations, and graph theory as a staged foundations sequence. | Official course material; accessed 2026-09-03 |
| [Retrieval practice produces more learning than elaborative studying](https://pubmed.ncbi.nlm.nih.gov/21252317/) | Jeffrey Karpicke and Janell Blunt, Science (2011) | Retrieval practice as a reason to attempt recall before rereading and to record what was retrievable. | PubMed record for primary study; accessed 2026-09-03 |
| [Distributed practice in verbal recall tasks](https://pubmed.ncbi.nlm.nih.gov/16719566/) | Nicholas Cepeda et al., Psychological Bulletin (2006) | Large review/meta-analysis showing that spacing and retention interval interact; it does not prescribe one fixed interval. | PubMed record for primary review; accessed 2026-09-03 |
| [The FSRS algorithm](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm) | Open Spaced Repetition | Difficulty, stability, retrievability, and rating concepts relevant to future scheduler design. | Official project documentation; accessed 2026-09-03 |

## Limits and follow-up

- The first two weeks do not cover every Python feature, formal proof technique, or data structure prerequisite.
- A learner who cannot yet write small tested functions should extend Days 1–4 rather than rush to problem volume.
- A learner who can already demonstrate the checks can move through the runway quickly and use the saved time on the main Algorithmic Foundations lessons.
- Readiness is evidence of a good next step, not a permanent label. The main roadmap and review loop should reopen foundations when later work exposes a gap.
