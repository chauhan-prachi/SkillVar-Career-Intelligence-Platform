from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, render

from apps.jobs.models import JobDescription

from .models import IngestionRun


@staff_member_required
def runs(request):
    page = Paginator(IngestionRun.objects.select_related("dataset"), 20).get_page(request.GET.get("page"))
    stats = {"jobs": JobDescription.objects.filter(user__isnull=True).count(),
             "runs": IngestionRun.objects.count(), "failed": IngestionRun.objects.filter(status="failed").count()}
    return render(request, "dataops/runs.html", {"page": page, "stats": stats})


@staff_member_required
def run_detail(request, pk):
    run = get_object_or_404(IngestionRun.objects.select_related("dataset"), pk=pk)
    return render(request, "dataops/run_detail.html", {
        "run": run, "quality": run.quality_results.all(), "rejected": run.rejected.all()[:50],
        "by_status": run.quality_results.values("status").annotate(n=Count("id"))})
