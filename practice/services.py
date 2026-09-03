import re
from dataclasses import dataclass

from django.db import transaction

from problems.models import Problem

from .models import ProblemDraft


# The seeded catalog has known LeetCode contracts. Keeping these here means the
# practice slice can provide useful signatures without changing catalog data.
KNOWN_SIGNATURES = {
    "contains-duplicate": "def contains_duplicate(nums):",
    "reverse-string": "def reverse_string(s):",
    "maximum-subarray": "def max_sub_array(nums):",
    "best-time-to-buy-and-sell-stock": "def max_profit(prices):",
    "two-sum-ii-input-array-is-sorted": "def two_sum(numbers, target):",
    "valid-palindrome": "def is_palindrome(s):",
    "search-insert-position": "def search_insert(nums, target):",
}


@dataclass(frozen=True)
class DraftSaveResult:
    saved: bool
    draft: ProblemDraft


def _function_name_for(problem: Problem) -> str:
    """Create a stable Python identifier for catalog entries without a map."""

    value = re.sub(r"[^a-zA-Z0-9]+", "_", problem.slug or problem.title)
    value = value.strip("_").lower() or "solve"
    if value[0].isdigit():
        value = f"solve_{value}"
    return value[:64]


def starter_signature_for(problem: Problem) -> str:
    """Return the best-known function signature for this specific Problem."""

    return KNOWN_SIGNATURES.get(
        problem.slug,
        f"def {_function_name_for(problem)}(data):",
    )


def starter_code_for(problem: Problem) -> str:
    signature = starter_signature_for(problem)
    return (
        f'{signature}\n'
        '    """Write your solution here, then explain the invariant below."""\n'
        "    pass\n"
    )


def get_or_create_draft(problem: Problem) -> tuple[ProblemDraft, bool]:
    """Create the first draft once and preserve it on every later page load."""

    return ProblemDraft.objects.get_or_create(
        problem=problem,
        defaults={
            "starter_signature": starter_signature_for(problem),
            "code": starter_code_for(problem),
        },
    )


@transaction.atomic
def save_draft(
    problem: Problem,
    *,
    code: str,
    base_revision: int,
) -> DraftSaveResult:
    """Save only when the browser started from the current server revision.

    This is optimistic concurrency control for autosave. A stale request gets
    the current draft back and cannot replace newer learner work.
    """

    draft = ProblemDraft.objects.select_for_update().get(problem=problem)
    if base_revision != draft.revision:
        return DraftSaveResult(saved=False, draft=draft)

    draft.code = code
    draft.revision += 1
    draft.save(update_fields=("code", "revision", "updated_at"))
    return DraftSaveResult(saved=True, draft=draft)
