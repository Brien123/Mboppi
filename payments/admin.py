from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from .models import (
    FlutterwaveCustomer,
    PaymentMethod,
    PaymentPlan,
    Subscription,
    Transaction,
    WebhookEvent,
)


@admin.register(FlutterwaveCustomer)
class FlutterwaveCustomerAdmin(ModelAdmin):
    list_display = ('id', 'user', 'email', 'flutterwave_customer_id', 'created_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('email', 'flutterwave_customer_id', 'user__email', 'user__username')
    readonly_fields = ('flutterwave_customer_id', 'created_at', 'updated_at')
    fields = ('user', 'flutterwave_customer_id', 'email', 'created_at', 'updated_at')


@admin.register(PaymentMethod)
class PaymentMethodAdmin(ModelAdmin):
    list_display = ('id', 'customer', 'flutterwave_payment_method_id', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('flutterwave_payment_method_id', 'customer__email', 'customer__flutterwave_customer_id')
    readonly_fields = ('flutterwave_payment_method_id', 'nonce', 'created_at')
    fields = ('customer', 'flutterwave_payment_method_id', 'nonce', 'is_active', 'created_at')


@admin.register(PaymentPlan)
class PaymentPlanAdmin(ModelAdmin):
    list_display = ('id', 'name', 'amount', 'currency', 'interval', 'is_active', 'created_at')
    list_filter = ('interval', 'is_active', 'currency', 'created_at')
    search_fields = ('name', 'flutterwave_plan_id')
    readonly_fields = ('flutterwave_plan_id', 'created_at')
    fields = ('flutterwave_plan_id', 'name', 'amount', 'currency', 'interval', 'is_active', 'created_at')


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = ('id', 'order', 'customer', 'flutterwave_subscription_id', 'plan', 'amount', 'currency', 'status', 'next_billing_date', 'created_at')
    list_filter = ('status', 'currency', 'created_at', 'next_billing_date')
    search_fields = ('flutterwave_subscription_id', 'flutterwave_plan_id', 'customer__email', 'customer__flutterwave_customer_id', 'order__order_id')
    readonly_fields = ('flutterwave_subscription_id', 'flutterwave_plan_id', 'created_at', 'cancelled_at')
    fields = (
        'order', 'customer', 'payment_method', 'flutterwave_subscription_id', 'plan',
        'flutterwave_plan_id', 'amount', 'currency', 'status', 'next_billing_date',
        'cancelled_at', 'cancel_reason', 'created_at'
    )


@admin.register(Transaction)
class TransactionAdmin(ModelAdmin):
    list_display = ('id', 'reference', 'order', 'amount', 'currency', 'status', 'customer', 'payment_method', 'subscription', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('reference', 'flutterwave_charge_id', 'customer__email', 'order__order_id')
    readonly_fields = ('flutterwave_charge_id', 'reference', 'created_at')
    fields = (
        'order', 'customer', 'payment_method', 'subscription', 'flutterwave_charge_id',
        'reference', 'amount', 'currency', 'status', 'created_at'
    )


@admin.register(WebhookEvent)
class WebhookEventAdmin(ModelAdmin):
    list_display = ('id', 'event_type', 'event_id', 'provider', 'status', 'retry_count', 'created_at', 'preview_payload')
    list_filter = ('provider', 'event_type', 'status', 'created_at')
    search_fields = ('event_id', 'event_type', 'error_message')
    readonly_fields = ('event_id', 'event_type', 'payload', 'provider', 'created_at', 'preview_payload')
    fields = (
        'provider', 'event_id', 'event_type', 'payload', 'status',
        'processed_at', 'error_message', 'retry_count', 'created_at'
    )

    def preview_payload(self, obj):
        """Show a truncated preview of the JSON payload."""
        if obj.payload:
            import json
            payload_str = json.dumps(obj.payload, indent=2)[:200]
            return format_html('<pre>{}{}</pre>', payload_str, '…' if len(json.dumps(obj.payload)) > 200 else '')
        return '-'
    preview_payload.short_description = 'Payload preview'