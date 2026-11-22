from django.contrib import admin

from . import models

admin.site.register(models.LearningResource)
admin.site.register(models.Roadmap)
admin.site.register(models.RoadmapItem)
