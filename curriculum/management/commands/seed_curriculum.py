
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Max

from curriculum.models import Concept, Topic
from curriculum.roadmap_content import ROADMAP_TOPICS


def _concepts_by_slug():
    return {
        concept["slug"]: concept
        for topic in ROADMAP_TOPICS
        for concept in topic["concepts"]
    }


_ALL_CONCEPTS = _concepts_by_slug()
_ARRAYS_TOPIC = next(topic for topic in ROADMAP_TOPICS if topic["slug"] == "arrays-strings")

# Keep the original three-lesson invocation stable for existing local fixtures.
# The --full option is the durable roadmap seed used by the application/content pack.
SEED_TOPIC = {
    key: value for key, value in _ARRAYS_TOPIC.items() if key != "concepts"
}
SEED_CONCEPTS = [
    {
        **_ALL_CONCEPTS[slug],
        "topic_slug": SEED_TOPIC["slug"],
        "order": order,
    }
    for order, slug in enumerate(
        ("array-fundamentals", "array-traversal", "two-pointers"),
        start=1,
    )
]


def _seed_topics(topic_payloads):
    payload_slugs = {
        concept["slug"]
        for topic_data in topic_payloads
        for concept in topic_data["concepts"]
    }
    existing = list(Concept.objects.filter(slug__in=payload_slugs).only("id"))
    if existing:
        temporary_order = (
            Concept.objects.aggregate(max_order=Max("order"))["max_order"] or 0
        ) + len(existing) + 1
        for offset, concept in enumerate(existing):
            Concept.objects.filter(pk=concept.pk).update(
                order=temporary_order + offset
            )

    concepts = {}
    for topic_data in topic_payloads:
        topic, _ = Topic.objects.update_or_create(
            slug=topic_data["slug"],
            defaults={
                key: value
                for key, value in topic_data.items()
                if key not in {"slug", "concepts"}
            },
        )
        for concept_data in topic_data["concepts"]:
            seed = dict(concept_data)
            prerequisites = seed.pop("prerequisite_slugs")
            seed.pop("topic_slug", None)
            concept, _ = Concept.objects.update_or_create(
                slug=seed["slug"],
                defaults={"topic": topic, **seed},
            )
            concepts[concept.slug] = (concept, prerequisites)

    for slug, (concept, prerequisite_slugs) in concepts.items():
        concept.prerequisites.set(
            [
                concepts[prerequisite_slug][0]
                for prerequisite_slug in prerequisite_slugs
                if prerequisite_slug in concepts
            ]
        )
    return concepts


class Command(BaseCommand):
    help = "Seed the original DSA curriculum, or the complete roadmap with --full."

    def add_arguments(self, parser):
        parser.add_argument(
            "--full",
            action="store_true",
            help="Seed every ordered Topic and Concept in the roadmap manifest.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["full"]:
            topic_payloads = ROADMAP_TOPICS
            concepts = _seed_topics(topic_payloads)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Seeded full DSA roadmap with {len(topic_payloads)} topics and "
                    f"{len(concepts)} ordered concepts."
                )
            )
            return

        legacy_topic = {**SEED_TOPIC, "concepts": SEED_CONCEPTS}
        concepts = _seed_topics([legacy_topic])
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {SEED_TOPIC['name']} with {len(concepts)} ordered concepts."
            )
        )
