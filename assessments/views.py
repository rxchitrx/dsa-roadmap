from datetime import datetime

from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import AssessmentPool
from .services import generate_saturday_assessment_pool, week_start_for


def _parse_week_start(value):
    if not value:
        return timezone.localdate()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@require_GET
def saturday_pool(request):
    requested_date = _parse_week_start(request.GET.get("week"))
    if requested_date is None:
        return HttpResponseBadRequest("Use a valid week date in YYYY-MM-DD format.")

    week_start = week_start_for(requested_date)
    pool = generate_saturday_assessment_pool(week_start)
    pool = AssessmentPool.objects.prefetch_related(
        "selections__problem",
    ).get(pk=pool.pk)
    return render(
        request,
        "assessments/saturday_pool.html",
        {
            "pool": pool,
            "week_start": week_start,
            "selections": pool.selections.all(),
        },
    )
