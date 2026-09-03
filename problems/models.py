from django.core.exceptions import ValidationError
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
    concepts = models.ManyToManyField(
        "curriculum.Concept",
        through="ProblemClassification",
        related_name="classified_problems",
        blank=True,
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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.concept_id:
            ProblemClassification.objects.get_or_create(
                problem=self,
                concept_id=self.concept_id,
                defaults={"status": ProblemClassification.Status.CONFIRMED},
            )

    def __str__(self) -> str:
        return self.title

    @property
    def has_metadata_warning(self) -> bool:
        return bool(self.metadata_warnings)

    @property
    def metadata_warnings(self) -> list[str]:
        warnings = []
        if not self.concept_id:
            warnings.append("Needs concept classification")
        if self.classification_warning_state == ProblemClassification.Status.UNCERTAIN:
            warnings.append("Concept classification is uncertain")
        elif self.classification_warning_state == ProblemClassification.Status.FALLBACK:
            warnings.append("Concept classification uses a fallback")
        elif self.classification_warning_state == "uncertain_and_fallback":
            warnings.extend(
                [
                    "Concept classification is uncertain",
                    "Concept classification uses a fallback",
                ]
            )
        if not self.difficulty:
            warnings.append("Difficulty not set")
        if not self.source_name:
            warnings.append("Source not set")
        return warnings

    @property
    def classification_warning_state(self) -> str | None:
        """Return the explicit warning state carried by this Problem's tags."""

        if not self.pk:
            return None

        warning_states = set(
            self.classifications.filter(
                status__in=(
                    ProblemClassification.Status.UNCERTAIN,
                    ProblemClassification.Status.FALLBACK,
                )
            ).values_list("status", flat=True)
        )
        if {
            ProblemClassification.Status.UNCERTAIN,
            ProblemClassification.Status.FALLBACK,
        }.issubset(warning_states):
            return "uncertain_and_fallback"
        if ProblemClassification.Status.UNCERTAIN in warning_states:
            return ProblemClassification.Status.UNCERTAIN
        if ProblemClassification.Status.FALLBACK in warning_states:
            return ProblemClassification.Status.FALLBACK
        return None

    @property
    def has_classification_warning(self) -> bool:
        return self.classification_warning_state is not None


class ProblemClassification(models.Model):
    """A Concept tag for a Problem, with provenance confidence."""

    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        UNCERTAIN = "uncertain", "Uncertain"
        FALLBACK = "fallback", "Fallback"

    problem = models.ForeignKey(
        Problem,
        on_delete=models.CASCADE,
        related_name="classifications",
    )
    concept = models.ForeignKey(
        "curriculum.Concept",
        on_delete=models.CASCADE,
        related_name="problem_classifications",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )
    note = models.CharField(
        max_length=500,
        blank=True,
        help_text="Explain why an uncertain or fallback classification was chosen.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("concept__topic", "concept__order", "concept__name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("problem", "concept"),
                name="unique_problem_concept_classification",
            ),
        ]
        indexes = [
            models.Index(fields=("problem", "status")),
            models.Index(fields=("concept", "status")),
        ]

    def __str__(self) -> str:
        return f"{self.problem.title} → {self.concept.name} ({self.get_status_display()})"

    @property
    def is_warning(self) -> bool:
        return self.status in {
            self.Status.UNCERTAIN,
            self.Status.FALLBACK,
        }

    def clean(self) -> None:
        super().clean()
        if self.is_warning and not (self.note or "").strip():
            raise ValidationError(
                {"note": "Add a reason for an uncertain or fallback classification."}
            )
