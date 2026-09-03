import ast
import copy
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

from django.db import transaction

from problems.models import Problem

from .models import CustomTestCase
from .models import ProblemDraft
from .models import PracticeRun


MAX_SUBMISSION_LENGTH = 20_000
RUN_TIMEOUT_SECONDS = 1.5
MAX_CUSTOM_TEST_CASES = 20
MAX_CUSTOM_LABEL_LENGTH = 120
MAX_CUSTOM_JSON_LENGTH = 10_000


@dataclass(frozen=True)
class VisibleTest:
    """A JSON-safe learner-facing test case for one catalog Problem."""

    label: str
    args: tuple
    expected: object
    kwargs: dict | None = None
    expected_args: tuple | None = None
    kind: str = "default"
    case_id: int | None = None


VISIBLE_TESTS = {
    "contains-duplicate": (
        VisibleTest("duplicates are detected", ([1, 2, 3, 1],), True),
        VisibleTest("distinct values return false", ([1, 2, 3, 4],), False),
    ),
    "reverse-string": (
        VisibleTest(
            "the characters are reversed in place",
            (["h", "e", "l", "l", "o"],),
            None,
            expected_args=("o", "l", "l", "e", "h"),
        ),
    ),
    "maximum-subarray": (
        VisibleTest("mixed values find the best sum", ([-2, 1, -3, 4, -1, 2, 1, -5, 4],), 6),
        VisibleTest("all-negative values keep the largest value", ([-3, -1, -2],), -1),
    ),
    "best-time-to-buy-and-sell-stock": (
        VisibleTest("a profitable trade is found", ([7, 1, 5, 3, 6, 4],), 5),
        VisibleTest("a falling market returns zero", ([7, 6, 4, 3, 1],), 0),
    ),
    "two-sum-ii-input-array-is-sorted": (
        VisibleTest("the one-indexed pair is returned", ([2, 7, 11, 15], 9), [1, 2]),
        VisibleTest("a later pair is found", ([2, 3, 4], 6), [1, 3]),
    ),
    "valid-palindrome": (
        VisibleTest("punctuation is ignored", ("A man, a plan, a canal: Panama",), True),
        VisibleTest("a non-palindrome is rejected", ("race a car",), False),
    ),
    "search-insert-position": (
        VisibleTest("an existing value returns its index", ([1, 3, 5, 6], 5), 2),
        VisibleTest("a missing value returns its insertion index", ([1, 3, 5, 6], 2), 1),
    ),
}

VISIBLE_TESTS_BY_SOURCE_ID = {
    "217": VISIBLE_TESTS["contains-duplicate"],
    "344": VISIBLE_TESTS["reverse-string"],
    "53": VISIBLE_TESTS["maximum-subarray"],
    "121": VISIBLE_TESTS["best-time-to-buy-and-sell-stock"],
    "167": VISIBLE_TESTS["two-sum-ii-input-array-is-sorted"],
    "125": VISIBLE_TESTS["valid-palindrome"],
    "35": (
        VisibleTest("an existing value returns its index", ([1, 3, 5, 6], 5), 2),
        VisibleTest("a missing value returns its insertion index", ([1, 3, 5, 6], 2), 1),
    ),
}


class SandboxViolation(ValueError):
    """Raised when a submission asks for capabilities outside the runner."""


_BLOCKED_NAMES = {
    "__builtins__",
    "__import__",
    "compile",
    "dir",
    "eval",
    "exec",
    "exit",
    "getattr",
    "globals",
    "help",
    "input",
    "locals",
    "open",
    "quit",
    "setattr",
    "vars",
}


def visible_tests_for(problem: Problem) -> tuple[VisibleTest, ...]:
    """Return tests for seeded slugs and synced records with known source IDs."""

    return VISIBLE_TESTS.get(problem.slug) or VISIBLE_TESTS_BY_SOURCE_ID.get(
        problem.source_problem_id,
        (),
    )


@dataclass(frozen=True)
class ValidatedCustomTest:
    """A validated custom case, before or after it is persisted."""

    case_id: int | None
    label: str
    input_data: list
    expected_output: object


class CustomTestValidationError(ValueError):
    """Raised when custom cases cannot be safely saved or executed."""

    def __init__(self, errors: list[dict]):
        super().__init__("Custom test cases need attention before they can run.")
        self.errors = errors


def _custom_error(index, field, message, case_id=None) -> dict:
    return {
        "index": index,
        "field": field,
        "message": message,
        "id": case_id,
    }


def _json_size(value: object) -> int:
    try:
        return len(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError):
        return -1


def validate_custom_test_payloads(
    problem: Problem,
    payload: object,
) -> list[ValidatedCustomTest]:
    """Validate the complete editable custom-test list before any mutation."""

    if not isinstance(payload, list):
        raise CustomTestValidationError(
            [_custom_error(None, "cases", "Custom tests must be a JSON array.")]
        )
    if len(payload) > MAX_CUSTOM_TEST_CASES:
        raise CustomTestValidationError(
            [
                _custom_error(
                    None,
                    "cases",
                    f"Keep the custom test list to {MAX_CUSTOM_TEST_CASES} cases or fewer.",
                )
            ]
        )

    existing_ids = set(
        CustomTestCase.objects.filter(problem=problem).values_list("id", flat=True)
    )
    seen_ids = set()
    errors = []
    validated = []

    for index, raw_case in enumerate(payload):
        if not isinstance(raw_case, dict):
            errors.append(
                _custom_error(index, "case", "Each custom test must be an object.")
            )
            continue

        raw_id = raw_case.get("id")
        case_id = None
        if raw_id is not None:
            if isinstance(raw_id, bool):
                errors.append(
                    _custom_error(index, "id", "Case id must be a number.", raw_id)
                )
            else:
                try:
                    case_id = int(raw_id)
                except (TypeError, ValueError):
                    errors.append(
                        _custom_error(index, "id", "Case id must be a number.", raw_id)
                    )
                else:
                    if case_id <= 0:
                        errors.append(
                            _custom_error(index, "id", "Case id must be positive.", raw_id)
                        )
                    elif case_id in seen_ids:
                        errors.append(
                            _custom_error(index, "id", "A case cannot appear twice.", raw_id)
                        )
                    elif case_id not in existing_ids:
                        errors.append(
                            _custom_error(
                                index,
                                "id",
                                "This custom test does not belong to the current Problem.",
                                raw_id,
                            )
                        )
                    else:
                        seen_ids.add(case_id)

        raw_label = raw_case.get("label")
        label = raw_label.strip() if isinstance(raw_label, str) else ""
        if not label:
            errors.append(
                _custom_error(index, "label", "Add a short name for this test.", raw_id)
            )
        elif len(label) > MAX_CUSTOM_LABEL_LENGTH:
            errors.append(
                _custom_error(
                    index,
                    "label",
                    f"Keep the test name to {MAX_CUSTOM_LABEL_LENGTH} characters or fewer.",
                    raw_id,
                )
            )

        input_key = "input_data" if "input_data" in raw_case else "input"
        if input_key not in raw_case:
            errors.append(
                _custom_error(
                    index,
                    "input",
                    "Input must be a JSON array of positional arguments.",
                    raw_id,
                )
            )
            input_data = None
        else:
            input_data = raw_case[input_key]
            if not isinstance(input_data, list):
                errors.append(
                    _custom_error(
                        index,
                        "input",
                        "Input must be a JSON array of positional arguments.",
                        raw_id,
                    )
                )
            elif _json_size(input_data) < 0:
                errors.append(
                    _custom_error(
                        index,
                        "input",
                        "Input must contain only JSON values.",
                        raw_id,
                    )
                )
            elif _json_size(input_data) > MAX_CUSTOM_JSON_LENGTH:
                errors.append(
                    _custom_error(
                        index,
                        "input",
                        f"Keep input to {MAX_CUSTOM_JSON_LENGTH:,} JSON characters or fewer.",
                        raw_id,
                    )
                )

        expected_key = (
            "expected_output" if "expected_output" in raw_case else "expected"
        )
        if expected_key not in raw_case:
            errors.append(
                _custom_error(
                    index,
                    "expected",
                    "Expected output is required; null is allowed when it is the answer.",
                    raw_id,
                )
            )
            expected_output = None
        else:
            expected_output = raw_case[expected_key]
            if _json_size(expected_output) < 0:
                errors.append(
                    _custom_error(
                        index,
                        "expected",
                        "Expected output must be a JSON value.",
                        raw_id,
                    )
                )
            elif _json_size(expected_output) > MAX_CUSTOM_JSON_LENGTH:
                errors.append(
                    _custom_error(
                        index,
                        "expected",
                        f"Keep expected output to {MAX_CUSTOM_JSON_LENGTH:,} JSON characters or fewer.",
                        raw_id,
                    )
                )

        if (
            label
            and len(label) <= MAX_CUSTOM_LABEL_LENGTH
            and isinstance(input_data, list)
            and _json_size(input_data) >= 0
            and _json_size(input_data) <= MAX_CUSTOM_JSON_LENGTH
            and expected_key in raw_case
            and _json_size(expected_output) >= 0
            and _json_size(expected_output) <= MAX_CUSTOM_JSON_LENGTH
            and (case_id is None or case_id in existing_ids)
        ):
            validated.append(
                ValidatedCustomTest(
                    case_id=case_id,
                    label=label,
                    input_data=copy.deepcopy(input_data),
                    expected_output=copy.deepcopy(expected_output),
                )
            )

    if errors:
        raise CustomTestValidationError(errors)
    return validated


@transaction.atomic
def save_custom_tests(
    problem: Problem,
    payload: object,
) -> tuple[CustomTestCase, ...]:
    """Replace the learner's ordered custom-test list after full validation."""

    validated = validate_custom_test_payloads(problem, payload)
    existing = {
        case.pk: case
        for case in CustomTestCase.objects.select_for_update().filter(problem=problem)
    }
    retained_ids = set()

    for position, case_data in enumerate(validated):
        if case_data.case_id is None:
            case = CustomTestCase.objects.create(
                problem=problem,
                label=case_data.label,
                input_data=case_data.input_data,
                expected_output=case_data.expected_output,
                position=position,
            )
        else:
            case = existing[case_data.case_id]
            case.label = case_data.label
            case.input_data = case_data.input_data
            case.expected_output = case_data.expected_output
            case.position = position
            case.save(
                update_fields=(
                    "label",
                    "input_data",
                    "expected_output",
                    "position",
                    "updated_at",
                )
            )
        retained_ids.add(case.pk)

    CustomTestCase.objects.filter(problem=problem).exclude(
        pk__in=retained_ids
    ).delete()
    return tuple(
        CustomTestCase.objects.filter(problem=problem).order_by("position", "id")
    )


def custom_visible_tests_for(
    problem: Problem,
    custom_cases=None,
) -> tuple[VisibleTest, ...]:
    """Adapt saved or already-validated custom cases to the runner contract."""

    if custom_cases is None:
        custom_cases = CustomTestCase.objects.filter(problem=problem).order_by(
            "position", "id"
        )

    def value(case, key, model_key=None):
        if isinstance(case, dict):
            return case.get(key)
        return getattr(case, model_key or key)

    return tuple(
        VisibleTest(
            label=f"Custom · {value(case, 'label')}",
            args=tuple(copy.deepcopy(value(case, "input_data"))),
            expected=copy.deepcopy(value(case, "expected_output")),
            kind="custom",
            case_id=(
                value(case, "id")
                if isinstance(case, dict)
                else getattr(case, "pk", None) or case.case_id
            ),
        )
        for case in custom_cases
    )


def function_name_for(problem: Problem) -> str:
    """Extract the callable name from the Problem-specific starter signature."""

    match = re.search(r"^def\s+([A-Za-z_]\w*)\s*\(", starter_signature_for(problem))
    return match.group(1) if match else "solve"


def _validate_submission(code: str) -> None:
    if len(code) > MAX_SUBMISSION_LENGTH:
        raise SandboxViolation(
            f"Submission is limited to {MAX_SUBMISSION_LENGTH:,} characters."
        )

    try:
        tree = ast.parse(code, filename="<submission>")
    except SyntaxError:
        # Syntax errors are useful learner feedback and are classified by the
        # child runner as a runtime error without ever executing the code.
        return

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise SandboxViolation(
                "Imports are disabled in the local runner; use the function's "
                "Python builtins instead."
            )
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise SandboxViolation(
                "Dunder attribute access is disabled in the local runner."
            )
        if isinstance(node, ast.Name) and node.id in _BLOCKED_NAMES:
            raise SandboxViolation(
                f"The builtin {node.id!r} is disabled in the local runner."
            )


def _test_payload(test: VisibleTest) -> dict:
    payload = {
        "label": test.label,
        "kind": test.kind,
        "case_id": test.case_id,
        "args": copy.deepcopy(list(test.args)),
        "kwargs": copy.deepcopy(test.kwargs or {}),
        "expected": copy.deepcopy(test.expected),
    }
    if test.expected_args is not None:
        payload["expected_args"] = [copy.deepcopy(test.expected_args)]
    return payload


# This source runs in a fresh ``python -I -S`` process. The learner code is
# executed with a small builtin allowlist, no imports, no inherited modules,
# and an audit hook that rejects OS, network, subprocess, and file events.
_RUNNER_SOURCE = r'''
import ast as _ast
import builtins as _builtins
import json as _json
import resource as _resource
import sys as _sys


def _audit(event, _args):
    blocked = (
        "open",
        "os.",
        "socket.",
        "subprocess.",
        "ctypes.",
        "pty.",
        "shutil.",
    )
    if event.startswith(blocked):
        raise PermissionError("sandbox denied this operating-system capability")


_sys.addaudithook(_audit)
try:
    _resource.setrlimit(_resource.RLIMIT_CPU, (2, 2))
    _resource.setrlimit(_resource.RLIMIT_FSIZE, (0, 0))
    _resource.setrlimit(_resource.RLIMIT_NOFILE, (3, 3))
    if hasattr(_resource, "RLIMIT_AS"):
        _resource.setrlimit(_resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
except (OSError, ValueError):
    pass


_SAFE_BUILTINS = {
    name: getattr(_builtins, name)
    for name in (
        "Exception",
        "AssertionError",
        "IndexError",
        "KeyError",
        "MemoryError",
        "RuntimeError",
        "StopIteration",
        "TypeError",
        "ValueError",
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "enumerate",
        "filter",
        "float",
        "int",
        "isinstance",
        "len",
        "list",
        "map",
        "max",
        "min",
        "range",
        "reversed",
        "round",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
        "type",
        "zip",
    )
}


def _message(error):
    text = _builtins.str(error).strip() or "No additional details."
    return f"{type(error).__name__}: {text[:240]}"


def _serializable(value, label):
    try:
        _json.dumps(value)
    except (TypeError, ValueError) as error:
        raise TypeError(f"{label} must be JSON-serializable") from error
    return value


def _emit(payload):
    _sys.stdout.write(_json.dumps(payload, separators=(",", ":")))
    _sys.stdout.flush()


def _main():
    request = _json.load(_sys.stdin)
    code = request["code"]
    try:
        tree = _ast.parse(code, filename="<submission>")
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.Import, _ast.ImportFrom)):
                raise PermissionError("imports are disabled in the local runner")
            if isinstance(node, _ast.Attribute) and node.attr.startswith("__"):
                raise PermissionError("dunder attribute access is disabled")
        compiled = compile(tree, "<submission>", "exec", dont_inherit=True)
        namespace = {"__builtins__": _SAFE_BUILTINS}
        exec(compiled, namespace, namespace)
        function = namespace.get(request["function_name"])
        if not callable(function):
            raise NameError(f"Define {request['function_name']} before running.")
    except PermissionError as error:
        _emit({"status": "safety_violation", "message": _message(error), "details": []})
        return
    except BaseException as error:
        _emit({"status": "runtime_error", "message": _message(error), "details": []})
        return

    details = []
    passed = 0
    status = "passed"
    for index, case in enumerate(request["tests"], start=1):
        args = case["args"]
        kwargs = case["kwargs"]
        try:
            actual = function(*args, **kwargs)
            _serializable(actual, "Return value")
            expected = case["expected"]
            expected_args = case.get("expected_args")
            actual_args = [args[index] for index in range(len(args))]
            _serializable(actual_args, "Mutated arguments")
            passed_case = actual == expected and (
                expected_args is None or actual_args == expected_args
            )
            detail = {
                "label": case["label"],
                "kind": case.get("kind", "default"),
                "case_id": case.get("case_id"),
                "passed": passed_case,
                "expected": expected,
                "actual": actual,
            }
            if expected_args is not None:
                detail["expected_args"] = expected_args
                detail["actual_args"] = actual_args
            details.append(detail)
            if not passed_case:
                if status == "passed":
                    status = "assertion_failure"
            else:
                passed += 1
        except AssertionError as error:
            status = "assertion_failure"
            details.append({
                "label": case["label"],
                "kind": case.get("kind", "default"),
                "case_id": case.get("case_id"),
                "passed": False,
                "message": _message(error),
            })
        except BaseException as error:
            if status == "passed":
                status = "runtime_error"
            details.append({
                "label": case["label"],
                "kind": case.get("kind", "default"),
                "case_id": case.get("case_id"),
                "passed": False,
                "message": _message(error),
            })

    if status == "passed":
        message = "Every visible test passed."
    else:
        message = "Review the highlighted visible tests and try again."
    _emit({
        "status": status,
        "passed_tests": passed,
        "message": message,
        "details": details,
    })


_main()
'''


@dataclass(frozen=True)
class ExecutionResult:
    status: str
    passed_tests: int
    total_tests: int
    duration_ms: int
    message: str
    details: list[dict]


def _run_in_subprocess(problem: Problem, code: str, tests: tuple[VisibleTest, ...]) -> ExecutionResult:
    started = time.monotonic()
    try:
        _validate_submission(code)
    except SandboxViolation as error:
        return ExecutionResult(
            status=PracticeRun.Status.SAFETY_VIOLATION,
            passed_tests=0,
            total_tests=len(tests),
            duration_ms=0,
            message=str(error),
            details=[],
        )

    request = json.dumps(
        {
            "code": code,
            "function_name": function_name_for(problem),
            "tests": [_test_payload(test) for test in tests],
        }
    )
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix="dsa-practice-") as sandbox_dir:
            process = subprocess.Popen(
                [sys.executable, "-I", "-S", "-c", _RUNNER_SOURCE],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=sandbox_dir,
                env={"PATH": os.defpath, "PYTHONNOUSERSITE": "1"},
                start_new_session=True,
                text=True,
            )
            stdout, _stderr = process.communicate(
                request,
                timeout=RUN_TIMEOUT_SECONDS,
            )
    except subprocess.TimeoutExpired:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
        elapsed_ms = max(1, int((time.monotonic() - started) * 1000))
        return ExecutionResult(
            status=PracticeRun.Status.TIMEOUT,
            passed_tests=0,
            total_tests=len(tests),
            duration_ms=elapsed_ms,
            message=(
                f"Execution stopped after {RUN_TIMEOUT_SECONDS:g} seconds. "
                "Check the loop or recursion before trying again."
            ),
            details=[],
        )
    except (OSError, ValueError) as error:
        return ExecutionResult(
            status=PracticeRun.Status.RUNTIME_ERROR,
            passed_tests=0,
            total_tests=len(tests),
            duration_ms=max(0, int((time.monotonic() - started) * 1000)),
            message=f"Runner error: {error}",
            details=[],
        )

    duration_ms = max(0, int((time.monotonic() - started) * 1000))
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return ExecutionResult(
            status=PracticeRun.Status.RUNTIME_ERROR,
            passed_tests=0,
            total_tests=len(tests),
            duration_ms=duration_ms,
            message="The isolated runner stopped before it returned a result.",
            details=[],
        )

    return ExecutionResult(
        status=payload.get("status", PracticeRun.Status.RUNTIME_ERROR),
        passed_tests=int(payload.get("passed_tests", 0)),
        total_tests=len(tests),
        duration_ms=duration_ms,
        message=str(payload.get("message", "The runner returned no details.")),
        details=payload.get("details", []),
    )


def run_visible_tests(
    problem: Problem,
    *,
    code: str,
    custom_cases=None,
    custom_tests=None,
) -> PracticeRun:
    """Execute and persist one bounded run with defaults and custom cases."""

    if custom_cases is not None and custom_tests is not None:
        raise ValueError("Pass custom_cases or custom_tests, not both.")
    if custom_tests is not None:
        custom_cases = custom_tests

    if custom_cases is None:
        custom_cases = validate_custom_test_payloads(
            problem,
            [
                {
                    "id": case.pk,
                    "label": case.label,
                    "input_data": case.input_data,
                    "expected_output": case.expected_output,
                }
                for case in CustomTestCase.objects.filter(problem=problem).order_by(
                    "position", "id"
                )
            ],
        )
    elif custom_cases and not isinstance(custom_cases[0], ValidatedCustomTest):
        if isinstance(custom_cases[0], dict):
            custom_cases = validate_custom_test_payloads(problem, custom_cases)
        else:
            custom_cases = validate_custom_test_payloads(
                problem,
                [
                    {
                        "id": case.pk,
                        "label": case.label,
                        "input_data": case.input_data,
                        "expected_output": case.expected_output,
                    }
                    for case in custom_cases
                ],
            )

    tests = visible_tests_for(problem) + custom_visible_tests_for(
        problem,
        custom_cases,
    )
    if not tests:
        result = ExecutionResult(
            status=PracticeRun.Status.NO_TESTS,
            passed_tests=0,
            total_tests=0,
            duration_ms=0,
            message="No visible tests are configured for this Problem yet.",
            details=[],
        )
    else:
        result = _run_in_subprocess(problem, code, tests)

    return PracticeRun.objects.create(
        problem=problem,
        code=code,
        status=result.status,
        passed_tests=result.passed_tests,
        total_tests=result.total_tests,
        duration_ms=result.duration_ms,
        message=result.message,
        details=result.details,
    )


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
