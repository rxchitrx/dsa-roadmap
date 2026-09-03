"""The first-time learner runway before the main DSA curriculum.

The sequence is a product-shaped interpretation of the source-backed guidance in
``docs/START_HERE.md``. It is intentionally finite and observable: two weeks can
build a launchpad, but cannot replace a full Python or discrete-mathematics course.
"""


START_HERE_SOURCES = {
    "python-tutorial": {
        "title": "Python Tutorial",
        "publisher": "Python Software Foundation",
        "url": "https://docs.python.org/3/tutorial/",
        "kind": "source",
    },
    "python-data-structures": {
        "title": "Python Data Structures",
        "publisher": "Python Software Foundation",
        "url": "https://docs.python.org/3/tutorial/datastructures.html",
        "kind": "source",
    },
    "python-control-flow": {
        "title": "More Control Flow Tools",
        "publisher": "Python Software Foundation",
        "url": "https://docs.python.org/3/tutorial/controlflow.html",
        "kind": "source",
    },
    "python-errors": {
        "title": "Errors and Exceptions",
        "publisher": "Python Software Foundation",
        "url": "https://docs.python.org/3/tutorial/errors.html",
        "kind": "source",
    },
    "mit-6006-syllabus": {
        "title": "MIT 6.006 Introduction to Algorithms syllabus",
        "publisher": "MIT OpenCourseWare",
        "url": "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/pages/syllabus/",
        "kind": "source",
    },
    "mit-6006-resources": {
        "title": "MIT 6.006 lecture and resource index",
        "publisher": "MIT OpenCourseWare",
        "url": "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/download/",
        "kind": "source",
    },
    "mit-6042": {
        "title": "MIT 6.042J Mathematics for Computer Science",
        "publisher": "MIT OpenCourseWare",
        "url": "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-spring-2015/",
        "kind": "source",
    },
    "mit-6042-notes": {
        "title": "MIT 6.042J lecture notes",
        "publisher": "MIT OpenCourseWare",
        "url": "https://ocw.mit.edu/courses/6-042j-mathematics-for-computer-science-fall-2005/pages/lecture-notes/",
        "kind": "source",
    },
    "karpicke-blunt": {
        "title": "Retrieval practice produces more learning than elaborative studying",
        "publisher": "Karpicke & Blunt, Science",
        "url": "https://pubmed.ncbi.nlm.nih.gov/21252317/",
        "kind": "source",
    },
    "cepeda-spacing": {
        "title": "Distributed practice in verbal recall tasks",
        "publisher": "Cepeda et al., Psychological Bulletin",
        "url": "https://pubmed.ncbi.nlm.nih.gov/16719566/",
        "kind": "source",
    },
    "fsrs-algorithm": {
        "title": "The FSRS algorithm",
        "publisher": "Open Spaced Repetition",
        "url": "https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm",
        "kind": "source",
    },
}


def _day(*, number, title, objective, minutes, study, exercises, readiness,
         source_keys=(), heuristic_note=""):
    return {
        "number": number,
        "title": title,
        "objective": objective,
        "minutes": minutes,
        "study": study,
        "exercises": exercises,
        "readiness": readiness,
        "source_keys": list(source_keys),
        "heuristic_note": heuristic_note,
    }


START_HERE_DAYS = [
    _day(
        number=1,
        title="Baseline and a tiny Python loop",
        objective="Find your starting point and make the edit-run-observe loop feel normal.",
        minutes=75,
        study=[
            "Read the Python tutorial sections on the interpreter, numbers, strings, and lists.",
            "Set up one folder with a Python file and a short notes file. Keep the setup boring and repeatable.",
        ],
        exercises=[
            "Write a function that returns the largest value in a non-empty list.",
            "Before running it, predict the output for [4, 1, 9] and [7]. Then test an empty-list decision explicitly.",
        ],
        readiness="You can run a file, call a function, read its output, and record one question without copying a solution.",
        source_keys=("python-tutorial",),
        heuristic_note="The baseline and 75-minute budget are product choices; the Python topics follow the official tutorial.",
    ),
    _day(
        number=2,
        title="Control flow, functions, and prediction",
        objective="Trace Python control flow before you execute it.",
        minutes=90,
        study=[
            "Review if/elif/else, for, while, range, defining functions, return values, and local variables.",
            "Write a one-sentence contract for every function: input, output, and assumptions.",
        ],
        exercises=[
            "Implement count_even(nums), reverse_words(text), and clamp(value, low, high).",
            "Predict three loop outputs on paper, including one zero-iteration loop, then run them.",
        ],
        readiness="You can explain why each loop stops, what a function returns on every path, and the difference between a value and an index.",
        source_keys=("python-control-flow", "python-tutorial"),
        heuristic_note="Three tiny functions are deliberately small implementation reps, not a prescribed textbook exercise set.",
    ),
    _day(
        number=3,
        title="Lists, dictionaries, sets, and mutation",
        objective="Choose the right built-in structure and avoid accidental aliasing.",
        minutes=90,
        study=[
            "Review list methods, list comprehensions, tuples, sets, and dictionaries.",
            "For each operation you use, write whether it scans, indexes, copies, or looks up.",
        ],
        exercises=[
            "Predict the result of alias = values and copy = values[:], then mutate both deliberately.",
            "Implement first_unique(nums) with a set and frequency_count(text) with a dictionary.",
        ],
        readiness="You can choose list vs set vs dict, explain mutation vs shallow copy, and state the likely cost of lookup, membership, and slicing.",
        source_keys=("python-data-structures", "mit-6006-resources"),
        heuristic_note="The exact cost checklist is a learning heuristic; verify operation assumptions against the course cost-model material when needed.",
    ),
    _day(
        number=4,
        title="Debugging, tracebacks, and assertions",
        objective="Treat a failure as evidence instead of guessing at code changes.",
        minutes=75,
        study=[
            "Review syntax errors, exceptions, traceback reading, and assert statements.",
            "Practice tracing one failing input from the error line back to the violated assumption.",
        ],
        exercises=[
            "Take yesterday's functions and add assertions for input and output assumptions.",
            "Create one off-by-one bug and one wrong-type bug, then diagnose each without looking up a fix first.",
        ],
        readiness="Given a failing test, you can name the observed input, the first incorrect state, and the smallest correction to try.",
        source_keys=("python-errors", "python-control-flow"),
        heuristic_note="The diagnose-before-edit ritual is a product habit designed to create useful attempt history.",
    ),
    _day(
        number=5,
        title="Problem decomposition and Big-O",
        objective="Turn a prompt into a contract, a baseline, and a resource estimate.",
        minutes=100,
        study=[
            "Read the MIT algorithms prerequisite guidance and the first algorithmic-thinking material.",
            "Review O(1), O(log n), O(n), O(n log n), and O(n²) as growth descriptions, not stopwatch promises.",
        ],
        exercises=[
            "For Two Sum, write input/output, constraints you would ask for, brute force, hash-based improvement, and both costs.",
            "Rank five snippets by growth and justify the dominant term in one sentence each.",
        ],
        readiness="Before coding, you can state the bottleneck, a baseline, an improved idea, and time plus auxiliary-space complexity.",
        source_keys=("mit-6006-syllabus", "mit-6006-resources"),
        heuristic_note="The named Big-O set and exercise format are a compact runway, not a claim that complexity is mastered in one day.",
    ),
    _day(
        number=6,
        title="Invariants and loop correctness",
        objective="Make the meaning of a running variable explicit and test boundary cases.",
        minutes=90,
        study=[
            "Review loop invariants, initialization, preservation, and termination.",
            "Use a small table to record the state after each iteration instead of relying on intuition.",
        ],
        exercises=[
            "Write the invariant for running maximum, palindrome two-pointers, and binary search's remaining range.",
            "Implement one of them and test empty, singleton, duplicate, and boundary inputs.",
        ],
        readiness="You can complete: ‘after iteration i, ___ is true,’ and use it to justify why the final answer is correct.",
        source_keys=("mit-6006-syllabus", "mit-6042-notes"),
        heuristic_note="The three-invariant set is chosen to bridge the starter path into the existing curriculum.",
    ),
    _day(
        number=7,
        title="Week-one retrieval and a small implementation",
        objective="Prove what survived the first week without rereading everything.",
        minutes=120,
        study=[
            "Close your notes. Reconstruct the Python structure/cost checklist, the problem-solving template, and one invariant from memory.",
            "Only after attempting recall, compare with your notes and mark gaps for next week.",
        ],
        exercises=[
            "Implement a small Stack class with push, pop, peek, and is_empty plus at least five assertions.",
            "Write a short README or notes entry explaining one design choice and one failure you fixed.",
        ],
        readiness="You can rebuild a tiny tested abstraction and explain one trade-off without reopening the lesson first.",
        source_keys=("karpicke-blunt", "cepeda-spacing", "python-data-structures"),
        heuristic_note="The Saturday-style consolidation block and five assertions are app heuristics informed by retrieval practice.",
    ),
    _day(
        number=8,
        title="Recursion and the call stack",
        objective="Write recursion with a contract, a base case, and measurable progress.",
        minutes=90,
        study=[
            "Review recursive decomposition, base cases, call frames, stack depth, and the cost of copying slices.",
            "Trace calls on paper before running them; then convert one recursive solution to iteration.",
        ],
        exercises=[
            "Implement factorial, sum_to_n, and reverse_string recursively with explicit base cases.",
            "Draw the frames for factorial(4) and identify the return order.",
        ],
        readiness="For a recursive function, you can point to the smaller input, base case, return combination, and maximum call-stack depth.",
        source_keys=("mit-6006-resources", "mit-6042-notes", "python-control-flow"),
        heuristic_note="Three tiny recursive functions provide practice volume; they are not a completeness claim about recursion.",
    ),
    _day(
        number=9,
        title="Sets, logic, and functions as discrete foundations",
        objective="Read the notation that appears in algorithm statements and proofs.",
        minutes=90,
        study=[
            "Review sets, subsets, Cartesian products, functions, relations, predicates, and quantifiers.",
            "Translate ‘for every,’ ‘there exists,’ and ‘if and only if’ into plain language examples.",
        ],
        exercises=[
            "Represent a small relation as pairs and decide whether it is a function.",
            "Write the logical negation of three algorithm requirements without changing their meaning.",
        ],
        readiness="You can explain the domain and codomain of a function and negate a quantified statement correctly on a small example.",
        source_keys=("mit-6042", "mit-6042-notes"),
        heuristic_note="The subset is intentionally light; MIT 6.042 is a full course, not a two-day checklist.",
    ),
    _day(
        number=10,
        title="Induction, recurrence, and invariants",
        objective="Connect recursive code and repeated process reasoning to a proof shape.",
        minutes=90,
        study=[
            "Review base case, inductive hypothesis, and inductive step; compare induction with a loop invariant.",
            "Write a simple recurrence for a recursive routine and identify what the recurrence counts.",
        ],
        exercises=[
            "Prove by induction that 1 + 2 + ... + n = n(n+1)/2.",
            "Give a short correctness argument for your recursive sum or an iterative running total.",
        ],
        readiness="You can separate the base case from the step and explain why the smaller-case assumption is legal.",
        source_keys=("mit-6042", "mit-6042-notes", "mit-6006-syllabus"),
        heuristic_note="The proof targets are deliberately elementary readiness checks, not formal proof-course requirements.",
    ),
    _day(
        number=11,
        title="Implementation habit: build, test, explain",
        objective="Create a repeatable small loop for implementing data structures and algorithms.",
        minutes=120,
        study=[
            "Review the existing app's lesson shape: intuition, example, complexity, traps, guided practice, checkpoint.",
            "Choose one tiny structure—queue, frequency counter, or fixed-size window—and write its contract before coding.",
        ],
        exercises=[
            "Implement the structure from a blank file, add normal and edge-case tests, and keep the first failing run in your notes.",
            "Rewrite the explanation in your own words with one invariant and one complexity statement.",
        ],
        readiness="You have one tested implementation, one recorded failure/fix, and a one-paragraph explanation you can reproduce.",
        source_keys=("python-data-structures", "mit-6006-syllabus"),
        heuristic_note="The blank-file → test → explain sequence is a product habit that makes progress observable.",
    ),
    _day(
        number=12,
        title="Transfer: two beginner array problems",
        objective="Use the runway on unfamiliar problem statements without pattern-matching blindly.",
        minutes=110,
        study=[
            "Review the contract, baseline, invariant, edge cases, and complexity template from memory.",
            "Pick two approachable array/string Problems from the app; do not read editorials before the first attempt.",
        ],
        exercises=[
            "Spend up to 25 minutes per Problem: clarify, predict, implement, test, and record the first wrong idea.",
            "For each, write one alternative approach and why the chosen one fits the constraints.",
        ],
        readiness="You can complete two honest attempts with tests and an explanation, even if one still needs a review rather than a perfect score.",
        source_keys=("mit-6006-syllabus", "karpicke-blunt"),
        heuristic_note="Two Problems and the timebox are calibration heuristics; a wrong answer with useful evidence is still progress.",
    ),
    _day(
        number=13,
        title="Mini assessment and mistake analysis",
        objective="Measure independent performance and turn mistakes into next actions.",
        minutes=120,
        study=[
            "Take a closed-notes 60-minute assessment: one easy array/hash problem and one approachable medium if ready.",
            "Use the remaining time to analyse every item, including solved ones: understanding, correctness, complexity, and communication.",
        ],
        exercises=[
            "Label each mistake as reading, decomposition, invariant, implementation, complexity, or testing.",
            "Write one repair action for the largest recurring category and schedule a revisit.",
        ],
        readiness="You can name the first failure point and the next corrective exercise instead of only recording pass/fail.",
        source_keys=("karpicke-blunt", "mit-6006-syllabus"),
        heuristic_note="The 60-minute assessment and labels are app heuristics modeled on the product's later assessment workflow.",
    ),
    _day(
        number=14,
        title="Readiness review and launch the main roadmap",
        objective="Decide what to start, what to repeat, and what evidence to carry forward.",
        minutes=90,
        study=[
            "Re-solve one Day 5–13 exercise from memory and revisit the spaced items that were hardest to retrieve.",
            "Read the Algorithmic Foundations topic overview and choose the first main concept: Problem Solving and Cost Models.",
        ],
        exercises=[
            "Complete the readiness checklist: Python structures, cost estimate, contract, invariant, recursion trace, debugging, and tested implementation.",
            "Write a next-week plan with one concept, two new Problems, one revisit, and one small implementation outcome.",
        ],
        readiness="Most checks are independently demonstrated. If one is weak, repeat that day; do not wait for a mythical perfect score.",
        source_keys=("mit-6006-syllabus", "mit-6042", "cepeda-spacing", "fsrs-algorithm"),
        heuristic_note="The ‘most checks’ launch rule and next-week plan are product decisions; the sources support readiness areas and spaced retrieval, not this threshold.",
    ),
]


START_HERE_READINESS_CHECKS = [
    "I can use lists, dictionaries, sets, functions, loops, and assertions without copying a template.",
    "I can explain the likely cost of indexing, membership, lookup, sorting, slicing, and a nested loop.",
    "I can turn a prompt into input/output, constraints, a baseline, an invariant, and a complexity estimate.",
    "I can read a traceback, locate the first incorrect state, and test a small correction.",
    "I can trace a recursive function and identify its base case, progress, and stack depth.",
    "I can use simple set/logic/induction language to explain an algorithm's claim.",
    "I have one small implementation with tests, a recorded failure/fix, and a plain-language explanation.",
    "I know which day to repeat and what to do next; I am not treating two weeks as total mastery.",
]
