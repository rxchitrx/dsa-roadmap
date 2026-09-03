import pytest
from django.db import connection

from problems.models import Problem


@pytest.fixture(autouse=True)
def ensure_problem_table(transactional_db):
    """Make this slice testable before the app is wired into project settings."""

    table_name = Problem._meta.db_table
    existing_tables = connection.introspection.table_names()
    if table_name not in existing_tables:
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(Problem)

    yield

    # The app is intentionally not in INSTALLED_APPS for this isolated slice,
    # so Django's normal flush command doesn't know about this table yet.
    Problem.objects.all().delete()
