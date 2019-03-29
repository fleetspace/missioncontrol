from django.contrib import admin
from django import forms
from . import models

admin.site.register(models.What)
admin.site.register(models.RelatedFile)
