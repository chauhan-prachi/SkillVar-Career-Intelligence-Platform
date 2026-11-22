from django.contrib import admin

from . import models

admin.site.register(models.JobDescription)
admin.site.register(models.JobRequirement)
