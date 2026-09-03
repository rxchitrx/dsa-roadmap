from django.shortcuts import render
from django.utils import timezone

from .models import StudyBlock


def today(request):
    today_date = timezone.localdate()
    study_block = (
        StudyBlock.objects.filter(date=today_date).order_by("id").first()
    )
    return render(
        request,
        "planner/today.html",
        {"today": today_date, "study_block": study_block},
    )
