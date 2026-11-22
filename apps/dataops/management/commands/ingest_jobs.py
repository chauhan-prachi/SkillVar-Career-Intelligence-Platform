from django.core.management.base import BaseCommand, CommandError

from apps.dataops.models import Dataset
from apps.dataops.pipeline import ingest_jobs


class Command(BaseCommand):
    help = "Ingest job postings from a CSV/JSON file into the shared reference data. Safe to re-run."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--dataset", default="synthetic-jobs", help="Dataset slug (created if missing)")
        parser.add_argument("--name", default="")
        parser.add_argument("--source-note", default="")
        parser.add_argument("--synthetic", action="store_true", help="Mark rows as synthetic (not real vacancies)")
        parser.add_argument("--batch-size", type=int, default=500)

    def handle(self, *args, path, dataset, name, source_note, synthetic, batch_size, **opts):
        ds, _ = Dataset.objects.get_or_create(slug=dataset, defaults={
            "name": name or dataset, "kind": Dataset.JOBS, "source_note": source_note or ("Synthetic data" if synthetic else "")})
        try:
            run = ingest_jobs(path, ds, batch_size=batch_size, synthetic=synthetic)
        except FileNotFoundError:
            raise CommandError(f"File not found: {path}")
        style = self.style.SUCCESS if run.status != "failed" else self.style.ERROR
        self.stdout.write(style(
            f"Run {run.pk}: {run.status} | read {run.rows_read}, loaded {run.rows_loaded}, duplicates {run.rows_duplicate}, "
            f"rejected {run.rows_rejected} | {run.duration_seconds:.2f}s"))
        if run.error_summary:
            raise CommandError(run.error_summary)
