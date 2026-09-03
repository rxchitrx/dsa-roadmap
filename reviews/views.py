from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from problems.models import Problem

from .forms import ReviewRatingForm, SundayReviewBatchForm
from .models import ProblemReview
from .services import (
    SUNDAY_REVIEW_DEFAULT_COUNT,
    due_review_queue,
    record_review,
    sunday_review_batch,
)


def due_queue(request):
    """Show every active Problem Review due for the current moment."""

    due_reviews = due_review_queue()
    return render(
        request,
        "reviews/due_queue.html",
        {
            "due_reviews": due_reviews,
            "queue_checked_at": timezone.now(),
        },
    )


@require_http_methods(["GET", "POST"])
def sunday_batch(request):
    """Run a configurable Sunday review batch through the shared rating flow."""

    raw_count = (
        request.POST.get("count")
        if request.method == "POST"
        else request.GET.get("count")
    )
    count_form = SundayReviewBatchForm(
        {"count": raw_count} if raw_count is not None else None
    )
    count = SUNDAY_REVIEW_DEFAULT_COUNT
    if count_form.is_valid():
        count = count_form.cleaned_data["count"]

    review_form = ReviewRatingForm(
        request.POST if request.method == "POST" else None
    )
    if request.method == "POST" and count_form.is_valid() and review_form.is_valid():
        problem = get_object_or_404(
            Problem,
            slug=request.POST.get("problem"),
            is_active=True,
        )
        record_review(
            problem,
            rating=review_form.cleaned_data["rating"],
            note=review_form.cleaned_data["note"],
        )
        batch_url = reverse("reviews:sunday_batch")
        return redirect(f"{batch_url}?count={count}&saved=1")

    return render(
        request,
        "reviews/sunday_batch.html",
        {
            "batch_reviews": sunday_review_batch(count=count),
            "batch_count": count,
            "count_form": count_form,
            "review_form": review_form,
            "review_saved": request.GET.get("saved") == "1",
            "batch_checked_at": timezone.now(),
        },
    )


@require_http_methods(["GET", "POST"])
def problem_review(request, slug):
    """Show the quick rating action and the Problem's review journal."""

    problem = get_object_or_404(
        Problem.objects.select_related("concept", "concept__topic"),
        slug=slug,
        is_active=True,
    )
    current_review = ProblemReview.objects.filter(problem=problem).first()
    form = ReviewRatingForm(request.POST if request.method == "POST" else None)

    if request.method == "POST" and form.is_valid():
        record_review(
            problem,
            rating=form.cleaned_data["rating"],
            note=form.cleaned_data["note"],
        )
        review_url = reverse("reviews:problem_review", kwargs={"slug": problem.slug})
        return redirect(f"{review_url}?saved=1")

    history = list(
        current_review.history.select_related("learning_status_event")
        if current_review is not None
        else []
    )
    learning_status = getattr(problem, "learning_status", None)
    return render(
        request,
        "reviews/problem_review.html",
        {
            "problem": problem,
            "current_review": current_review,
            "review_history": history,
            "learning_status": learning_status,
            "review_form": form,
            "review_saved": request.GET.get("saved") == "1",
        },
    )
