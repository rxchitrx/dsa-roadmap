"""Versioned, local-first backup and restore for the learner journey.

The backup format is deliberately explicit instead of relying on Django's
fixture format.  Explicit model keys make the file reviewable, let us retain
primary keys and timestamps, and give restore a complete validation pass
before it creates the safety copy or touches the database.

This module is domain-only.  The eventual export/restore view can use
``export_backup_json`` and ``restore_backup`` without knowing about model
ordering or relationship details.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timezone as datetime_timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime, parse_time

from assessments.models import (
    AssessmentMistake,
    AssessmentPool,
    AssessmentResponse,
    AssessmentSelection,
    AssessmentSession,
)
from curriculum.models import Concept, Topic
from history.models import RunHistoryEntry
from practice.models import (
    CustomTestCase,
    LearningStatusEvent,
    PracticeRun,
    ProblemDraft,
    ProblemLearningStatus,
    SolutionReflection,
)
from problems.models import (
    CatalogSync,
    Problem,
    ProblemClassification,
    ProblemSnapshot,
)
from progress.models import ConceptCheckpoint, ConceptNote
from reviews.models import ProblemReview, ProblemReviewEvent

from .models import RestDay, StudyBlock, StudyBlockProblem, WorkSession


BACKUP_FORMAT = "dsa-roadmap-backup"
BACKUP_VERSION = 1


class BackupError(ValueError):
    """Base error for malformed or un-restorable backup data."""


class BackupValidationError(BackupError):
    """Raised before any filesystem or database mutation for bad input."""

    def __init__(self, message: str, *, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or [message]


class BackupRestoreError(BackupError):
    """Raised when a validated restore cannot be committed."""


@dataclass(frozen=True)
class ModelSpec:
    key: str
    model: type[models.Model]


@dataclass(frozen=True)
class RelationSpec:
    key: str
    through: type[models.Model]
    source_model_key: str
    target_model_key: str
    source_attname: str
    target_attname: str


@dataclass(frozen=True)
class RestoreResult:
    """Details returned after a successful atomic replacement."""

    safety_export_path: Path
    restored_counts: dict[str, int]


MODEL_SPECS = (
    ModelSpec("curriculum.topic", Topic),
    ModelSpec("curriculum.concept", Concept),
    ModelSpec("planner.studyblock", StudyBlock),
    ModelSpec("planner.studyblockproblem", StudyBlockProblem),
    ModelSpec("planner.restday", RestDay),
    ModelSpec("planner.worksession", WorkSession),
    ModelSpec("progress.conceptnote", ConceptNote),
    ModelSpec("progress.conceptcheckpoint", ConceptCheckpoint),
    ModelSpec("problems.problem", Problem),
    ModelSpec("problems.problemsnapshot", ProblemSnapshot),
    ModelSpec("problems.catalogsync", CatalogSync),
    ModelSpec("problems.problemclassification", ProblemClassification),
    ModelSpec("practice.problemdraft", ProblemDraft),
    ModelSpec("practice.customtestcase", CustomTestCase),
    ModelSpec("practice.practicerun", PracticeRun),
    ModelSpec("practice.solutionreflection", SolutionReflection),
    ModelSpec("practice.problemlearningstatus", ProblemLearningStatus),
    ModelSpec("practice.learningstatusevent", LearningStatusEvent),
    ModelSpec("history.runhistoryentry", RunHistoryEntry),
    ModelSpec("reviews.problemreview", ProblemReview),
    ModelSpec("reviews.problemreviewevent", ProblemReviewEvent),
    ModelSpec("assessments.assessmentpool", AssessmentPool),
    ModelSpec("assessments.assessmentselection", AssessmentSelection),
    ModelSpec("assessments.assessmentsession", AssessmentSession),
    ModelSpec("assessments.assessmentresponse", AssessmentResponse),
    ModelSpec("assessments.assessmentmistake", AssessmentMistake),
)

MODEL_SPEC_BY_KEY = {spec.key: spec for spec in MODEL_SPECS}

_CONCEPT_PREREQUISITES = Concept._meta.get_field("prerequisites")
RELATION_SPECS = (
    RelationSpec(
        key="curriculum.concept.prerequisites",
        through=_CONCEPT_PREREQUISITES.remote_field.through,
        source_model_key="curriculum.concept",
        target_model_key="curriculum.concept",
        source_attname="from_concept_id",
        target_attname="to_concept_id",
    ),
)
RELATION_SPEC_BY_KEY = {spec.key: spec for spec in RELATION_SPECS}

_SETTINGS_KEYS = ("time_zone", "language_code", "use_tz")


def _model_fields(model: type[models.Model]) -> tuple[models.Field, ...]:
    return tuple(model._meta.concrete_fields)


def _json_safe(value: Any) -> Any:
    """Return a detached JSON-compatible value or raise a clear error."""

    try:
        return json.loads(
            json.dumps(value, cls=DjangoJSONEncoder, allow_nan=False)
        )
    except (TypeError, ValueError) as exc:
        raise BackupError(f"Value is not JSON-compatible: {exc}") from exc


def _serialize_value(field: models.Field, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(field, models.DateTimeField):
        if not isinstance(value, datetime):
            raise BackupError(f"Expected datetime in {field.model._meta.label}." )
        return value.isoformat()
    if isinstance(field, models.DateField):
        if not isinstance(value, date):
            raise BackupError(f"Expected date in {field.model._meta.label}.")
        return value.isoformat()
    if isinstance(field, models.TimeField):
        if not isinstance(value, time):
            raise BackupError(f"Expected time in {field.model._meta.label}.")
        return value.isoformat()
    if isinstance(field, models.JSONField):
        return _json_safe(value)
    return value


def _parse_datetime_value(value: Any, *, field_name: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = parse_datetime(value)
    else:
        parsed = None
    if parsed is None:
        raise BackupValidationError(f"{field_name} must be an ISO datetime.")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, datetime_timezone.utc)
    return parsed


def _parse_date_value(value: Any, *, field_name: str) -> date:
    if isinstance(value, datetime):
        raise BackupValidationError(f"{field_name} must be an ISO date.")
    parsed = value if isinstance(value, date) else parse_date(value) if isinstance(value, str) else None
    if parsed is None:
        raise BackupValidationError(f"{field_name} must be an ISO date.")
    return parsed


def _parse_time_value(value: Any, *, field_name: str) -> time:
    parsed = value if isinstance(value, time) else parse_time(value) if isinstance(value, str) else None
    if parsed is None:
        raise BackupValidationError(f"{field_name} must be an ISO time.")
    return parsed


def _coerce_field_value(field: models.Field, value: Any, *, field_name: str) -> Any:
    if value is None:
        if not field.null:
            raise BackupValidationError(f"{field_name} cannot be null.")
        return None

    if isinstance(field, (models.ForeignKey, models.OneToOneField)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise BackupValidationError(f"{field_name} must be a positive integer id.")
        return value
    if isinstance(field, models.BooleanField):
        if not isinstance(value, bool):
            raise BackupValidationError(f"{field_name} must be true or false.")
        return value
    if isinstance(field, models.IntegerField):
        if isinstance(value, bool) or not isinstance(value, int):
            raise BackupValidationError(f"{field_name} must be an integer.")
    if isinstance(field, models.FloatField):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise BackupValidationError(f"{field_name} must be a number.")
    if isinstance(field, models.DateTimeField):
        return _parse_datetime_value(value, field_name=field_name)
    if isinstance(field, models.DateField):
        return _parse_date_value(value, field_name=field_name)
    if isinstance(field, models.TimeField):
        return _parse_time_value(value, field_name=field_name)
    if isinstance(field, models.JSONField):
        return _json_safe(value)
    if isinstance(field, (models.CharField, models.TextField, models.URLField)):
        if not isinstance(value, str):
            raise BackupValidationError(f"{field_name} must be text.")

    instance = field.model()
    try:
        return field.clean(value, instance)
    except ValidationError as exc:
        raise BackupValidationError(f"Invalid {field_name}: {exc}") from exc


def _load_json_input(source: Any) -> dict[str, Any]:
    if hasattr(source, "read"):
        source = source.read()
    if isinstance(source, (str, bytes, bytearray)):
        try:
            source = json.loads(
                source,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError(f"invalid JSON constant {value}")
                ),
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise BackupValidationError("Backup is not valid JSON.") from exc
    elif isinstance(source, os.PathLike):
        try:
            return _load_json_input(Path(source).read_text(encoding="utf-8"))
        except OSError as exc:
            raise BackupValidationError("Backup file could not be read.") from exc
    if not isinstance(source, Mapping):
        raise BackupValidationError("Backup must be a JSON object.")
    try:
        return copy.deepcopy(dict(source))
    except (TypeError, ValueError) as exc:
        raise BackupValidationError("Backup object could not be copied safely.") from exc


def _validate_unique_constraints(
    spec: ModelSpec,
    records: list[dict[str, Any]],
) -> None:
    model = spec.model
    unique_field_sets: list[tuple[tuple[str, ...], models.Q | None]] = []
    for field in _model_fields(model):
        if field.unique:
            unique_field_sets.append(((field.attname,), None))
    for fields in model._meta.unique_together:
        unique_field_sets.append(
            (
                tuple(
                    model._meta.get_field(field_name).attname
                    for field_name in fields
                ),
                None,
            )
        )
    for constraint in model._meta.constraints:
        if not isinstance(constraint, models.UniqueConstraint) or not constraint.fields:
            continue
        unique_field_sets.append(
            (
                tuple(
                    model._meta.get_field(field_name).attname
                    for field_name in constraint.fields
                ),
                constraint.condition,
            )
        )

    for field_names, condition in unique_field_sets:
        bucket: set[tuple[Any, ...]] = set()
        for record in records:
            if condition is not None and not _condition_matches(record, condition):
                continue
            values = tuple(record[field_name] for field_name in field_names)
            if any(value is None for value in values):
                continue
            if values in bucket:
                label = ", ".join(field_names)
                raise BackupValidationError(
                    f"{spec.key} contains duplicate values for {label}."
                )
            bucket.add(values)


def _condition_matches(record: Mapping[str, Any], condition: models.Q) -> bool:
    """Evaluate the simple Q conditions used by this project's constraints."""

    results = []
    for child in condition.children:
        if isinstance(child, models.Q):
            result = _condition_matches(record, child)
        else:
            lookup, expected = child
            parts = lookup.split("__")
            field_name = parts[0]
            actual = record.get(field_name)
            lookup_name = parts[1] if len(parts) > 1 else "exact"
            if lookup_name == "isnull":
                result = (actual is None) is bool(expected)
            elif lookup_name == "in":
                result = actual in expected
            elif lookup_name == "exact":
                result = actual == expected
            else:
                raise BackupValidationError(
                    f"Unsupported backup constraint lookup: {lookup}."
                )
        results.append(result)
    result = all(results) if condition.connector == models.Q.AND else any(results)
    return not result if condition.negated else result


def validate_backup(source: Any) -> dict[str, Any]:
    """Validate and normalize a backup without changing local state.

    The returned object is detached from the caller and contains Python model
    values (for example ``datetime`` objects) ready for the restore writer.
    """

    raw = _load_json_input(source)
    required = {"format", "version", "exported_at", "settings", "data", "relations"}
    missing = required - set(raw)
    unknown = set(raw) - required
    if missing or unknown:
        details = []
        if missing:
            details.append("missing " + ", ".join(sorted(missing)))
        if unknown:
            details.append("unknown " + ", ".join(sorted(unknown)))
        raise BackupValidationError("Invalid backup envelope: " + "; ".join(details))
    if raw["format"] != BACKUP_FORMAT:
        raise BackupValidationError("Unsupported backup format.")
    if isinstance(raw["version"], bool) or raw["version"] != BACKUP_VERSION:
        raise BackupValidationError(
            f"Unsupported backup version: {raw['version']!r}."
        )
    _parse_datetime_value(raw["exported_at"], field_name="exported_at")

    raw_settings = raw["settings"]
    if not isinstance(raw_settings, Mapping) or set(raw_settings) != set(_SETTINGS_KEYS):
        raise BackupValidationError("Backup settings are incomplete or unknown.")
    if not isinstance(raw_settings["time_zone"], str) or not isinstance(
        raw_settings["language_code"], str
    ) or not isinstance(raw_settings["use_tz"], bool):
        raise BackupValidationError("Backup settings have invalid value types.")

    raw_data = raw["data"]
    raw_relations = raw["relations"]
    if not isinstance(raw_data, Mapping) or set(raw_data) != set(MODEL_SPEC_BY_KEY):
        raise BackupValidationError("Backup data does not contain the complete model set.")
    if not isinstance(raw_relations, Mapping) or set(raw_relations) != set(
        RELATION_SPEC_BY_KEY
    ):
        raise BackupValidationError("Backup relations do not contain the complete relation set.")

    normalized_data: dict[str, list[dict[str, Any]]] = {}
    id_sets: dict[str, set[int]] = {}
    for spec in MODEL_SPECS:
        raw_records = raw_data[spec.key]
        if not isinstance(raw_records, list):
            raise BackupValidationError(f"{spec.key} must be a list of records.")
        fields = _model_fields(spec.model)
        expected_fields = {field.attname for field in fields}
        records: list[dict[str, Any]] = []
        ids: set[int] = set()
        for index, raw_record in enumerate(raw_records):
            if not isinstance(raw_record, Mapping):
                raise BackupValidationError(f"{spec.key}[{index}] must be an object.")
            if set(raw_record) != expected_fields:
                raise BackupValidationError(
                    f"{spec.key}[{index}] fields do not match the schema."
                )
            record: dict[str, Any] = {}
            for field in fields:
                field_name = field.attname
                value = raw_record[field_name]
                if field_name == "id":
                    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                        raise BackupValidationError(
                            f"{spec.key}[{index}].id must be a positive integer."
                        )
                    record[field_name] = value
                else:
                    record[field_name] = _coerce_field_value(
                        field,
                        value,
                        field_name=f"{spec.key}[{index}].{field_name}",
                    )
            if record["id"] in ids:
                raise BackupValidationError(f"{spec.key} contains duplicate ids.")
            ids.add(record["id"])
            instance = spec.model(**record)
            try:
                instance.clean()
            except ValidationError as exc:
                raise BackupValidationError(
                    f"Invalid {spec.key}[{index}]: {exc}"
                ) from exc
            records.append(record)
        _validate_unique_constraints(spec, records)
        normalized_data[spec.key] = records
        id_sets[spec.key] = ids

    normalized_relations: dict[str, list[dict[str, int]]] = {}
    for relation in RELATION_SPECS:
        raw_rows = raw_relations[relation.key]
        if not isinstance(raw_rows, list):
            raise BackupValidationError(f"{relation.key} must be a list.")
        rows = []
        seen_pairs: set[tuple[int, int]] = set()
        for index, raw_row in enumerate(raw_rows):
            if not isinstance(raw_row, Mapping) or set(raw_row) != {"from_id", "to_id"}:
                raise BackupValidationError(f"{relation.key}[{index}] is invalid.")
            from_id = raw_row["from_id"]
            to_id = raw_row["to_id"]
            if any(
                isinstance(value, bool) or not isinstance(value, int) or value < 1
                for value in (from_id, to_id)
            ):
                raise BackupValidationError(f"{relation.key}[{index}] ids are invalid.")
            if from_id not in id_sets[relation.source_model_key] or to_id not in id_sets[
                relation.target_model_key
            ]:
                raise BackupValidationError(
                    f"{relation.key}[{index}] references a missing record."
                )
            pair = (from_id, to_id)
            if pair in seen_pairs:
                raise BackupValidationError(f"{relation.key} contains duplicate edges.")
            seen_pairs.add(pair)
            rows.append({"from_id": from_id, "to_id": to_id})
        normalized_relations[relation.key] = rows

    return {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "exported_at": _parse_datetime_value(
            raw["exported_at"], field_name="exported_at"
        ),
        "settings": dict(raw_settings),
        "data": normalized_data,
        "relations": normalized_relations,
    }


def export_backup(*, exported_at: datetime | None = None) -> dict[str, Any]:
    """Return the complete local domain as a deterministic JSON-ready dict."""

    moment = exported_at or timezone.now()
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment, datetime_timezone.utc)
    data: dict[str, list[dict[str, Any]]] = {}
    for spec in MODEL_SPECS:
        fields = _model_fields(spec.model)
        records = []
        for instance in spec.model.objects.order_by("id"):
            records.append(
                {
                    field.attname: _serialize_value(field, getattr(instance, field.attname))
                    for field in fields
                }
            )
        data[spec.key] = records

    relations: dict[str, list[dict[str, int]]] = {}
    for relation in RELATION_SPECS:
        rows = relation.through.objects.order_by(
            relation.source_attname, relation.target_attname
        ).values_list(relation.source_attname, relation.target_attname)
        relations[relation.key] = [
            {"from_id": from_id, "to_id": to_id} for from_id, to_id in rows
        ]

    return {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "exported_at": moment.isoformat(),
        "settings": {
            "time_zone": settings.TIME_ZONE,
            "language_code": settings.LANGUAGE_CODE,
            "use_tz": settings.USE_TZ,
        },
        "data": data,
        "relations": relations,
    }


def export_backup_json(
    *, exported_at: datetime | None = None, indent: int = 2
) -> str:
    """Serialize ``export_backup`` to a portable UTF-8 JSON string."""

    return json.dumps(
        export_backup(exported_at=exported_at),
        cls=DjangoJSONEncoder,
        ensure_ascii=False,
        indent=indent,
    ) + "\n"


def _atomic_write(path: Path, contents: str) -> Path:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(contents)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = temporary.name
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass
    return path


def write_backup(path: str | os.PathLike[str], backup: Mapping[str, Any] | None = None) -> Path:
    """Write a backup atomically and return its path."""

    payload = backup if backup is not None else export_backup()
    return _atomic_write(
        Path(path),
        json.dumps(payload, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2) + "\n",
    )


def _default_safety_export_path() -> Path:
    backup_dir = Path(
        getattr(settings, "DSA_BACKUP_DIR", Path(settings.BASE_DIR) / "backups")
    )
    stamp = timezone.now().strftime("%Y%m%dT%H%M%S%fZ")
    return backup_dir / f"safety-{stamp}-{uuid4().hex[:8]}.json"


def _delete_carried_blocks() -> None:
    """Delete self-referencing carried blocks from leaves upward."""

    while StudyBlock.objects.filter(carried_from__isnull=False).exists():
        leaf_ids = list(
            StudyBlock.objects.filter(
                carried_from__isnull=False,
                carry_forward_blocks__isnull=True,
            ).values_list("id", flat=True)
        )
        if not leaf_ids:
            raise BackupRestoreError("Existing StudyBlock carry-forward graph is cyclic.")
        StudyBlock.objects.filter(id__in=leaf_ids).delete()


def _clear_domain() -> None:
    """Remove domain rows in dependency order inside the active transaction."""

    # PROTECT relationships must disappear before their referenced rows.
    for model in (
        AssessmentMistake,
        AssessmentResponse,
        AssessmentSession,
        AssessmentSelection,
        AssessmentPool,
        ProblemReviewEvent,
        ProblemReview,
        RunHistoryEntry,
        LearningStatusEvent,
        SolutionReflection,
        PracticeRun,
        CustomTestCase,
        ProblemDraft,
        ProblemLearningStatus,
        StudyBlockProblem,
        WorkSession,
    ):
        model.objects.all().delete()

    _delete_carried_blocks()
    StudyBlock.objects.all().delete()
    RestDay.objects.all().delete()

    Concept.prerequisites.through.objects.all().delete()
    ProblemClassification.objects.all().delete()
    ProblemSnapshot.objects.all().delete()
    CatalogSync.objects.all().delete()
    Problem.objects.all().delete()
    ConceptCheckpoint.objects.all().delete()
    ConceptNote.objects.all().delete()
    Concept.objects.all().delete()
    Topic.objects.all().delete()


def _instance_from_record(
    spec: ModelSpec,
    record: Mapping[str, Any],
    *,
    clear_carried_from: bool = False,
) -> models.Model:
    values = dict(record)
    if clear_carried_from and spec.model is StudyBlock:
        values["carried_from_id"] = None
    return spec.model(**values)


def _restore_exact_timestamps(
    spec: ModelSpec,
    records: list[dict[str, Any]],
) -> None:
    """Undo auto-now pre-save behavior from bulk inserts.

    ``bulk_create`` still prepares ``auto_now`` and ``auto_now_add`` fields on
    current Django versions.  Updating those columns directly after the
    insert keeps the backup's historical timestamps byte-for-byte stable
    without invoking model ``save`` hooks or signals.
    """

    timestamp_fields = tuple(
        field.attname
        for field in _model_fields(spec.model)
        if isinstance(field, models.DateTimeField)
    )
    if not timestamp_fields:
        return
    for record in records:
        spec.model.objects.filter(pk=record["id"]).update(
            **{field_name: record[field_name] for field_name in timestamp_fields}
        )


def _insert_domain(data: Mapping[str, list[dict[str, Any]]]) -> dict[str, int]:
    restored_counts: dict[str, int] = {}
    carried_from_by_id: dict[int, int | None] = {}

    for spec in MODEL_SPECS:
        records = data[spec.key]
        if spec.model is StudyBlock:
            instances = []
            for record in records:
                carried_from_by_id[record["id"]] = record["carried_from_id"]
                instances.append(
                    _instance_from_record(spec, record, clear_carried_from=True)
                )
        else:
            instances = [_instance_from_record(spec, record) for record in records]
        if instances:
            spec.model.objects.bulk_create(instances, batch_size=500)
            _restore_exact_timestamps(spec, records)
        restored_counts[spec.key] = len(instances)

    for block_id, carried_from_id in carried_from_by_id.items():
        if carried_from_id is not None:
            StudyBlock.objects.filter(pk=block_id).update(
                carried_from_id=carried_from_id
            )

    for relation in RELATION_SPECS:
        rows = data["__relations__"][relation.key]
        through_instances = [
            relation.through(
                **{
                    relation.source_attname: row["from_id"],
                    relation.target_attname: row["to_id"],
                }
            )
            for row in rows
        ]
        if through_instances:
            relation.through.objects.bulk_create(through_instances, batch_size=500)
        restored_counts[relation.key] = len(through_instances)
    return restored_counts


@transaction.atomic
def _replace_validated_backup(validated: Mapping[str, Any]) -> dict[str, int]:
    _clear_domain()
    insert_data = dict(validated["data"])
    insert_data["__relations__"] = validated["relations"]
    return _insert_domain(insert_data)


def restore_backup(
    source: Any,
    *,
    safety_export_path: str | os.PathLike[str] | None = None,
) -> RestoreResult:
    """Validate, safety-export, and atomically replace the local domain.

    Validation is completed before the safety file is written.  Therefore an
    invalid upload cannot even create a safety artifact or mutate local data.
    A database failure after the safety export rolls back the replacement
    transaction, leaving both the original rows and the recoverable safety
    file available.
    """

    validated = validate_backup(source)
    safety_path = Path(safety_export_path) if safety_export_path else _default_safety_export_path()
    write_backup(safety_path, export_backup())
    try:
        restored_counts = _replace_validated_backup(validated)
    except (IntegrityError, ValidationError, BackupRestoreError) as exc:
        raise BackupRestoreError(
            "Restore could not be committed; local data was left unchanged."
        ) from exc
    return RestoreResult(safety_export_path=safety_path, restored_counts=restored_counts)


__all__ = [
    "BACKUP_FORMAT",
    "BACKUP_VERSION",
    "BackupError",
    "BackupRestoreError",
    "BackupValidationError",
    "RestoreResult",
    "export_backup",
    "export_backup_json",
    "restore_backup",
    "validate_backup",
    "write_backup",
]
