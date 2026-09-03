import pytest
from django.utils import timezone

from progress.models import ConceptCheckpoint, ConceptNote


@pytest.mark.django_db
def test_note_and_checkpoint_reference_a_concept_and_record_timestamps(concept):
    note = ConceptNote.objects.create(concept=concept, body="An index names a position.")
    checkpoint = ConceptCheckpoint.objects.create(
        concept=concept,
        confidence=ConceptCheckpoint.Confidence.SOLID,
        recall_response="I can explain the invariant before I code.",
    )

    assert note.concept == concept
    assert note.created_at <= note.updated_at
    assert checkpoint.concept == concept
    assert checkpoint.submitted_at <= timezone.now()
    assert list(concept.checkpoints.all()) == [checkpoint]
