from django.core.management.base import BaseCommand
from django.db import transaction

from curriculum.models import Concept, Topic


SEED_TOPIC = {
    "name": "Arrays & Strings",
    "slug": "arrays-strings",
    "description": (
        "Build reliable array intuition first, then turn that intuition into "
        "repeatable traversal and pointer patterns."
    ),
    "display_order": 1,
}

SEED_CONCEPTS = [
    {
        "name": "Array Fundamentals",
        "slug": "array-fundamentals",
        "order": 1,
        "summary": "Learn how indexed storage gives you fast access and predictable scans.",
        "intuition": (
            "An array is a row of numbered boxes. The index is the address of a box, "
            "so reaching a known position does not require walking through the boxes before it."
        ),
        "explanation": (
            "Arrays are ordered collections accessed by zero-based index. Most DSA solutions "
            "combine direct reads or writes with a left-to-right scan. Before choosing a clever "
            "pattern, identify what each position means, what range is still unprocessed, and "
            "which value must be remembered while the scan moves."
        ),
        "examples": [
            {
                "title": "Find the first repeated value",
                "input": "nums = [4, 7, 2, 7, 9]",
                "output": "7",
                "walkthrough": (
                    "Scan left to right while storing values already seen. The second 7 is "
                    "the first value found in that set."
                ),
                "code": (
                    "seen = set()\n"
                    "for value in nums:\n"
                    "    if value in seen:\n"
                    "        return value\n"
                    "    seen.add(value)"
                ),
            },
            {
                "title": "Reverse an array in place",
                "input": "nums = [1, 2, 3, 4]",
                "output": "[4, 3, 2, 1]",
                "walkthrough": (
                    "Swap the first and last values, then move both indices toward the center."
                ),
                "code": "nums.reverse()",
            },
        ],
        "complexity_notes": (
            "Index access is O(1). A full scan is O(n). Reversing in place uses O(1) extra "
            "space; a separate reversed collection uses O(n) space."
        ),
        "implementation_guidance": (
            "Name the invariant before coding: for example, every index before left has "
            "already been processed. Prefer enumerate when you need both an index and a value, "
            "and test empty and one-element arrays explicitly."
        ),
        "common_traps": (
            "Confusing a value with its index, reading nums[i + 1] at the final index, and "
            "using nums2 = nums when you intended to make a copy."
        ),
        "guided_practice": (
            "Trace a scan on [3, 3, 1] and write down the set after each iteration. Then "
            "predict the result for [], [8], and [2, 1, 2]."
        ),
        "checkpoint": (
            "In one sentence, explain why direct access by index is O(1), and in one sentence "
            "state when a scan must stop before the last index."
        ),
        "prerequisite_slugs": [],
    },
    {
        "name": "Array Traversal",
        "slug": "array-traversal",
        "order": 2,
        "summary": "Turn a scan into a precise invariant that accumulates an answer safely.",
        "intuition": (
            "A traversal is a moving boundary between what you have proved and what you have "
            "not inspected yet. The accumulator summarizes the proved side."
        ),
        "explanation": (
            "Many array problems are the same loop with a different accumulator: a running "
            "maximum, a count, a prefix sum, or the best answer seen so far. Start with a "
            "correct value for the first element when possible, then update the accumulator as "
            "the boundary advances. This keeps the invariant visible and handles negative values "
            "better than arbitrary sentinels."
        ),
        "examples": [
            {
                "title": "Best profit from one buy and one sell",
                "input": "prices = [7, 1, 5, 3, 6, 4]",
                "output": "5",
                "walkthrough": (
                    "Keep the cheapest price seen so far and compare today's price against it. "
                    "The best difference is 6 - 1."
                ),
                "code": (
                    "lowest = prices[0]\n"
                    "best = 0\n"
                    "for price in prices[1:]:\n"
                    "    best = max(best, price - lowest)\n"
                    "    lowest = min(lowest, price)"
                ),
            },
        ],
        "complexity_notes": (
            "A single traversal is O(n) time. If the accumulator stores only a fixed number "
            "of values, extra space is O(1). Prefix arrays or lookup sets usually add O(n) space."
        ),
        "implementation_guidance": (
            "Write the invariant in a comment before the loop. Decide whether the current "
            "element is included before or after the update, and make that order consistent. "
            "For an empty input, define the contract before calling prices[0]."
        ),
        "common_traps": (
            "Initializing a maximum to zero when all values can be negative, updating the "
            "answer before updating required state, and accidentally using future values."
        ),
        "guided_practice": (
            "Trace lowest and best for [8, 2, 6, 1, 4]. Then explain why the algorithm never "
            "uses a selling price from before its buying price."
        ),
        "checkpoint": (
            "What exactly is true about the accumulator after processing index i? Answer using "
            "the words 'every element through i'."
        ),
        "prerequisite_slugs": ["array-fundamentals"],
    },
    {
        "name": "Two Pointers",
        "slug": "two-pointers",
        "order": 3,
        "summary": "Use two moving indices to shrink a search space without rechecking pairs.",
        "intuition": (
            "Two pointers are two fingers marking the remaining search interval. A comparison "
            "tells you which finger can move while preserving the possibility of a solution."
        ),
        "explanation": (
            "The two-pointer pattern is most useful when the input has structure, commonly a "
            "sorted array or a sequence where the ends give useful information. Put pointers at "
            "the boundaries, inspect the pair, and move exactly one or both pointers according "
            "to a proof-based rule. Each pointer only moves inward, so pairs are not revisited."
        ),
        "examples": [
            {
                "title": "Two sum in a sorted array",
                "input": "nums = [1, 2, 4, 6, 9], target = 10",
                "output": "[1, 4]",
                "walkthrough": (
                    "The ends sum to 10, so the answer is at indices 1 and 4. If the sum were "
                    "too small, moving right would be the only move that could increase it."
                ),
                "code": (
                    "left, right = 0, len(nums) - 1\n"
                    "while left < right:\n"
                    "    total = nums[left] + nums[right]\n"
                    "    if total == target:\n"
                    "        return [left, right]\n"
                    "    if total < target:\n"
                    "        left += 1\n"
                    "    else:\n"
                    "        right -= 1"
                ),
            },
        ],
        "complexity_notes": (
            "Both pointers move at most n times total, giving O(n) time and O(1) extra space. "
            "Sorting first changes the cost to O(n log n) and may change the meaning of indices."
        ),
        "implementation_guidance": (
            "Confirm the input is sorted, write the pointer invariant, and use while left < right "
            "so the same element is not used twice. Prove why the discarded side cannot contain "
            "a valid pair before moving a pointer."
        ),
        "common_traps": (
            "Applying the pattern to unsorted data without an intentional sort, using <= and "
            "reusing one position, and moving the wrong pointer for the comparison result."
        ),
        "guided_practice": (
            "For [2, 3, 5, 8, 11] and target 13, write every pair inspected and pointer move. "
            "Then give an input where no pair exists."
        ),
        "checkpoint": (
            "If the current pair sums to less than target, why is moving the right pointer left "
            "never helpful in a sorted array?"
        ),
        "prerequisite_slugs": ["array-traversal"],
    },
]


class Command(BaseCommand):
    help = "Seed the original foundational DSA curriculum."

    @transaction.atomic
    def handle(self, *args, **options):
        topic, _ = Topic.objects.update_or_create(
            slug=SEED_TOPIC["slug"],
            defaults={key: value for key, value in SEED_TOPIC.items() if key != "slug"},
        )
        concepts = {}
        for seed_data in SEED_CONCEPTS:
            seed = dict(seed_data)
            prerequisites = seed.pop("prerequisite_slugs")
            concept, _ = Concept.objects.update_or_create(
                slug=seed["slug"],
                defaults={"topic": topic, **seed},
            )
            concepts[concept.slug] = (concept, prerequisites)

        for slug, (concept, prerequisite_slugs) in concepts.items():
            concept.prerequisites.set(
                [concepts[prerequisite_slug][0] for prerequisite_slug in prerequisite_slugs]
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {topic.name} with {len(concepts)} ordered concepts."
            )
        )
