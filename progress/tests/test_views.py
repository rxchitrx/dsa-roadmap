from django.urls import reverse
from django.utils import timezone
import pytest

from progress.models import ConceptCheckpoint, ConceptNote


@pytest.mark.django_db
def test_progress_page_shows_empty_state_for_a_concept(client, concept):
    response = client.get(
        reverse("progress:concept_progress", kwargs={"concept_slug": concept.slug})
    )

    assert response.status_code == 200
    assert response.context["note"] is None
    assert response.context["latest_checkpoint"] is None
    html = response.content.decode()
    assert 'data-testid="notes-empty"' in html
    assert 'data-testid="checkpoint-empty"' in html


@pytest.mark.django_db
def test_notes_can_be_created_edited_and_loaded_after_redirect(client, concept):
    url = reverse("progress:concept_progress", kwargs={"concept_slug": concept.slug})

    create_response = client.post(
        url,
        {"action": "notes", "body": "The window is the part I am tracking."},
    )

    assert create_response.status_code == 302
    note = ConceptNote.objects.get(concept=concept)
    note_id = note.pk
    created_at = note.created_at
    assert note.updated_at >= created_at

    loaded_response = client.get(url)
    assert loaded_response.status_code == 200
    assert "The window is the part I am tracking." in loaded_response.content.decode()

    edit_response = client.post(
        url,
        {"action": "notes", "body": "I track the window and its invariant."},
    )

    assert edit_response.status_code == 302
    note.refresh_from_db()
    assert note.pk == note_id
    assert note.body == "I track the window and its invariant."
    assert note.created_at == created_at
    assert note.updated_at >= created_at


@pytest.mark.django_db
def test_checkpoint_submission_is_timestamped_and_latest_result_is_visible(
    client, concept
):
    url = reverse("progress:concept_progress", kwargs={"concept_slug": concept.slug})

    first_response = client.post(
        url,
        {
            "action": "checkpoint",
            "confidence": "2",
            "recall_response": "I need a hint to state the invariant.",
        },
    )
    first_checkpoint = ConceptCheckpoint.objects.get(concept=concept)

    assert first_response.status_code == 302
    assert first_checkpoint.submitted_at <= timezone.now()

    second_response = client.post(
        url,
        {
            "action": "checkpoint",
            "confidence": "4",
            "recall_response": "I can state the invariant and choose the pointers.",
        },
    )

    assert second_response.status_code == 302
    assert ConceptCheckpoint.objects.filter(concept=concept).count() == 2
    latest = ConceptCheckpoint.objects.filter(concept=concept).first()
    assert latest.confidence == 4
    assert latest.recall_response == "I can state the invariant and choose the pointers."

    loaded_response = client.get(url)
    html = loaded_response.content.decode()
    assert 'data-testid="latest-checkpoint"' in html
    assert "I can state the invariant and choose the pointers." in html
    assert "Confident" in html


@pytest.mark.django_db
def test_checkpoint_requires_a_valid_confidence_and_recall_response(client, concept):
    url = reverse("progress:concept_progress", kwargs={"concept_slug": concept.slug})

    response = client.post(
        url,
        {
            "action": "checkpoint",
            "confidence": "9",
            "recall_response": "   ",
        },
    )

    assert response.status_code == 200
    assert ConceptCheckpoint.objects.count() == 0
    assert response.context["checkpoint_form"].errors
    assert "Select a valid choice" in response.content.decode()


@pytest.mark.django_db
def test_unknown_concept_progress_page_returns_not_found(client):
    response = client.get(
        reverse(
            "progress:concept_progress",
            kwargs={"concept_slug": "does-not-exist"},
        )
    )

    assert response.status_code == 404
