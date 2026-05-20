from django.db import models
from django.conf import settings
from django.utils import timezone


class FlutterwaveCustomer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='flutterwave_customer'
    )
    flutterwave_customer_id = models.CharField(max_length=50, unique=True)
    email = models.EmailField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.email} ({self.flutterwave_customer_id})"


class PaymentMethod(models.Model):
    customer = models.ForeignKey(
        FlutterwaveCustomer,
        on_delete=models.CASCADE,
        related_name='payment_methods'
    )
    flutterwave_payment_method_id = models.CharField(max_length=50, unique=True)
    nonce = models.CharField(max_length=12, help_text="12 char alphanumeric nonce used for encryption")
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    brand = models.CharField(max_length=20, null=True, blank=True)
    last4 = models.CharField(max_length=4, null=True, blank=True)
    expiry_month = models.CharField(max_length=2, null=True, blank=True)
    expiry_year = models.CharField(max_length=2, null=True, blank=True)
    idempotency_key = models.CharField(max_length=255, null=True, blank=True)


    trace_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Payment method {self.flutterwave_payment_method_id}"


class Interval(models.TextChoices):
    DAILY = 'DAILY', 'Daily'
    WEEKLY = 'WEEKLY', 'Weekly'
    MONTHLY = 'MONTHLY', 'Monthly'
    YEARLY = 'YEARLY', 'Yearly'


class PaymentPlan(models.Model):
    """Cached payment plan from Flutterwave."""
    flutterwave_plan_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=12)
    interval = models.CharField(max_length=10, choices=Interval.choices, default=Interval.MONTHLY)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class Subscription(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    customer = models.ForeignKey(FlutterwaveCustomer, on_delete=models.CASCADE, related_name='subscriptions')
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True)
    flutterwave_subscription_id = models.CharField(max_length=50, unique=True)
    plan = models.ForeignKey(PaymentPlan, on_delete=models.PROTECT, related_name='subscriptions', null=True, blank=True)
    flutterwave_plan_id = models.CharField(max_length=50)  # fallback ID
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    next_billing_date = models.DateTimeField(null=True, blank=True, db_index=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True)
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscriptions'
    )
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Subscription {self.flutterwave_subscription_id}"


class Transaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
    ]

    customer = models.ForeignKey(FlutterwaveCustomer, on_delete=models.SET_NULL, null=True)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True)
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True)
    flutterwave_charge_id = models.CharField(max_length=50, unique=True)
    reference = models.CharField(max_length=100, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    idempotency_key = models.CharField(max_length=255, null=True, blank=True)
    trace_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    def __str__(self):
        return self.reference


class WebhookEvent(models.Model):
    """
    Logs all incoming webhook events for auditing and idempotency.
    """
    PROVIDER_CHOICES = [
        ('flutterwave', 'Flutterwave'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('ignored', 'Ignored'),
    ]

    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='flutterwave')
    event_id = models.CharField(max_length=100, unique=True, help_text="Unique webhook event ID from Flutterwave")
    event_type = models.CharField(max_length=100, db_index=True, help_text="e.g., charge.completed, charge.failed")
    payload = models.JSONField(help_text="Original webhook payload")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    retry_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_id']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.event_id}"