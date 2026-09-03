from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from curriculum.models import Concept

from .forms import ConceptCheckpointForm, ConceptNoteForm
from .models import ConceptCheckpoint, ConceptNote


def _progress_context(
    concept,
    *,
    note_form=None,
    checkpoint_form=None,
    note=None,
    latest_checkpoint=None,
):
    note = note if note is not None else ConceptNote.objects.filter(concept=concept).first()
    latest_checkpoint = (
        latest_checkpoint
        if latest_checkpoint is not None
        else ConceptCheckpoint.objects.filter(concept=concept).first()
    )
    return {
        "concept": concept,
        "note": note,
        "latest_checkpoint": latest_checkpoint,
        "note_form": note_form or ConceptNoteForm(instance=note),
        "checkpoint_form": checkpoint_form or ConceptCheckpointForm(),
    }


@require_http_methods(["GET", "POST"])
def concept_progress(request, concept_slug):
    concept = get_object_or_404(
        Concept.objects.select_related("topic"),
        slug=concept_slug,
    )
    note = ConceptNote.objects.filter(concept=concept).first()

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "notes":
            note_form = ConceptNoteForm(request.POST, instance=note)
            if note_form.is_valid():
                saved_note = note_form.save(commit=False)
                saved_note.concept = concept
                saved_note.save()
                return redirect("progress:concept_progress", concept_slug=concept.slug)
            return render(
                request,
                "progress/concept_progress.html",
                _progress_context(
                    concept,
                    note_form=note_form,
                    note=note,
                ),
            )

        if action == "checkpoint":
            checkpoint_form = ConceptCheckpointForm(request.POST)
            if checkpoint_form.is_valid():
                checkpoint = checkpoint_form.save(commit=False)
                checkpoint.concept = concept
                checkpoint.save()
                return redirect("progress:concept_progress", concept_slug=concept.slug)
            return render(
                request,
                "progress/concept_progress.html",
                _progress_context(
                    concept,
                    checkpoint_form=checkpoint_form,
                    note=note,
                ),
            )

        return HttpResponseBadRequest("Choose a progress action.")

    return render(
        request,
        "progress/concept_progress.html",
        _progress_context(concept, note=note),
    )
