from django.core.management.base import BaseCommand, CommandError

from problems.catalog_sync import CatalogSyncError, sync_catalog


class Command(BaseCommand):
    help = "Sync the public unauthenticated LeetCode catalog into the local problem library."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of public catalog records requested per page (default: 100).",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=20,
            help="Network timeout in seconds for each public catalog page.",
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting public LeetCode catalog sync…")

        def report_progress(run):
            self.stdout.write(
                f"Batch {run.current_batch}: {run.progress_label} "
                f"({run.imported_count} new, {run.updated_count} updated)."
            )

        try:
            run = sync_catalog(
                batch_size=options["batch_size"],
                timeout=options["timeout"],
                progress_callback=report_progress,
            )
        except CatalogSyncError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Catalog sync complete: {run.processed_items} processed, "
                f"{run.imported_count} imported, {run.updated_count} updated, "
                f"{run.deactivated_count} deactivated."
            )
        )
