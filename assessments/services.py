from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from curriculum.models import Concept
from planner.models import StudyBlock
from practice.models import LearningStatus, ProblemLearningStatus
from problems.models import Problem

from .models import (
    AssessmentPool,
    AssessmentResponse,
    AssessmentSelection,
    AssessmentSession,
)


SLOT_PLAN = (
    (AssessmentSelection.SlotKind.EASY, 1),
    (AssessmentSelection.SlotKind.MEDIUM, 2),
)


class AssessmentUnavailable(ValueError):
    """Raised when a Saturday session cannot be started from the current pool."""


class AssessmentClosed(ValueError):
    """Raised when a response is changed after final submission."""


def week_start_for(value: date) -> date:
    """Return the Monday containing ``value`` without changing planner code."""

    return value - timedelta(days=value.weekday())


def _week_end_for(week_start: date) -> date:
    return week_start + timedelta(days=6)


def _is_concept_study_block(block: StudyBlock) -> bool:
    """Recognize the planner's concept-learning block without changing it."""

    if block.routine_key:
        return block.routine_key.endswith("-concept")
    return "concept" in block.title.casefold()


def get_studied_concept_evidence(
    week_start: date | None = None,
) -> dict[int, dict]:
    """Return explicit current-week Concept study evidence keyed by Concept id.

    A completed concept-learning StudyBlock is the intentionally narrow signal
    for this slice. A partially timed block is not silently treated as studied;
    later assessment work can decide how partial evidence should count.
    """

    start = week_start_for(week_start or timezone.localdate())
    blocks = (
        StudyBlock.objects.select_related("assigned_concept__topic")
        .filter(
            date__range=(start, _week_end_for(start)),
            assigned_concept__isnull=False,
            status=StudyBlock.Status.COMPLETED,
        )
        .order_by("date", "position", "id")
    )

    evidence_by_concept: dict[int, dict] = {}
    for block in blocks:
        if not _is_concept_study_block(block):
            continue

        concept = block.assigned_concept
        evidence = evidence_by_concept.setdefault(
            concept.pk,
            {
                "concept": concept,
                "evidence": [],
            },
        )
        evidence["evidence"].append(
            {
                "type": "completed_study_block",
                "block_id": block.pk,
                "date": block.date.isoformat(),
                "title": block.title,
            }
        )

    return evidence_by_concept


def get_studied_concepts(week_start: date | None = None) -> list[Concept]:
    """Return Concepts with explicit completed study evidence this week."""

    evidence = get_studied_concept_evidence(week_start)
    return [item["concept"] for item in evidence.values()]


def _get_older_concept_evidence(
    week_start: date,
    excluded_concept_ids: set[int],
) -> dict[int, dict]:
    """Return fallback Concepts outside the current week's studied set.

    Concepts with completed study blocks before this week are ranked ahead of
    untouched Concepts. The latter are still eligible because the local
    curriculum does not have a separate concept-readiness table yet; keeping
    them available makes a zero-preferred-pool assessment useful without
    pretending that the fallback measured current-week learning.
    """

    prior_blocks = (
        StudyBlock.objects.select_related("assigned_concept__topic")
        .filter(
            date__lt=week_start,
            assigned_concept__isnull=False,
            status=StudyBlock.Status.COMPLETED,
        )
        .order_by("date", "position", "id")
    )
    prior_evidence: dict[int, list[dict]] = {}
    for block in prior_blocks:
        if not _is_concept_study_block(block):
            continue
        prior_evidence.setdefault(block.assigned_concept_id, []).append(
            {
                "type": "completed_prior_study_block",
                "block_id": block.pk,
                "date": block.date.isoformat(),
                "title": block.title,
            }
        )

    concepts = (
        Concept.objects.select_related("topic")
        .exclude(pk__in=excluded_concept_ids)
        .order_by("topic__display_order", "topic__id", "order", "id")
    )
    return {
        concept.pk: {
            "concept": concept,
            "evidence": prior_evidence.get(concept.pk, []),
        }
        for concept in concepts
    }


def _problem_concept_metadata(problem: Problem, studied_evidence: dict[int, dict]) -> list[dict]:
    """Explain which studied Concepts make a Problem eligible."""

    concept_ids = set()
    if problem.concept_id:
        concept_ids.add(problem.concept_id)
    concept_ids.update(
        classification.concept_id
        for classification in problem.classifications.all()
    )

    matching = []
    for concept_id in sorted(concept_ids):
        if concept_id not in studied_evidence:
            continue
        concept = studied_evidence[concept_id]["concept"]
        matching.append(
            {
                "id": concept.pk,
                "name": concept.name,
                "topic": concept.topic.name,
                "evidence": studied_evidence[concept_id]["evidence"],
            }
        )
    return matching


def _unseen_by_problem_id(problem_ids: list[int]) -> dict[int, bool]:
    statuses = dict(
        ProblemLearningStatus.objects.filter(problem_id__in=problem_ids).values_list(
            "problem_id", "status"
        )
    )
    return {
        problem_id: statuses.get(problem_id, LearningStatus.UNSEEN)
        == LearningStatus.UNSEEN
        for problem_id in problem_ids
    }


def _candidate_pool(studied_evidence: dict[int, dict]) -> list[dict]:
    if not studied_evidence:
        return []

    studied_ids = list(studied_evidence)
    candidates = list(
        Problem.objects.filter(
            Q(concept_id__in=studied_ids)
            | Q(classifications__concept_id__in=studied_ids),
            difficulty__in=(
                Problem.Difficulty.EASY,
                Problem.Difficulty.MEDIUM,
            ),
            is_active=True,
        )
        .select_related("concept__topic")
        .prefetch_related(
            "classifications__concept__topic",
        )
        .distinct()
    )
    unseen_by_problem_id = _unseen_by_problem_id([item.pk for item in candidates])

    candidate_rows = []
    for problem in candidates:
        eligible_concepts = _problem_concept_metadata(problem, studied_evidence)
        if not eligible_concepts:
            continue
        candidate_rows.append(
            {
                "problem": problem,
                "difficulty": problem.difficulty,
                "is_unseen": unseen_by_problem_id[problem.pk],
                "eligible_concepts": eligible_concepts,
                "concept_evidence": [
                    evidence
                    for concept in eligible_concepts
                    for evidence in concept["evidence"]
                ],
            }
        )
    return candidate_rows


def _candidate_sort_key(row: dict) -> tuple:
    problem = row["problem"]
    return (
        not row["is_unseen"],
        problem.display_order,
        problem.title.casefold(),
        problem.pk,
    )


def _fallback_candidate_sort_key(row: dict) -> tuple:
    problem = row["problem"]
    return (
        not row["is_unseen"],
        not bool(row["concept_evidence"]),
        problem.display_order,
        problem.title.casefold(),
        problem.pk,
    )


def _selection_rationale(
    row: dict,
    slot_kind: str,
    *,
    source_kind: str,
    source_reason: str = "",
) -> str:
    concept_names = ", ".join(
        concept["name"] for concept in row["eligible_concepts"]
    )
    novelty = "unseen preference" if row["is_unseen"] else "no unseen eligible Problem remained"
    if source_kind == AssessmentSelection.SourceKind.OLDER_CONCEPT_FALLBACK:
        return (
            f"{slot_kind.title()} fallback from older Concept(s): {concept_names}. "
            f"{source_reason} Chosen with {novelty}."
        )
    return (
        f"{slot_kind.title()} slot from current-week studied Concept(s): "
        f"{concept_names}. Chosen with {novelty}."
    )


def _pool_rationale(
    studied_evidence: dict[int, dict],
    candidate_rows: list[dict],
    selected_rows: list[tuple[str, dict, str, str]],
) -> str:
    concept_names = ", ".join(
        item["concept"].name for item in studied_evidence.values()
    )
    candidate_counts = Counter(row["difficulty"] for row in candidate_rows)
    selected_counts = Counter(kind for kind, _row, _source, _reason in selected_rows)
    fallback_rows = [
        (kind, row)
        for kind, row, source, _reason in selected_rows
        if source == AssessmentSelection.SourceKind.OLDER_CONCEPT_FALLBACK
    ]
    selected_unseen = sum(
        row["is_unseen"] for _kind, row, _source, _reason in selected_rows
    )
    selected_count = len(selected_rows)
    rationale = (
        f"Eligible Concepts studied this week: {concept_names or 'none'}. "
        f"The selector requested 1 easy and 2 medium Problems, preferring unseen "
        f"Problems within each difficulty. Found {candidate_counts['easy']} easy and "
        f"{candidate_counts['medium']} medium candidates; selected "
        f"{selected_counts['easy']} easy and {selected_counts['medium']} medium "
        f"({selected_unseen} of {selected_count} unseen)."
    )
    if fallback_rows:
        fallback_counts = Counter(kind for kind, _row in fallback_rows)
        rationale += (
            f" The preferred current-week pool was sparse, so the selector filled "
            f"{len(fallback_rows)} slot(s) from older Concepts "
            f"({fallback_counts['easy']} easy and {fallback_counts['medium']} medium). "
            "Fallback Problems are reported separately from the current-week score."
        )
    elif selected_count < 3:
        rationale += (
            " The current-week pool is sparse, and no eligible older-Concept "
            "Problems were available to fill the remaining slots."
        )
    return rationale


@transaction.atomic
def generate_saturday_assessment_pool(
    week_start: date | None = None,
) -> AssessmentPool:
    """Generate the Saturday pool, filling missing slots with older Concepts."""

    start = week_start_for(week_start or timezone.localdate())
    existing_pool = AssessmentPool.objects.filter(week_start=start).first()
    if existing_pool and AssessmentSession.objects.filter(pool=existing_pool).exists():
        # Starting a session freezes its Problem identities. A later pool page
        # load must not regenerate selections and cascade away saved answers.
        return existing_pool
    studied_evidence = get_studied_concept_evidence(start)
    candidate_rows = _candidate_pool(studied_evidence)
    selected_rows: list[tuple[str, dict, str, str]] = []
    selected_problem_ids: set[int] = set()

    for slot_kind, requested_count in SLOT_PLAN:
        matching = sorted(
            (
                row
                for row in candidate_rows
                if row["difficulty"] == slot_kind
                and row["problem"].pk not in selected_problem_ids
            ),
            key=_candidate_sort_key,
        )
        for row in matching[:requested_count]:
            selected_rows.append(
                (
                    slot_kind,
                    row,
                    AssessmentSelection.SourceKind.CURRENT_WEEK,
                    "",
                )
            )
            selected_problem_ids.add(row["problem"].pk)

    preferred_problem_ids = {row["problem"].pk for row in candidate_rows}
    older_evidence = _get_older_concept_evidence(
        start,
        set(studied_evidence),
    )
    fallback_rows = [
        row
        for row in _candidate_pool(older_evidence)
        if row["problem"].pk not in preferred_problem_ids
    ]
    current_counts = Counter(
        kind
        for kind, _row, source, _reason in selected_rows
        if source == AssessmentSelection.SourceKind.CURRENT_WEEK
    )
    fallback_candidate_counts = Counter(
        row["difficulty"] for row in fallback_rows
    )
    for slot_kind, requested_count in SLOT_PLAN:
        remaining_count = requested_count - current_counts[slot_kind]
        matching = sorted(
            (
                row
                for row in fallback_rows
                if row["difficulty"] == slot_kind
                and row["problem"].pk not in selected_problem_ids
            ),
            key=_fallback_candidate_sort_key,
        )
        source_reason = (
            f"The current-week studied Concept pool had only "
            f"{current_counts[slot_kind]} eligible {slot_kind} Problem(s); "
            f"this slot was filled from an older Concept."
        )
        for row in matching[:remaining_count]:
            selected_rows.append(
                (
                    slot_kind,
                    row,
                    AssessmentSelection.SourceKind.OLDER_CONCEPT_FALLBACK,
                    source_reason,
                )
            )
            selected_problem_ids.add(row["problem"].pk)

    pool, _created = AssessmentPool.objects.get_or_create(
        week_start=start,
        defaults={
            "requested_problem_count": 3,
            "duration_minutes": 90,
        },
    )
    pool.selections.all().delete()

    candidate_counts = Counter(row["difficulty"] for row in candidate_rows)
    unseen_candidate_counts = Counter(
        row["difficulty"] for row in candidate_rows if row["is_unseen"]
    )
    fallback_selected_counts = Counter(
        kind
        for kind, _row, source, _reason in selected_rows
        if source == AssessmentSelection.SourceKind.OLDER_CONCEPT_FALLBACK
    )
    metadata = {
        "week_start": start.isoformat(),
        "studied_concepts": [
            {
                "id": item["concept"].pk,
                "name": item["concept"].name,
                "topic": item["concept"].topic.name,
                "evidence": item["evidence"],
            }
            for item in studied_evidence.values()
        ],
        "requested_mix": {"easy": 1, "medium": 2},
        "candidate_counts": {
            "easy": candidate_counts["easy"],
            "medium": candidate_counts["medium"],
        },
        "unseen_candidate_counts": {
            "easy": unseen_candidate_counts["easy"],
            "medium": unseen_candidate_counts["medium"],
        },
        "selected_counts": dict(
            Counter(kind for kind, _row, _source, _reason in selected_rows)
        ),
        "current_week_selected_counts": dict(current_counts),
        "fallback_candidate_counts": {
            "easy": fallback_candidate_counts["easy"],
            "medium": fallback_candidate_counts["medium"],
        },
        "fallback_selected_counts": {
            "easy": fallback_selected_counts["easy"],
            "medium": fallback_selected_counts["medium"],
        },
        "selection_scope": (
            "current_week_and_older_concept_fallback"
            if fallback_selected_counts
            else "current_week_studied_concepts"
        ),
        "fallback_included": bool(fallback_selected_counts),
    }
    pool.rationale = _pool_rationale(studied_evidence, candidate_rows, selected_rows)
    pool.eligibility_metadata = metadata
    pool.save(update_fields=("rationale", "eligibility_metadata", "updated_at"))

    for position, (slot_kind, row, source_kind, source_reason) in enumerate(
        selected_rows,
        start=1,
    ):
        problem = row["problem"]
        AssessmentSelection.objects.create(
            pool=pool,
            problem=problem,
            position=position,
            slot_kind=slot_kind,
            is_unseen=row["is_unseen"],
            rationale=_selection_rationale(
                row,
                slot_kind,
                source_kind=source_kind,
                source_reason=source_reason,
            ),
            eligibility_metadata={
                "eligibility": source_kind,
                "source_kind": source_kind,
                "source_reason": source_reason,
                "eligible_concepts": row["eligible_concepts"],
                "difficulty": problem.difficulty,
                "is_unseen": row["is_unseen"],
                "concept_evidence": row.get("concept_evidence", []),
            },
        )

    return pool


# A descriptive alias for callers that care about the selection operation.
select_saturday_problems = generate_saturday_assessment_pool


def _now(value=None):
    return value or timezone.now()


def _ensure_session_responses(session: AssessmentSession) -> None:
    """Create missing response rows without resetting an existing session."""

    existing_selection_ids = set(
        session.responses.values_list("selection_id", flat=True)
    )
    selections = session.pool.selections.all()
    missing = [
        AssessmentResponse(session=session, selection=selection)
        for selection in selections
        if selection.pk not in existing_selection_ids
    ]
    if missing:
        AssessmentResponse.objects.bulk_create(missing)


def _response_snapshot(response: AssessmentResponse) -> dict:
    selection = response.selection
    return {
        "response_id": response.pk,
        "selection_id": selection.pk,
        "position": selection.position,
        "problem_id": selection.problem_id,
        "difficulty": selection.slot_kind,
        "source_kind": selection.source_kind,
        "source_reason": selection.source_reason,
        "is_fallback": selection.is_fallback,
        "draft_answer": response.draft_answer,
        "outcome": response.outcome,
        "result_note": response.result_note,
    }


def _record_cutoff_snapshot(
    session: AssessmentSession,
    captured_at,
    *,
    mark_overtime: bool,
) -> AssessmentSession:
    responses = list(
        session.responses.select_related("selection__problem").order_by(
            "selection__position", "id"
        )
    )
    snapshot = [_response_snapshot(response) for response in responses]
    for response in responses:
        response.cutoff_draft_answer = response.draft_answer
        response.cutoff_outcome = response.outcome
        response.cutoff_result_note = response.result_note
        response.cutoff_recorded_at = captured_at
        response.save(
            update_fields=(
                "cutoff_draft_answer",
                "cutoff_outcome",
                "cutoff_result_note",
                "cutoff_recorded_at",
                "updated_at",
            )
        )

    session.cutoff_recorded_at = captured_at
    session.cutoff_snapshot = {
        "captured_at": captured_at.isoformat(),
        "responses": snapshot,
    }
    if mark_overtime and session.status == AssessmentSession.Status.IN_PROGRESS:
        session.status = AssessmentSession.Status.OVERTIME
    session.save(
        update_fields=(
            "cutoff_recorded_at",
            "cutoff_snapshot",
            "status",
            "updated_at",
        )
    )
    return session


@transaction.atomic
def refresh_assessment_session(
    session: AssessmentSession,
    now=None,
) -> AssessmentSession:
    """Record the official timed snapshot once the 90-minute cutoff is reached."""

    current_time = _now(now)
    if (
        session.status == AssessmentSession.Status.IN_PROGRESS
        and current_time >= session.cutoff_at
        and session.cutoff_recorded_at is None
    ):
        session = AssessmentSession.objects.select_for_update().get(pk=session.pk)
        if session.cutoff_recorded_at is None:
            _record_cutoff_snapshot(session, current_time, mark_overtime=True)
    return AssessmentSession.objects.get(pk=session.pk)


@transaction.atomic
def start_saturday_assessment(
    week_start: date | None = None,
    now=None,
) -> AssessmentSession:
    """Start once per pool, or return the same session for a safe resume."""

    current_time = _now(now)
    start = week_start_for(week_start or timezone.localdate())
    existing_pool = AssessmentPool.objects.filter(week_start=start).first()
    existing_session = (
        AssessmentSession.objects.filter(pool=existing_pool).first()
        if existing_pool
        else None
    )
    pool = existing_pool or generate_saturday_assessment_pool(start)
    if existing_session:
        _ensure_session_responses(existing_session)
        return refresh_assessment_session(existing_session, current_time)
    if not pool.selections.exists():
        raise AssessmentUnavailable("No Problems are available for this assessment yet.")

    session, _created = AssessmentSession.objects.get_or_create(
        pool=pool,
        defaults={
            "duration_minutes": pool.duration_minutes,
            "started_at": current_time,
            "cutoff_at": current_time + timedelta(minutes=pool.duration_minutes),
        },
    )
    _ensure_session_responses(session)
    session = refresh_assessment_session(session, current_time)
    return session


def _summary_for_rows(rows: list[dict]) -> dict:
    outcomes = [choice for choice, _label in AssessmentResponse.Outcome.choices]
    summary = {
        difficulty: {
            "total": 0,
            **{outcome: 0 for outcome in outcomes},
        }
        for difficulty in (
            AssessmentSelection.SlotKind.EASY,
            AssessmentSelection.SlotKind.MEDIUM,
        )
    }
    summary["total"] = 0
    summary["solved"] = 0
    for row in rows:
        difficulty = row.get("difficulty")
        if difficulty not in summary:
            continue
        outcome = row.get("outcome") or AssessmentResponse.Outcome.NOT_STARTED
        if outcome not in summary[difficulty]:
            outcome = AssessmentResponse.Outcome.NOT_STARTED
        summary[difficulty]["total"] += 1
        summary[difficulty][outcome] += 1
        summary["total"] += 1
        if outcome == AssessmentResponse.Outcome.SOLVED:
            summary["solved"] += 1
    return summary


def _row_is_fallback(row: dict) -> bool:
    """Recognize fallback snapshots created before or after this slice."""

    return row.get("is_fallback", False) or row.get(
        "source_kind"
    ) == AssessmentSelection.SourceKind.OLDER_CONCEPT_FALLBACK


def _summary_with_fallback(rows: list[dict]) -> dict:
    current_rows = [row for row in rows if not _row_is_fallback(row)]
    fallback_rows = [row for row in rows if _row_is_fallback(row)]
    summary = _summary_for_rows(current_rows)
    summary["fallback"] = _summary_for_rows(fallback_rows)
    return summary


def _live_response_rows(session: AssessmentSession) -> list[dict]:
    return [
        _response_snapshot(response)
        for response in session.responses.select_related("selection__problem").order_by(
            "selection__position", "id"
        )
    ]


def get_assessment_summary(session: AssessmentSession) -> dict:
    """Return current-week and fallback results for timed and final states."""

    timed_rows = session.cutoff_snapshot.get("responses", [])
    final_rows = _live_response_rows(session)
    return {
        "timed": _summary_with_fallback(timed_rows),
        "final": _summary_with_fallback(final_rows),
        "submitted_after_cutoff": bool(
            session.submitted_at and session.submitted_at >= session.cutoff_at
        ),
        "overtime_minutes": (
            max(0, int((session.submitted_at - session.cutoff_at).total_seconds() // 60))
            if session.submitted_at and session.submitted_at >= session.cutoff_at
            else 0
        ),
    }


@transaction.atomic
def save_assessment_response(
    session: AssessmentSession,
    position: int,
    *,
    draft_answer: str = "",
    outcome: str = AssessmentResponse.Outcome.NOT_STARTED,
    result_note: str = "",
    now=None,
) -> AssessmentResponse:
    """Persist one Problem's answer and self-recorded outcome before navigation."""

    session = refresh_assessment_session(session, now)
    if not session.is_editable:
        raise AssessmentClosed("This assessment has already been submitted.")
    if outcome not in dict(AssessmentResponse.Outcome.choices):
        raise ValueError("Choose a valid Problem outcome.")
    response = session.responses.select_related("selection").get(
        selection__position=position
    )
    response.draft_answer = draft_answer
    response.outcome = outcome
    response.result_note = result_note
    response.save(update_fields=("draft_answer", "outcome", "result_note", "updated_at"))
    return response


@transaction.atomic
def navigate_assessment(
    session: AssessmentSession,
    position: int,
    now=None,
) -> AssessmentSession:
    """Move the active Problem while retaining all response rows."""

    session = refresh_assessment_session(session, now)
    problem_count = session.pool.selections.count()
    if position < 1 or position > problem_count:
        raise ValueError("That assessment Problem does not exist.")
    if not session.is_editable:
        return session
    session.current_position = position
    session.save(update_fields=("current_position", "updated_at"))
    return session


@transaction.atomic
def submit_assessment(session: AssessmentSession, now=None) -> AssessmentSession:
    """Freeze a final result, retaining a separate timed cutoff result."""

    current_time = _now(now)
    session = refresh_assessment_session(session, current_time)
    if session.status == AssessmentSession.Status.COMPLETED:
        return session
    if session.cutoff_recorded_at is None:
        _record_cutoff_snapshot(
            session,
            current_time,
            mark_overtime=current_time >= session.cutoff_at,
        )
        session.refresh_from_db()
    session.submitted_at = current_time
    session.status = AssessmentSession.Status.COMPLETED
    session.final_summary = get_assessment_summary(session)
    session.save(
        update_fields=("submitted_at", "status", "final_summary", "updated_at")
    )
    return session
