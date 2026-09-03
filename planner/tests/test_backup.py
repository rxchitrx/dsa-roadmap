import copy
import json
from datetime import date, timedelta

import pytest
from django.utils import timezone

from assessments.models import (
    AssessmentMistake,
    AssessmentPool,
    AssessmentResponse,
    AssessmentSelection,
    AssessmentSession,
)
from curriculum.models import Concept, Topic
from history.models import RunHistoryEntry
from practice.models import (
    CustomTestCase,
    LearningStatusEvent,
    PracticeRun,
    ProblemDraft,
    ProblemLearningStatus,
    SolutionReflection,
)
from problems.models import (
    CatalogSync,
    Problem,
    ProblemClassification,
    ProblemSnapshot,
)
from progress.models import ConceptCheckpoint, ConceptNote
from reviews.models import ProblemReview, ProblemReviewEvent, ReviewRating

from planner.backup import (
    BACKUP_VERSION,
    BackupRestoreError,
    BackupValidationError,
    export_backup,
    export_backup_json,
    restore_backup,
    validate_backup,
)
from planner.models import RestDay, StudyBlock, StudyBlockProblem, WorkSession


def _create_full_domain():
    topic = Topic.objects.create(
        name="Arrays",
        slug="arrays",
        description="Core array patterns.",
        display_order=1,
    )
    second_topic = Topic.objects.create(
        name="Hashing",
        slug="hashing",
        description="Hash-based lookup.",
        display_order=2,
    )
    first_concept = Concept.objects.create(
        topic=topic,
        name="Array traversal",
        slug="array-traversal",
        order=1,
        summary="Walk through a sequence.",
        intuition="Keep one clear invariant.",
        explanation="A traversal visits each relevant value.",
        examples=[{"input": [1, 2], "output": 3}],
        complexity_notes="Usually O(n).",
        implementation_guidance="Use a direct loop.",
        common_traps="Do not confuse indices and values.",
        guided_practice="Trace a two-element input.",
        checkpoint="Explain the invariant.",
    )
    second_concept = Concept.objects.create(
        topic=second_topic,
        name="Hash lookup",
        slug="hash-lookup",
        order=1,
        summary="Use a map for fast membership.",
        intuition="Trade memory for lookup speed.",
        explanation="A hash table maps keys to values.",
        examples=[{"input": [2, 7], "output": True}],
        complexity_notes="Average O(1) lookup.",
        implementation_guidance="Choose a meaningful key.",
        common_traps="Account for duplicate keys.",
        guided_practice="Compare a scan and a set.",
        checkpoint="State the expected complexity.",
    )
    second_concept.prerequisites.add(first_concept)

    problem = Problem.objects.create(
        concept=first_concept,
        title="Pair Sum",
        slug="pair-sum",
        statement="Find two values with a target sum.",
        difficulty=Problem.Difficulty.EASY,
        source_name="Local",
        source_problem_id="pair-1",
        source_url="https://example.com/pair-sum",
        examples=[{"input": [[2, 7], 9], "output": [0, 1]}],
        tags=["array", "hashing"],
        display_order=1,
    )
    ProblemClassification.objects.filter(problem=problem, concept=first_concept).update(
        note="Primary concept.",
    )
    second_problem = Problem.objects.create(
        title="Count Values",
        slug="count-values",
        statement="Count the values in a list.",
        difficulty=Problem.Difficulty.MEDIUM,
        source_name="Local",
        source_problem_id="count-1",
        source_url="https://example.com/count-values",
        examples=[{"input": [[1, 1]], "output": {"1": 2}}],
        tags=["hashing"],
        display_order=2,
    )
    ProblemClassification.objects.create(
        problem=second_problem,
        concept=second_concept,
        status=ProblemClassification.Status.FALLBACK,
        note="Fallback mapping retained from import.",
    )

    captured_at = timezone.now() - timedelta(days=3)
    ProblemSnapshot.objects.create(
        problem=problem,
        version=1,
        title="Pair Sum (old)",
        slug="pair-sum",
        statement="Old statement.",
        difficulty=Problem.Difficulty.EASY,
        source_name="Local",
        source_problem_id="pair-1",
        source_url="https://example.com/pair-sum",
        examples=[],
        tags=["old"],
        is_active=False,
        captured_at=captured_at,
    )
    active_snapshot = ProblemSnapshot.objects.create(
        problem=problem,
        version=2,
        title=problem.title,
        slug=problem.slug,
        statement=problem.statement,
        difficulty=problem.difficulty,
        source_name=problem.source_name,
        source_problem_id=problem.source_problem_id,
        source_url=problem.source_url,
        examples=problem.examples,
        tags=problem.tags,
        captured_at=timezone.now() - timedelta(days=1),
    )
    ProblemSnapshot.objects.create(
        problem=second_problem,
        version=1,
        title=second_problem.title,
        slug=second_problem.slug,
        statement=second_problem.statement,
        difficulty=second_problem.difficulty,
        source_name=second_problem.source_name,
        source_problem_id=second_problem.source_problem_id,
        source_url=second_problem.source_url,
        examples=second_problem.examples,
        tags=second_problem.tags,
    )
    CatalogSync.objects.create(
        source_name="Local",
        status=CatalogSync.Status.SUCCEEDED,
        finished_at=timezone.now(),
        last_success_at=timezone.now(),
        total_items=2,
        processed_items=2,
        imported_count=2,
    )

    week_start = date(2026, 8, 31)
    block = StudyBlock.objects.create(
        date=week_start,
        title="Learn one concept",
        planned_minutes=30,
        week_start=week_start,
        routine_key="0-concept",
        assigned_concept=first_concept,
        concept_assignment_source=StudyBlock.ConceptAssignmentSource.MANUAL,
        position=0,
        status=StudyBlock.Status.COMPLETED,
    )
    carried_block = StudyBlock.objects.create(
        date=week_start + timedelta(days=1),
        title="Carried review",
        planned_minutes=20,
        week_start=week_start,
        routine_key="carry-forward-1",
        carried_from=block,
        position=1,
        status=StudyBlock.Status.PENDING,
    )
    StudyBlockProblem.objects.create(
        study_block=block,
        problem=problem,
        position=0,
        assignment_source=StudyBlockProblem.AssignmentSource.MANUAL,
    )
    StudyBlockProblem.objects.create(
        study_block=carried_block,
        problem=second_problem,
        position=0,
    )
    started_at = timezone.now() - timedelta(minutes=25)
    WorkSession.objects.create(
        study_block=block,
        status=WorkSession.Status.STOPPED,
        started_at=started_at,
        last_resumed_at=started_at,
        stopped_at=timezone.now() - timedelta(minutes=1),
        elapsed_seconds=1440,
    )
    RestDay.objects.create(date=week_start + timedelta(days=6))

    ConceptNote.objects.create(concept=first_concept, body="My invariant notes.")
    ConceptCheckpoint.objects.create(
        concept=first_concept,
        confidence=ConceptCheckpoint.Confidence.SOLID,
        recall_response="I can explain the loop invariant.",
    )
    ProblemDraft.objects.create(
        problem=problem,
        starter_signature="def pair_sum(nums, target):",
        code="return []",
        revision=3,
    )
    CustomTestCase.objects.create(
        problem=problem,
        label="duplicate values",
        input_data=[[3, 3], 6],
        expected_output=[0, 1],
        position=1,
    )
    practice_run = PracticeRun.objects.create(
        problem=problem,
        code="return [0]",
        status=PracticeRun.Status.ASSERTION_FAILURE,
        passed_tests=0,
        total_tests=1,
        duration_ms=18,
        message="Expected two indices.",
        details=[{"label": "example", "passed": False}],
    )
    reflection = SolutionReflection.objects.create(
        practice_run=practice_run,
        rewritten_approach="Track the complement in a map.",
        complexity="O(n) time, O(n) space.",
        mistake_cause="I returned after the first value.",
        next_correction="Trace the duplicate case before coding.",
        notes="Review tomorrow.",
    )
    learning_status = ProblemLearningStatus.objects.create(
        problem=problem,
        status=ProblemLearningStatus.Status.ATTEMPTED,
        reason="The first attempt failed.",
    )
    status_event = LearningStatusEvent.objects.create(
        learning_status=learning_status,
        problem_snapshot=active_snapshot,
        practice_run=practice_run,
        reflection=reflection,
        status=ProblemLearningStatus.Status.ATTEMPTED,
        reason="Recorded the failed attempt.",
    )
    history_entry = practice_run.history_entry
    history_entry.problem_snapshot = active_snapshot
    history_entry.code_snapshot = practice_run.code
    history_entry.status = practice_run.status
    history_entry.result_summary = practice_run.summary
    history_entry.passed_tests = 0
    history_entry.total_tests = 1
    history_entry.duration_ms = 18
    history_entry.save()

    review = ProblemReview.objects.create(
        problem=problem,
        rating=ReviewRating.COULD_NOT_SOLVE,
        interval_days=1,
        due_at=timezone.now() + timedelta(days=1),
        review_count=1,
        last_reviewed_at=timezone.now(),
    )
    ProblemReviewEvent.objects.create(
        review=review,
        rating=ReviewRating.COULD_NOT_SOLVE,
        interval_days=1,
        reviewed_at=review.last_reviewed_at,
        due_at=review.due_at,
        note="Need another recall pass.",
        learning_status_event=status_event,
    )

    pool = AssessmentPool.objects.create(
        week_start=week_start,
        requested_problem_count=2,
        duration_minutes=90,
        rationale="Current week concepts.",
        eligibility_metadata={"fallback_included": True},
    )
    first_selection = AssessmentSelection.objects.create(
        pool=pool,
        problem=problem,
        position=1,
        slot_kind=AssessmentSelection.SlotKind.EASY,
        is_unseen=False,
        rationale="Current concept.",
        eligibility_metadata={"source_kind": "current_week_studied_concept"},
    )
    second_selection = AssessmentSelection.objects.create(
        pool=pool,
        problem=second_problem,
        position=2,
        slot_kind=AssessmentSelection.SlotKind.MEDIUM,
        rationale="Older concept fallback.",
        eligibility_metadata={"source_kind": "older_concept_fallback"},
    )
    assessment = AssessmentSession.objects.create(
        pool=pool,
        duration_minutes=90,
        started_at=timezone.now() - timedelta(minutes=100),
        cutoff_at=timezone.now() - timedelta(minutes=10),
        cutoff_recorded_at=timezone.now() - timedelta(minutes=9),
        current_position=2,
        status=AssessmentSession.Status.OVERTIME,
        cutoff_snapshot={"official": {"solved": 0}},
        final_summary={"final": {"solved": 1}},
    )
    response = AssessmentResponse.objects.create(
        session=assessment,
        selection=first_selection,
        draft_answer="def pair_sum(nums, target):\n    return []",
        outcome=AssessmentResponse.Outcome.NEEDS_REVIEW,
        result_note="Missed the complement lookup.",
        cutoff_draft_answer="return []",
        cutoff_outcome=AssessmentResponse.Outcome.NEEDS_REVIEW,
        cutoff_result_note="Timed result.",
        cutoff_recorded_at=assessment.cutoff_recorded_at,
    )
    AssessmentResponse.objects.create(
        session=assessment,
        selection=second_selection,
        outcome=AssessmentResponse.Outcome.SOLVED,
        result_note="Solved after the cutoff.",
    )
    AssessmentMistake.objects.create(
        assessment=assessment,
        response=response,
        problem=problem,
        cause=AssessmentMistake.Cause.CONCEPT_GAP,
        corrected_approach="Use a complement map.",
        next_action="Re-solve tomorrow.",
    )


@pytest.mark.django_db
def test_export_restore_round_trip_preserves_the_complete_journey(tmp_path):
    _create_full_domain()
    original = export_backup(exported_at=timezone.now())
    safety_path = tmp_path / "safety.json"

    result = restore_backup(original, safety_export_path=safety_path)

    restored = export_backup()
    assert restored["data"] == original["data"]
    assert restored["relations"] == original["relations"]
    assert restored["settings"] == original["settings"]
    assert result.safety_export_path == safety_path
    assert json.loads(safety_path.read_text(encoding="utf-8"))["data"] == original["data"]
    assert StudyBlock.objects.get(pk=2).carried_from_id == 1
    assert ProblemSnapshot.objects.filter(problem_id=1).count() == 2


@pytest.mark.django_db
def test_json_export_validates_and_preserves_schema_version():
    payload = json.loads(export_backup_json())

    validated = validate_backup(json.dumps(payload))

    assert validated["version"] == BACKUP_VERSION
    assert validated["data"] == payload["data"]


@pytest.mark.django_db
def test_invalid_backup_does_not_create_safety_export_or_change_data(tmp_path):
    _create_full_domain()
    before = export_backup()
    invalid = copy.deepcopy(before)
    invalid["version"] = BACKUP_VERSION + 1
    safety_path = tmp_path / "should-not-exist.json"

    with pytest.raises(BackupValidationError):
        restore_backup(invalid, safety_export_path=safety_path)

    assert export_backup()["data"] == before["data"]
    assert not safety_path.exists()


@pytest.mark.django_db
def test_database_failure_rolls_back_replacement_after_safety_export(tmp_path, monkeypatch):
    _create_full_domain()
    before = export_backup()
    safety_path = tmp_path / "safety.json"

    def fail_insert(_data):
        from django.db import IntegrityError

        raise IntegrityError("simulated insert failure")

    monkeypatch.setattr("planner.backup._insert_domain", fail_insert)
    with pytest.raises(BackupRestoreError):
        restore_backup(before, safety_export_path=safety_path)

    assert export_backup()["data"] == before["data"]
    assert safety_path.exists()
