from django.core.validators import MinValueValidator
from django.db import models


class Problem(models.Model):
    """A source-specific DSA problem in the learner's local catalog."""

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    # Explicit app_label keeps this slice importable and testable before the
    # integrator adds ``problems`` to INSTALLED_APPS.
    class Meta:
        app_label = "problems"
        ordering = ("title", "id")
        indexes = [
            models.Index(fields=("difficulty", "is_active")),
            models.Index(fields=("concept", "is_active")),
        ]

    concept = models.ForeignKey(
        "curriculum.Concept",
        on_delete=models.SET_NULL,
        related_name="problems",
        blank=True,
        null=True,
    )
    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, unique=True)
    statement = models.TextField()
    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty.choices,
        blank=True,
    )
    source_name = models.CharField(max_length=100, blank=True)
    source_problem_id = models.CharField(max_length=100, blank=True)
    source_url = models.URLField(blank=True)
    examples = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    display_order = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title

    @property
    def has_metadata_warning(self) -> bool:
        return not self.concept_id or not self.difficulty or not self.source_name

    @property
    def metadata_warnings(self) -> list[str]:
        warnings = []
        if not self.concept_id:
            warnings.append("Needs concept classification")
        if not self.difficulty:
            warnings.append("Difficulty not set")
        if not self.source_name:
            warnings.append("Source not set")
        return warnings
