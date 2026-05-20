from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Country, UserDevice

@admin.register(Country)
class CountryAdmin(ModelAdmin):
    list_display = ["name", "code", "slug", "currency_code", "exchange_rate", "is_default", "is_active"]
    list_filter = ["is_default", "is_active"]
    search_fields = ["name", "code", "slug"]
    prepopulated_fields = {"slug": ("code",)}

@admin.register(UserDevice)
class UserDeviceAdmin(ModelAdmin):
    list_display = ('__str__', 'ip_address', 'last_seen', 'created_at')
    list_filter = ('device_type', 'os', 'browser', 'user')
    search_fields = ('user__username', 'user__email', 'fingerprint', 'ip_address', 'device_family')
    readonly_fields = ('last_seen', 'created_at', 'fingerprint')

