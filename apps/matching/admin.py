from django.contrib import admin

from . import models

admin.site.register(models.JobMatch)
admin.site.register(models.ReadinessSnapshot)
