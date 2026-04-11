from django.contrib import admin
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "mobile_number", "is_active", "is_staff", "date_joined")
    list_filter = ("is_active", "is_staff", "is_superuser", "date_joined")
    search_fields = ("full_name", "mobile_number")
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined",)
    
    fieldsets = (
        ("Account Info", {
            "fields": ("mobile_number", "password")
        }),
        ("Personal Info", {
            "fields": ("full_name",)
        }),
        ("Permissions", {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")
        }),
        ("Dates", {
            "fields": ("date_joined",),
            "classes": ("collapse",)
        }),
    )
