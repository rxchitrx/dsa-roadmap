from django.contrib import messages
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .models import Concept, Topic
from .services import (
    PrerequisiteGraphError,
    add_prerequisite,
    recommend_next_concept,
    remove_prerequisite,
)


def curriculum_index(request):
    topics = Topic.objects.prefetch_related(
        Prefetch("concepts", queryset=Concept.objects.order_by("order", "id"))
    )
    return render(request, "curriculum/index.html", {"topics": topics})


def concept_detail(request, concept_slug):
    concept = get_object_or_404(
        Concept.objects.select_related("topic").prefetch_related(
            "prerequisites",
            "unlocks",
        ),
        slug=concept_slug,
    )
    return render(request, "curriculum/concept_detail.html", {"concept": concept})


def concept_recommendation(request):
    recommendation = recommend_next_concept()
    return render(
        request,
        "curriculum/recommendation.html",
        {"recommendation": recommendation},
    )


def prerequisite_graph(request):
    concepts = list(
        Concept.objects.select_related("topic")
        .prefetch_related("prerequisites")
        .order_by("topic__display_order", "topic_id", "order", "id")
    )
    return render(
        request,
        "curriculum/prerequisite_graph.html",
        {"concepts": concepts},
    )


def _posted_concept(request, field_name: str) -> Concept:
    value = request.POST.get(field_name, "").strip()
    try:
        concept_id = int(value)
    except (TypeError, ValueError) as exc:
        raise PrerequisiteGraphError(
            "Choose both a concept and a prerequisite, then try again."
        ) from exc

    try:
        return Concept.objects.select_related("topic").get(pk=concept_id)
    except Concept.DoesNotExist as exc:
        raise PrerequisiteGraphError(
            "That concept is no longer available. Refresh the graph and try again."
        ) from exc


@require_POST
def add_prerequisite_edge(request):
    try:
        concept = _posted_concept(request, "concept_id")
        prerequisite = _posted_concept(request, "prerequisite_id")
        added = add_prerequisite(concept=concept, prerequisite=prerequisite)
    except PrerequisiteGraphError as exc:
        messages.error(request, str(exc))
    else:
        if added:
            messages.success(
                request,
                f"Prerequisite added: {prerequisite.name} → {concept.name}.",
            )
        else:
            messages.info(
                request,
                f"{prerequisite.name} is already a prerequisite for {concept.name}.",
            )
    return redirect("curriculum:prerequisite_graph")


@require_POST
def remove_prerequisite_edge(request):
    try:
        concept = _posted_concept(request, "concept_id")
        prerequisite = _posted_concept(request, "prerequisite_id")
        removed = remove_prerequisite(concept=concept, prerequisite=prerequisite)
    except PrerequisiteGraphError as exc:
        messages.error(request, str(exc))
    else:
        if removed:
            messages.success(
                request,
                f"Prerequisite removed: {prerequisite.name} → {concept.name}.",
            )
        else:
            messages.info(
                request,
                "That prerequisite was already removed. Refresh the graph to see the latest edges.",
            )
    return redirect("curriculum:prerequisite_graph")
