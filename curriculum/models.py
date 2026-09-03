from django.core.validators import MinValueValidator
from django.db import models


class Topic(models.Model):
    """A broad DSA area containing an ordered set of concepts."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField()
    display_order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("display_order", "id")

    def __str__(self) -> str:
        return self.name


class Concept(models.Model):
    """A learner-facing lesson in a Topic's prerequisite sequence."""

    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="concepts",
    )
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160, unique=True)
    order = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    summary = models.CharField(max_length=240)
    intuition = models.TextField()
    explanation = models.TextField()
    examples = models.JSONField(default=list)
    complexity_notes = models.TextField()
    implementation_guidance = models.TextField()
    common_traps = models.TextField()
    guided_practice = models.TextField()
    checkpoint = models.TextField()
    prerequisites = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="unlocks",
    )

    class Meta:
        ordering = ("topic", "order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("topic", "order"),
                name="unique_concept_order_per_topic",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.topic.name}: {self.name}"
