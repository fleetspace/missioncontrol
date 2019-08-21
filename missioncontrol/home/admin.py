from django.contrib import admin
from django import forms
from . import models

from django.contrib.postgres.forms import SplitArrayField

# Register your models here.
admin.site.register(models.GroundStation)


class SatelliteForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["tle"] = "\n".join(self.instance.tle or [])


class PassForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["source_tle"] = "\n".join(self.instance.source_tle or [])


class TaskStackForm(forms.ModelForm):
    tasks = SplitArrayField(forms.CharField(), size=10, remove_trailing_nulls=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


@admin.register(models.Satellite)
class SatelliteAdmin(admin.ModelAdmin):
    form = SatelliteForm


@admin.register(models.Pass)
class PassAdmin(admin.ModelAdmin):
    list_display = (
        "uuid",
        "access_id",
        "satellite",
        "groundstation",
        "start_time",
        "end_time",
        "scheduled_on_sat",
        "scheduled_on_gs",
        "is_desired",
        "is_valid",
        "attributes",
    )
    form = PassForm
    list_filter = (
        "satellite",
        "groundstation",
        "scheduled_on_sat",
        "scheduled_on_gs",
        "is_desired",
        "is_valid",
    )
    date_hierarchy = "start_time"


@admin.register(models.TaskStack)
class TaskStackAdmin(admin.ModelAdmin):
    form = TaskStackForm
    list_display = ("uuid", "name", "environment", "tasks")
    list_filter = ("environment",)
