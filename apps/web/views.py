from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from . import dashboard


def home(request):
    return render(request, "web/home.html")


@login_required
def dashboard_view(request):
    return render(request, "web/dashboard.html", dashboard.build(request.user))


def health(request):
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        return JsonResponse({"status": "ok", "database": connection.vendor})
    except Exception:  # noqa: BLE001 - a health probe must report any failure, never raise
        return JsonResponse({"status": "error"}, status=503)


def not_found(request, exception=None):
    return render(request, "404.html", status=404)


def server_error(request):
    return render(request, "500.html", status=500)
