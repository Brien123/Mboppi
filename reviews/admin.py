from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Review

@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ["product", "user", "rating", "is_active", "created_at"]
    list_filter = ["rating", "is_active", "created_at"]
    search_fields = ["product__name", "user__email", "comment"]
    list_editable = ["is_active"]
    readonly_fields = ["created_at", "updated_at"]
