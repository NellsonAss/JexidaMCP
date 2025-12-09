from django.contrib import admin
from .models import Secret


@admin.register(Secret)
class SecretAdmin(admin.ModelAdmin):
    list_display = ["name", "service_type", "key", "created_at", "updated_at"]
    list_filter = ["service_type"]
    search_fields = ["name", "key"]
    readonly_fields = ["created_at", "updated_at"]
    
    # Don't show encrypted_value in admin
    exclude = ["encrypted_value"]

