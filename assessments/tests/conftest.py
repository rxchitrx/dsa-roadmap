import pytest
from django.db import connection

from assessments.models import (
    AssessmentPool,
    AssessmentResponse,
    AssessmentSelection,
    AssessmentSession,
)


@pytest.fixture(autouse=True)
def ensure_assessment_tables(transactional_db):
    """Keep this app testable before shared settings/URL wiring is integrated."""

    existing_tables = connection.introspection.table_names()
    created_models = []
    with connection.schema_editor() as schema_editor:
        for model in (
            AssessmentPool,
            AssessmentSelection,
            AssessmentSession,
            AssessmentResponse,
        ):
            if model._meta.db_table not in existing_tables:
                schema_editor.create_model(model)
                created_models.append(model)

    yield

    # The isolated app is intentionally not in INSTALLED_APPS yet, so normal
    # pytest-django flushing does not know about these tables.
    AssessmentResponse.objects.all().delete()
    AssessmentSession.objects.all().delete()
    AssessmentSelection.objects.all().delete()
    AssessmentPool.objects.all().delete()
