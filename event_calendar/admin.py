from django.contrib import admin
from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "start", "end", "priority"]
    list_filter = ["priority", "is_all_day"]
    search_fields = ["title", "user__email"]
