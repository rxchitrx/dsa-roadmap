from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render

from .models import Concept, Topic


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
