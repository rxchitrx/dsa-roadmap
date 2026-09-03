import json
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from assessments.models import AssessmentMistake, AssessmentResponse, AssessmentSession
from curriculum.models import Concept, Topic
from planner.backup import export_backup_json
from planner.models import StudyBlock, StudyBlockProblem
from planner.services import week_start_for
from practice.models import (
    LearningStatus,
    PracticeRun,
    ProblemLearningStatus,
    SolutionReflection,
)
from problems.models import Problem
from progress.models import ConceptCheckpoint, ConceptNote
from reviews.models import ProblemReview, ProblemReviewEvent, ReviewRating


def _concept():
    topic = Topic.objects.create(
        name="Dogfood Arrays",
        slug="dogfood-arrays",
        description="A small fixture for the full weekly loop.",
        display_order=1,
    )
    return Concept.objects.create(
        topic=topic,
        name="Invariant tracing",
        slug="dogfood-invariant-tracing",
        order=1,
        summary="Keep one useful fact true while scanning.",
        intuition="A loop becomes easier to trust when its invariant is explicit.",
        explanation="State what is true before and after each iteration.",
        examples=[
            {
                "title": "Running maximum",
                "input": "[3, 1, 5]",
                "output": "5",
                "walkthrough": "The best value seen so far stays true after each item.",
            }
        ],
        complexity_notes="A single scan is O(n) time and O(1) extra space.",
        implementation_guidance="Write the invariant before choosing the update order.",
        common_traps="Do not read the updated state as if it were the old state.",
        guided_practice="Trace an empty list and a one-item list before coding.",
        checkpoint="Explain the invariant and one boundary case without looking.",
    )


def _problem(concept, *, title, slug, difficulty, display_order):
    return Problem.objects.create(
        concept=concept,
        title=title,
        slug=slug,
        statement=f"Solve {title} with a clear invariant.",
        difficulty=difficulty,
        source_name="Dogfood fixture",
        source_problem_id=slug,
        display_order=display_order,
    )


@pytest.mark.django_db(transaction=True)
def test_complete_weekly_loop_across_every_persisted_surface(client, tmp_path, settings):
    """Exercise one realistic week through the same routes a learner uses."""

    concept = _concept()
    easy = _problem(
        concept,
        title="Invariant Easy",
        slug="dogfood-invariant-easy",
        difficulty=Problem.Difficulty.EASY,
        display_order=1,
    )
    medium_one = _problem(
        concept,
        title="Invariant Medium One",
        slug="dogfood-invariant-medium-one",
        difficulty=Problem.Difficulty.MEDIUM,
        display_order=2,
    )
    medium_two = _problem(
        concept,
        title="Invariant Medium Two",
        slug="dogfood-invariant-medium-two",
        difficulty=Problem.Difficulty.MEDIUM,
        display_order=3,
    )

    today = timezone.localdate()
    week_start = week_start_for(today)
    next_week = week_start + timedelta(days=7)

    # Planning: generate the default week, then load Today so the real
    # recommendation/assignment hooks populate the learner's current blocks.
    generated = client.post(reverse("planner:generate_weekly_routine"))
    assert generated.status_code == 302
    assert StudyBlock.objects.filter(week_start=week_start).count() == 37
    today_page = client.get(reverse("planner:today"))
    assert today_page.status_code == 200
    concept_block = StudyBlock.objects.get(
        week_start=week_start,
        routine_key=f"{today.weekday()}-concept",
    )
    assert concept_block.assigned_concept_id == concept.pk

    # Concept learning/checkpoint: complete the assigned concept block with a
    # real timer route, then persist personal notes and recall evidence.
    started = client.post(
        reverse("planner:start_timer", args=[concept_block.pk]),
    )
    assert started.status_code == 302
    stopped = client.post(
        reverse("planner:stop_timer", args=[concept_block.pk]),
        {"complete_block": "1"},
    )
    assert stopped.status_code == 302
    concept_block.refresh_from_db()
    assert concept_block.status == StudyBlock.Status.COMPLETED

    progress_url = reverse(
        "progress:concept_progress",
        kwargs={"concept_slug": concept.slug},
    )
    assert client.post(
        progress_url,
        {
            "action": "notes",
            "body": "The invariant describes the useful fact after every scan step.",
        },
    ).status_code == 302
    assert client.post(
        progress_url,
        {
            "action": "checkpoint",
            "confidence": ConceptCheckpoint.Confidence.CONFIDENT,
            "recall_response": "I can state the invariant and trace the boundary cases.",
        },
    ).status_code == 302
    assert ConceptNote.objects.filter(concept=concept).exists()
    assert ConceptCheckpoint.objects.filter(concept=concept).count() == 1

    # Problem work: save a draft, run a failing attempt, run a passing attempt
    # with a visible custom case, write the reflection, and explicitly label
    # the learning status.
    editor_url = reverse("practice:editor", kwargs={"slug": easy.slug})
    editor = client.get(editor_url)
    assert editor.status_code == 200
    draft = editor.context["draft"]
    draft_response = client.post(
        reverse("practice:save_draft", kwargs={"slug": easy.slug}),
        data=json.dumps(
            {
                "code": "def dogfood_invariant_easy(data):\n    return False\n",
                "base_revision": draft.revision,
            }
        ),
        content_type="application/json",
    )
    assert draft_response.status_code == 200
    failed_run = client.post(
        reverse("practice:run_tests", kwargs={"slug": easy.slug}),
        data=json.dumps(
            {
                "code": "def dogfood_invariant_easy(data):\n    return False\n",
                "custom_tests": [
                    {
                        "label": "truthy input",
                        "input_data": [[1]],
                        "expected_output": True,
                    }
                ],
            }
        ),
        content_type="application/json",
    )
    assert failed_run.status_code == 200
    assert failed_run.json()["status"] == PracticeRun.Status.ASSERTION_FAILURE
    passing_code = (
        "def dogfood_invariant_easy(data):\n"
        "    return bool(data)\n"
    )
    passing_run = client.post(
        reverse("practice:run_tests", kwargs={"slug": easy.slug}),
        data=json.dumps(
            {
                "code": passing_code,
                "custom_tests": [
                    {
                        "label": "truthy input",
                        "input_data": [[1]],
                        "expected_output": True,
                    }
                ],
            }
        ),
        content_type="application/json",
    )
    assert passing_run.status_code == 200
    passing_payload = passing_run.json()
    assert passing_payload["status"] == PracticeRun.Status.PASSED
    practice_run = PracticeRun.objects.get(pk=passing_payload["id"])
    reflection_url = reverse(
        "practice:reflection",
        kwargs={"slug": easy.slug, "run_id": practice_run.pk},
    )
    assert client.post(
        reflection_url,
        {
            "rewritten_approach": "Track the invariant and return whether the input has evidence.",
            "complexity": "O(n) time and O(1) extra space for the scan.",
            "mistake_cause": "I returned a constant before tracing the input.",
            "next_correction": "Write one truthy and one empty trace before coding.",
            "notes": "The test made the missing invariant obvious.",
        },
    ).status_code == 302
    assert client.post(
        reverse("practice:update_learning_status", kwargs={"slug": easy.slug}),
        {
            "status": LearningStatus.SOLVED_INDEPENDENTLY,
            "reason": "I reproduced the invariant and passed the visible case after reflection.",
        },
    ).status_code == 302
    assert SolutionReflection.objects.filter(practice_run=practice_run).exists()
    assert ProblemLearningStatus.objects.get(problem=easy).status == (
        LearningStatus.SOLVED_INDEPENDENTLY
    )

    # The completed concept evidence now unlocks weekday Problem assignment and
    # the Saturday pool.
    client.get(reverse("planner:today"))
    assert set(
        StudyBlockProblem.objects.filter(study_block__week_start=week_start)
        .values_list("problem_id", flat=True)
    ) == {easy.pk, medium_one.pk, medium_two.pk}

    # Weekday review queue: create a review through the public page, make the
    # next revisit due for this dogfood run, then rate it again.
    review_url = reverse("reviews:problem_review", kwargs={"slug": easy.slug})
    assert client.post(
        review_url,
        {
            "rating": ReviewRating.COULD_NOT_SOLVE,
            "note": "The invariant was not available on the first recall.",
        },
    ).status_code == 302
    easy_review = ProblemReview.objects.get(problem=easy)
    easy_review.due_at = timezone.now() - timedelta(minutes=1)
    easy_review.save(update_fields=("due_at", "updated_at"))
    queue = client.get(reverse("reviews:due_queue"))
    assert queue.status_code == 200
    assert easy.title in queue.content.decode()
    assert client.post(
        review_url,
        {
            "rating": ReviewRating.SOLVED_WITH_HELP,
            "note": "I could recall the invariant with one prompt.",
        },
    ).status_code == 302
    assert ProblemReviewEvent.objects.filter(review=easy_review).count() == 2

    # Sunday batch: use a second due review so the batch has a live item after
    # the weekday queue has been cleared.
    sunday_review_url = reverse(
        "reviews:problem_review", kwargs={"slug": medium_one.slug}
    )
    client.post(
        sunday_review_url,
        {"rating": ReviewRating.COULD_NOT_SOLVE, "note": "Need another pass."},
    )
    medium_review = ProblemReview.objects.get(problem=medium_one)
    medium_review.due_at = timezone.now() - timedelta(minutes=1)
    medium_review.save(update_fields=("due_at", "updated_at"))
    sunday_page = client.get(reverse("reviews:sunday_batch"), {"count": 1})
    assert sunday_page.status_code == 200
    assert sunday_page.context["batch_count"] == 1
    assert sunday_page.content.decode().count('data-testid="sunday-review-item"') == 1
    sunday_saved = client.post(
        reverse("reviews:sunday_batch"),
        {
            "count": 1,
            "problem": medium_one.slug,
            "rating": ReviewRating.SOLVED_INDEPENDENTLY,
            "note": "The second recall was independent.",
        },
    )
    assert sunday_saved.status_code == 302
    assert ProblemReviewEvent.objects.filter(review=medium_review).count() == 2

    # Saturday assessment: build the real pool, start an already-expired
    # session to force the cutoff snapshot, continue in overtime, submit, and
    # complete the generated mistake review.
    pool_page = client.get(
        reverse("assessments:saturday_pool"),
        {"week": week_start.isoformat()},
    )
    assert pool_page.status_code == 200
    assert pool_page.context["pool"].selected_count == 3
    start_at = timezone.now() - timedelta(minutes=100)
    from assessments.services import start_saturday_assessment

    session = start_saturday_assessment(week_start, start_at)
    session_url = reverse(
        "assessments:assessment_session", kwargs={"session_id": session.pk}
    )
    overtime_page = client.get(session_url)
    assert overtime_page.status_code == 200
    session.refresh_from_db()
    assert session.status == AssessmentSession.Status.OVERTIME
    selections = list(session.pool.selections.order_by("position"))
    responses = [
        (selections[0], AssessmentResponse.Outcome.SOLVED, "easy solution"),
        (selections[1], AssessmentResponse.Outcome.NEEDS_REVIEW, "stuck on the edge"),
        (selections[2], AssessmentResponse.Outcome.SOLVED, "medium solution"),
    ]
    for index, (_selection, outcome, answer) in enumerate(responses, start=1):
        action = "submit" if index == len(responses) else "next"
        payload = {
            "action": action,
            "draft_answer": answer,
            "outcome": outcome,
        }
        if action == "next":
            payload["target_position"] = str(index + 1)
        submitted = client.post(session_url, payload)
        assert submitted.status_code == 302
    session.refresh_from_db()
    assert session.status == AssessmentSession.Status.COMPLETED
    assert session.cutoff_recorded_at is not None
    assert session.submitted_at >= session.cutoff_at
    assert AssessmentMistake.objects.filter(assessment=session).count() == 1
    mistake = AssessmentMistake.objects.get(assessment=session)
    mistakes_url = reverse(
        "assessments:assessment_mistakes", kwargs={"session_id": session.pk}
    )
    mistake_page = client.get(mistakes_url)
    assert mistake_page.status_code == 200
    assert client.post(
        mistakes_url,
        {
            "mistake": mistake.pk,
            "cause": AssessmentMistake.Cause.CONCEPT_GAP,
            "corrected_approach": "State the invariant before updating the pointers.",
            "next_action": "Re-solve this Problem tomorrow from a blank editor.",
            "action": "complete",
        },
    ).status_code == 302
    mistake.refresh_from_db()
    assert mistake.is_complete is True

    # Weekly summary: all of the completed evidence is reachable from the
    # selected week and the assessment result links to a clean mistake state.
    summary_url = reverse("planner:weekly_summary")
    summary = client.get(summary_url, {"week": week_start.isoformat()})
    assert summary.status_code == 200
    summary_context = summary.context["summary"]
    assert summary_context["practice"]["run_count"] == 2
    assert summary_context["practice"]["passed_count"] == 1
    assert summary_context["reviews"]["completed_count"] >= 4
    assert summary_context["assessment"]["is_complete"] is True
    assert summary_context["assessment"]["mistakes_remaining"] == 0

    # Next-week planning: preview without writing, then save an edited block.
    preview = client.get(
        reverse("planner:next_week_plan"),
        {"week": next_week.isoformat()},
    )
    assert preview.status_code == 200
    assert preview.context["plan"].week_start == next_week
    saved_plan = client.post(
        reverse("planner:save_next_week_plan"),
        {
            "week": next_week.isoformat(),
            "block__0-review__title": "Dogfood next week review",
            "block__0-review__planned_minutes": "25",
            "block__0-review__date": next_week.isoformat(),
        },
    )
    assert saved_plan.status_code == 200
    assert StudyBlock.objects.get(
        week_start=next_week,
        routine_key="0-review",
    ).title == "Dogfood next week review"

    # Secondary CSV export and canonical JSON backup/restore.
    csv_response = client.get(
        reverse("planner:weekly_csv_export"),
        {"week": week_start.isoformat()},
    )
    assert csv_response.status_code == 200
    assert csv_response["Content-Type"] == "text/csv; charset=utf-8"
    assert b"practice_run" in csv_response.content
    assert b"assessment_response" in csv_response.content

    settings.DSA_BACKUP_DIR = tmp_path
    backup_payload = export_backup_json()
    marker = StudyBlock.objects.create(
        date=week_start,
        week_start=week_start,
        routine_key="dogfood-marker",
        title="Must disappear after restore",
        planned_minutes=5,
    )
    restored = client.post(
        reverse("planner:backup_restore"),
        {
            "backup": SimpleUploadedFile(
                "dogfood.json",
                backup_payload.encode("utf-8"),
                content_type="application/json",
            )
        },
    )
    assert restored.status_code == 200
    assert 'data-testid="backup-restored"' in restored.content.decode()
    assert not StudyBlock.objects.filter(pk=marker.pk).exists()
    assert PracticeRun.objects.filter(problem__slug=easy.slug).count() == 2
    assert AssessmentSession.objects.filter(pk=session.pk).exists()
