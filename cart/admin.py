from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Cart, CartItem

@admin.register(Cart)
class CartAdmin(ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    search_fields = ('user__email', 'user__username')

@admin.register(CartItem)
class CartItemAdmin(ModelAdmin):
    list_display = ('cart', 'product', 'quantity', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    search_fields = ('cart__user__email', 'product__name')
    list_filter = ('product',)
