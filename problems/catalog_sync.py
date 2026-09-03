"""Public, unauthenticated LeetCode catalog import support.

The network client is deliberately small and injectable.  The importer only
needs an object exposing ``iter_batches()``, which keeps pagination and import
behavior independently testable with mocked public responses.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from curriculum.models import Concept

from .models import CatalogSync, Problem, ProblemClassification


LEETCODE_SOURCE_NAME = "LeetCode"
LEETCODE_GRAPHQL_ENDPOINT = "https://leetcode.com/graphql"


class CatalogSyncError(RuntimeError):
    """A public catalog could not be read or safely imported."""


class CatalogSyncAlreadyRunning(CatalogSyncError):
    """A second sync was requested while the source is already being read."""


@dataclass(frozen=True)
class CatalogProblem:
    """Normalized fields needed by the local Problem library."""

    title: str
    title_slug: str
    source_problem_id: str
    difficulty: str = ""
    statement: str = ""
    examples: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    is_paid_only: bool = False


@dataclass(frozen=True)
class CatalogPage:
    items: tuple[Mapping[str, Any], ...]
    total: int | None
    skip: int
    limit: int


class _VisibleTextParser(HTMLParser):
    """Turn public HTML statement content into readable plain text."""

    _BLOCK_TAGS = {"br", "div", "li", "ol", "p", "pre", "ul"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _html_to_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    parser = _VisibleTextParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        # Malformed source HTML should remain importable as visible text.
        return " ".join(text.split())
    return " ".join("".join(parser.parts).split())


def _as_bool(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _as_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise CatalogSyncError(f"The public catalog returned an invalid total: {value!r}.") from exc


def _normalize_difficulty(value: object) -> str:
    normalized = str(value or "").strip().lower()
    valid = {choice for choice, _label in Problem.Difficulty.choices}
    return normalized if normalized in valid else ""


def _normalize_tags(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []

    tags: list[str] = []
    seen: set[str] = set()
    for raw_tag in value:
        if isinstance(raw_tag, Mapping):
            raw_tag = raw_tag.get("name") or raw_tag.get("slug") or ""
        tag = str(raw_tag or "").strip()
        if tag and tag.casefold() not in seen:
            seen.add(tag.casefold())
            tags.append(tag)
    return tags


def _normalize_examples(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(example) for example in value if isinstance(example, Mapping)]


def normalize_catalog_problem(raw: Mapping[str, Any]) -> CatalogProblem:
    """Normalize the public response's aliases into local catalog fields."""

    title = str(raw.get("title") or raw.get("translatedTitle") or "").strip()
    title_slug = str(
        raw.get("titleSlug") or raw.get("title_slug") or raw.get("slug") or ""
    ).strip()
    if not title:
        raise CatalogSyncError("The public catalog returned a problem without a title.")
    if not title_slug:
        title_slug = slugify(title)
    if not title_slug:
        raise CatalogSyncError(f"The public catalog returned an unusable title: {title!r}.")

    source_problem_id = str(
        raw.get("frontendQuestionId")
        or raw.get("questionFrontendId")
        or raw.get("source_problem_id")
        or title_slug
    ).strip()

    statement = raw.get("statement")
    if statement in (None, ""):
        statement = raw.get("content")

    return CatalogProblem(
        title=title,
        title_slug=title_slug,
        source_problem_id=source_problem_id,
        difficulty=_normalize_difficulty(raw.get("difficulty")),
        statement=_html_to_text(statement),
        examples=_normalize_examples(raw.get("examples")),
        tags=_normalize_tags(raw.get("topicTags") or raw.get("tags")),
        is_paid_only=_as_bool(raw.get("isPaidOnly", raw.get("paidOnly", False))),
    )


def parse_catalog_page(
    response: Mapping[str, Any],
    *,
    skip: int,
    limit: int,
) -> CatalogPage:
    """Parse either the current LeetCode GraphQL aliases or test fixtures."""

    errors = response.get("errors")
    if errors:
        messages = [
            str(error.get("message", "Unknown public API error"))
            for error in errors
            if isinstance(error, Mapping)
        ]
        raise CatalogSyncError("; ".join(messages) or "The public catalog returned an error.")

    data = response.get("data", response)
    if not isinstance(data, Mapping):
        raise CatalogSyncError("The public catalog response did not contain data.")

    page_data = data.get("problemsetQuestionList") or data.get("questionList")
    if not isinstance(page_data, Mapping):
        raise CatalogSyncError("The public catalog response did not contain a question page.")

    raw_items = page_data.get("questions")
    if raw_items is None:
        raw_items = page_data.get("data", [])
    if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)):
        raise CatalogSyncError("The public catalog question page was not a list.")

    items = tuple(item for item in raw_items if isinstance(item, Mapping))
    return CatalogPage(
        items=items,
        total=_as_int(page_data.get("total", page_data.get("totalNum"))),
        skip=skip,
        limit=limit,
    )


class LeetCodeCatalogClient:
    """Fetch the public LeetCode question list through paginated GraphQL."""

    query = """
    query ProblemsetQuestionList(
      $categorySlug: String,
      $limit: Int!,
      $skip: Int!,
      $filters: QuestionListFilterInput
    ) {
      problemsetQuestionList: questionList(
        categorySlug: $categorySlug,
        limit: $limit,
        skip: $skip,
        filters: $filters
      ) {
        total: totalNum
        questions: data {
          difficulty
          frontendQuestionId: questionFrontendId
          isPaidOnly
          title
          titleSlug
          topicTags { name slug }
        }
      }
    }
    """

    def __init__(
        self,
        *,
        batch_size: int = 100,
        timeout: float = 20,
        endpoint: str = LEETCODE_GRAPHQL_ENDPOINT,
        request_json: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        self.batch_size = batch_size
        self.timeout = timeout
        self.endpoint = endpoint
        self._request_json = request_json or self._request_over_http
        self.total: int | None = None

    def _request_over_http(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "DSA-Roadmap/0.1 (public catalog sync)",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise CatalogSyncError(f"Could not reach the public LeetCode catalog: {exc}") from exc
        if not isinstance(decoded, Mapping):
            raise CatalogSyncError("The public LeetCode catalog returned invalid JSON.")
        return decoded

    def fetch_page(self, *, skip: int) -> CatalogPage:
        response = self._request_json(
            {
                "query": self.query,
                "variables": {
                    "categorySlug": "",
                    "limit": self.batch_size,
                    "skip": skip,
                    "filters": {},
                },
            }
        )
        page = parse_catalog_page(response, skip=skip, limit=self.batch_size)
        self.total = page.total
        return page

    def iter_pages(self) -> Iterator[CatalogPage]:
        skip = 0
        while True:
            page = self.fetch_page(skip=skip)
            yield page
            if not page.items:
                return

            skip += len(page.items)
            if page.total is not None and skip >= page.total:
                return
            if page.total is None and len(page.items) < self.batch_size:
                return

    def iter_batches(self) -> Iterator[tuple[Mapping[str, Any], ...]]:
        for page in self.iter_pages():
            if page.items:
                yield page.items


def _find_existing_problem(item: CatalogProblem) -> Problem | None:
    existing = (
        Problem.objects.filter(
            source_name=LEETCODE_SOURCE_NAME,
            source_problem_id=item.source_problem_id,
        )
        .order_by("id")
        .first()
    )
    if existing:
        return existing

    candidate_slug = slugify(item.title_slug)
    candidate = Problem.objects.filter(slug=candidate_slug).first()
    if candidate is None:
        return None
    if candidate.source_name in {"", LEETCODE_SOURCE_NAME}:
        return candidate
    return None


def _available_slug(item: CatalogProblem, existing: Problem | None) -> str:
    base = slugify(item.title_slug) or slugify(item.title)
    if not base:
        base = f"leetcode-{slugify(item.source_problem_id) or 'problem'}"

    candidate = base
    if existing is not None and existing.slug == candidate:
        return candidate

    if Problem.objects.filter(slug=candidate).exists():
        suffix = slugify(item.source_problem_id) or "problem"
        candidate = f"{base}-{suffix}"
    return candidate[:240]


def _upsert_problem(item: CatalogProblem) -> tuple[Problem, bool]:
    existing = _find_existing_problem(item)
    slug = _available_slug(item, existing)
    defaults: dict[str, Any] = {
        "title": item.title,
        "slug": slug,
        "difficulty": item.difficulty,
        "source_name": LEETCODE_SOURCE_NAME,
        "source_problem_id": item.source_problem_id,
        "source_url": f"https://leetcode.com/problems/{item.title_slug}/",
        "is_paid_only": item.is_paid_only,
        "examples": item.examples,
        "tags": item.tags,
        "is_active": True,
    }

    if existing is None:
        return Problem.objects.create(statement=item.statement, **defaults), True

    # A list response may omit full content.  Keep the last useful statement
    # instead of erasing learner-facing data during a metadata-only refresh.
    defaults["statement"] = item.statement or existing.statement
    for field_name, value in defaults.items():
        setattr(existing, field_name, value)
    existing.save(update_fields=[*defaults.keys(), "updated_at"])
    return existing, False


def _infer_concept(item: CatalogProblem) -> Concept | None:
    tag_slugs = {slugify(tag) for tag in item.tags if slugify(tag)}
    if not tag_slugs:
        return None

    candidates = [
        concept
        for concept in Concept.objects.all()
        if concept.slug in tag_slugs or slugify(concept.name) in tag_slugs
    ]
    return candidates[0] if len(candidates) == 1 else None


def _ensure_classification_warning(problem: Problem, item: CatalogProblem) -> bool:
    """Preserve manual tags and mark only inferred tags as needing review."""

    if ProblemClassification.objects.filter(problem=problem).exists():
        return problem.has_classification_warning

    if problem.concept_id:
        ProblemClassification.objects.create(
            problem=problem,
            concept_id=problem.concept_id,
            status=ProblemClassification.Status.CONFIRMED,
        )
        return False

    inferred_concept = _infer_concept(item)
    if inferred_concept is not None:
        Problem.objects.filter(pk=problem.pk).update(concept_id=inferred_concept.pk)
        problem.concept_id = inferred_concept.pk
        ProblemClassification.objects.create(
            problem=problem,
            concept=inferred_concept,
            status=ProblemClassification.Status.UNCERTAIN,
            note="Matched from a public LeetCode topic tag; review this Concept assignment.",
        )
        return True

    return True


def _save_progress(run: CatalogSync) -> None:
    run.save(
        update_fields=[
            "total_items",
            "processed_items",
            "imported_count",
            "updated_count",
            "classification_warning_count",
            "current_batch",
        ]
    )


def sync_catalog(
    source: Any | None = None,
    *,
    batch_size: int = 100,
    timeout: float = 20,
    progress_callback: Callable[[CatalogSync], None] | None = None,
) -> CatalogSync:
    """Import the complete source stream while keeping the last catalog safe."""

    if source is None:
        source = LeetCodeCatalogClient(batch_size=batch_size, timeout=timeout)

    if not hasattr(source, "iter_batches"):
        raise TypeError("source must expose iter_batches()")

    if CatalogSync.objects.filter(
        source_name=LEETCODE_SOURCE_NAME,
        status=CatalogSync.Status.RUNNING,
    ).exists():
        raise CatalogSyncAlreadyRunning("A LeetCode catalog sync is already running.")

    run = CatalogSync.objects.create(status=CatalogSync.Status.RUNNING)
    seen_source_ids: set[str] = set()

    try:
        for batch_number, raw_batch in enumerate(source.iter_batches(), start=1):
            batch = tuple(raw_batch)
            run.current_batch = batch_number
            run.total_items = int(getattr(source, "total", None) or run.total_items or 0)

            with transaction.atomic():
                for raw_item in batch:
                    if not isinstance(raw_item, Mapping):
                        raise CatalogSyncError("The public catalog returned a malformed problem.")
                    item = normalize_catalog_problem(raw_item)
                    problem, created = _upsert_problem(item)
                    warning = _ensure_classification_warning(problem, item)
                    seen_source_ids.add(item.source_problem_id)
                    run.processed_items += 1
                    if created:
                        run.imported_count += 1
                    else:
                        run.updated_count += 1
                    if warning:
                        run.classification_warning_count += 1

            _save_progress(run)
            if progress_callback:
                progress_callback(run)

        if run.processed_items == 0:
            raise CatalogSyncError(
                "The public catalog returned no problems; the existing catalog was kept."
            )

        # Only a completed stream can deactivate records missing from the
        # source.  Failed/offline runs never remove the last successful shelf.
        stale = Problem.objects.filter(
            source_name=LEETCODE_SOURCE_NAME,
            is_active=True,
        ).exclude(source_problem_id="").exclude(source_problem_id__in=seen_source_ids)
        run.deactivated_count = stale.update(is_active=False)
        run.status = CatalogSync.Status.SUCCEEDED
        run.finished_at = timezone.now()
        run.last_success_at = run.finished_at
        run.save(
            update_fields=[
                "deactivated_count",
                "status",
                "finished_at",
                "last_success_at",
            ]
        )
        if progress_callback:
            progress_callback(run)
        return run
    except Exception as exc:
        run.status = CatalogSync.Status.FAILED
        run.finished_at = timezone.now()
        run.error_message = str(exc)[:2000]
        run.save(update_fields=["status", "finished_at", "error_message"])
        if progress_callback:
            progress_callback(run)
        if isinstance(exc, CatalogSyncError):
            raise
        raise CatalogSyncError(f"Catalog sync failed: {exc}") from exc
