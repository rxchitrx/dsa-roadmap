from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from curriculum.models import Concept

from problems.models import Problem


SEED_PROBLEMS = [
    {
        "title": "Contains Duplicate",
        "slug": "contains-duplicate",
        "concept_slug": "array-fundamentals",
        "difficulty": Problem.Difficulty.EASY,
        "source_name": "LeetCode",
        "source_problem_id": "217",
        "source_url": "https://leetcode.com/problems/contains-duplicate/",
        "statement": (
            "Given an integer array nums, return true if any value appears at least twice "
            "in the array, and return false if every element is distinct."
        ),
        "examples": [
            {"input": "nums = [1, 2, 3, 1]", "output": "true"},
            {"input": "nums = [1, 2, 3, 4]", "output": "false"},
        ],
        "tags": ["array", "hash-set"],
        "display_order": 1,
    },
    {
        "title": "Reverse String",
        "slug": "reverse-string",
        "concept_slug": "array-fundamentals",
        "difficulty": Problem.Difficulty.EASY,
        "source_name": "LeetCode",
        "source_problem_id": "344",
        "source_url": "https://leetcode.com/problems/reverse-string/",
        "statement": (
            "Write a function that reverses a list of characters in place using O(1) extra "
            "memory."
        ),
        "examples": [
            {"input": "s = ['h', 'e', 'l', 'l', 'o']", "output": "['o', 'l', 'l', 'e', 'h']"}
        ],
        "tags": ["array", "two-pointers", "in-place"],
        "display_order": 2,
    },
    {
        "title": "Maximum Subarray",
        "slug": "maximum-subarray",
        "concept_slug": "array-traversal",
        "difficulty": Problem.Difficulty.MEDIUM,
        "source_name": "LeetCode",
        "source_problem_id": "53",
        "source_url": "https://leetcode.com/problems/maximum-subarray/",
        "statement": (
            "Given an integer array nums, find the subarray with the largest sum and return "
            "its sum."
        ),
        "examples": [
            {"input": "nums = [-2,1,-3,4,-1,2,1,-5,4]", "output": "6"}
        ],
        "tags": ["array", "dynamic-programming", "kadane"],
        "display_order": 3,
    },
    {
        "title": "Best Time to Buy and Sell Stock",
        "slug": "best-time-to-buy-and-sell-stock",
        "concept_slug": "array-traversal",
        "difficulty": Problem.Difficulty.EASY,
        "source_name": "LeetCode",
        "source_problem_id": "121",
        "source_url": "https://leetcode.com/problems/best-time-to-buy-and-sell-stock/",
        "statement": (
            "Choose one day to buy a stock and a different later day to sell it to maximize "
            "your profit. Return the maximum profit, or zero if no profit is possible."
        ),
        "examples": [
            {"input": "prices = [7,1,5,3,6,4]", "output": "5"},
            {"input": "prices = [7,6,4,3,1]", "output": "0"},
        ],
        "tags": ["array", "greedy", "running-minimum"],
        "display_order": 4,
    },
    {
        "title": "Two Sum II - Input Array Is Sorted",
        "slug": "two-sum-ii-input-array-is-sorted",
        "concept_slug": "two-pointers",
        "difficulty": Problem.Difficulty.MEDIUM,
        "source_name": "LeetCode",
        "source_problem_id": "167",
        "source_url": "https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/",
        "statement": (
            "Given a 1-indexed array of integers that is already sorted in non-decreasing order, "
            "find two numbers that add up to a specific target number."
        ),
        "examples": [
            {"input": "numbers = [2,7,11,15], target = 9", "output": "[1,2]"}
        ],
        "tags": ["array", "two-pointers", "sorted"],
        "display_order": 5,
    },
    {
        "title": "Valid Palindrome",
        "slug": "valid-palindrome",
        "concept_slug": "two-pointers",
        "difficulty": Problem.Difficulty.EASY,
        "source_name": "LeetCode",
        "source_problem_id": "125",
        "source_url": "https://leetcode.com/problems/valid-palindrome/",
        "statement": (
            "Return true if a phrase is a palindrome after converting uppercase letters to "
            "lowercase and removing all non-alphanumeric characters."
        ),
        "examples": [
            {"input": "s = 'A man, a plan, a canal: Panama'", "output": "true"},
            {"input": "s = 'race a car'", "output": "false"},
        ],
        "tags": ["string", "two-pointers", "normalization"],
        "display_order": 6,
    },
]


class Command(BaseCommand):
    help = "Seed representative DSA problems for the local problem library."

    @transaction.atomic
    def handle(self, *args, **options):
        concept_slugs = {item["concept_slug"] for item in SEED_PROBLEMS}
        concepts = {
            concept.slug: concept
            for concept in Concept.objects.filter(slug__in=concept_slugs)
        }
        missing_slugs = sorted(concept_slugs - concepts.keys())
        if missing_slugs:
            raise CommandError(
                "Missing curriculum concepts: "
                + ", ".join(missing_slugs)
                + ". Run seed_curriculum first."
            )

        for seed_data in SEED_PROBLEMS:
            seed = dict(seed_data)
            seed["concept"] = concepts[seed.pop("concept_slug")]
            Problem.objects.update_or_create(
                slug=seed["slug"],
                defaults=seed,
            )

        self.stdout.write(
            self.style.SUCCESS(f"Seeded {len(SEED_PROBLEMS)} representative DSA problems.")
        )
