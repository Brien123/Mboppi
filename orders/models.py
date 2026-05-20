from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import uuid
from products.models import Product

class PaymentPlan(models.TextChoices):
    FULL_PAYMENT = 'FP', _('Full Payment')
    WEEKLY_4 = '4W', _('4 Weeks (weekly)')
    MONTHLY_2 = '2M', _('2 Months (monthly)')
    MONTHLY_4 = '4M', _('4 Months (monthly)')
    MONTHLY_6 = '6M', _('6 Months (monthly)')
    MONTHLY_12 = '12M', _('12 Months (monthly)')


class Order(models.Model):
    order_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    country = models.ForeignKey('common.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    # order_number = models.CharField(_('Order Number'), max_length=50, unique=True, editable=False)
    total_base_price = models.DecimalField(_('Total Base Price'), max_digits=12, decimal_places=2)
    total_local_price = models.DecimalField(_('Total Local Price'), max_digits=12, decimal_places=2)
    currency_code = models.CharField(max_length=10)
    payment_plan = models.CharField(_('Payment Plan'), max_length=3, choices=PaymentPlan.choices)
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', _('Pending')),
        ('active', _('Active')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    local_price = models.DecimalField(max_digits=12, decimal_places=2)

class PaymentInstallment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='installments')
    due_date = models.DateField()
    amount_base = models.DecimalField(max_digits=12, decimal_places=2)
    amount_local = models.DecimalField(max_digits=12, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    transaction = models.ForeignKey(
        'payments.Transaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='installments'
    )

    class Meta:
        ordering = ['due_date']

class DeliveryDetail(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_detail')
    full_name = models.CharField(_('Full Name'), max_length=255)
    phone_number = models.CharField(_('Phone Number'), max_length=20)
    address = models.TextField(_('Address'))
    city = models.CharField(_('City'), max_length=100)
    state = models.CharField(_('State'), max_length=100)
    postal_code = models.CharField(_('Postal Code'), max_length=20, blank=True)

    def __str__(self):
        return f"Delivery for Order {self.order.order_id}"