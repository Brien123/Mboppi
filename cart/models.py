from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from products.models import Product

class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='cart',verbose_name=_('User'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Cart')
        verbose_name_plural = _('Carts')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email}'s Cart"

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())

    @property
    def total_items(self):
        return self.items.count()


class CartItem(models.Model):
    cart = models.ForeignKey(Cart,on_delete=models.CASCADE,related_name='items',verbose_name=_('Cart'))
    product = models.ForeignKey(Product,on_delete=models.CASCADE,related_name='cart_items',verbose_name=_('Product'))
    quantity = models.PositiveIntegerField(_('Quantity'), default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Cart Item')
        verbose_name_plural = _('Cart Items')
        unique_together = ('cart', 'product')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def total_price(self):
        return self.product.base_price * self.quantity
