from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline, StackedInline
from .models import Order, OrderItem, PaymentInstallment, DeliveryDetail

class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product_name', 'base_price', 'local_price']

class PaymentInstallmentInline(TabularInline):
    model = PaymentInstallment
    extra = 0
    readonly_fields = ['due_date', 'amount_base', 'amount_local', 'is_paid', 'paid_at']
    fields = ['due_date', 'amount_base', 'amount_local', 'is_paid', 'paid_at', 'transaction']

class DeliveryDetailInline(StackedInline):
    model = DeliveryDetail
    extra = 0

@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ['order_id', 'user', 'total_local_price', 'currency_code', 'payment_plan', 'status', 'created_at']
    list_filter = ['status', 'payment_plan', 'created_at']
    search_fields = ['order_id', 'user__email']
    readonly_fields = ['order_id', 'total_base_price', 'total_local_price', 'currency_code']
    inlines = [OrderItemInline, PaymentInstallmentInline, DeliveryDetailInline]