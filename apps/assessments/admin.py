from django.contrib import admin

from . import models

admin.site.register(models.Assessment)
admin.site.register(models.Question)
admin.site.register(models.Attempt)
admin.site.register(models.AnswerRecord)
