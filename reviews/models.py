from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

User = get_user_model()

class Review(models.Model):
    product = models.ForeignKey(
        'products.Product', 
        on_delete=models.CASCADE, 
        related_name='reviews',
        verbose_name=_('Product')
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='reviews',
        verbose_name=_('User')
    )
    rating = models.PositiveSmallIntegerField(
        _('Rating'),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_('Rating between 1 and 5')
    )
    comment = models.TextField(_('Comment'), blank=True)
    is_active = models.BooleanField(_('Is Active'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Review')
        verbose_name_plural = _('Reviews')
        ordering = ['-created_at']
        unique_together = ('product', 'user')

    def __str__(self):
        return f"Review by {self.user.email} for {self.product.name}"
