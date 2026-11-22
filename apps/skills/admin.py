from django.contrib import admin

from . import models

admin.site.register(models.SkillCategory)
admin.site.register(models.Skill)
admin.site.register(models.SkillAlias)
admin.site.register(models.SkillPrerequisite)
admin.site.register(models.Role)
admin.site.register(models.RoleRequirement)
