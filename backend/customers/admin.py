from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "phone", "email", "is_active", "created_at")
    list_filter = ("is_active", "organization")
    search_fields = ("name", "phone", "email", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")
