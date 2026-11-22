import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.dataops.synthetic import generate


class Command(BaseCommand):
    help = "Write deterministic SYNTHETIC job postings to a CSV or JSON file (not real vacancies)."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=1000)
        parser.add_argument("--seed", type=int, default=1)
        parser.add_argument("--out", default="data/synthetic_jobs.csv")

    def handle(self, *args, count, seed, out, **opts):
        rows = generate(count, seed)
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".json":
            path.write_text(json.dumps({"jobs": rows}, indent=1), encoding="utf-8")
        else:
            with path.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(rows)} synthetic postings to {path}"))
