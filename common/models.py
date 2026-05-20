from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify

class Country(models.Model):
    LANGUAGE_CHOICES = (
        ('en', _('English')),
        ('fr', _('French')),
    )

    name = models.CharField(_('Name'), max_length=100)
    code = models.CharField(_('Country Code'), max_length=5, unique=True, help_text=_('e.g. NG, CM'))
    slug = models.SlugField(_('Slug'), max_length=10, unique=True, help_text=_('Used in URLs and subdomains, e.g. cm, ng'), null=False, blank=True)
    currency_code = models.CharField(_('Currency Code'), max_length=10, help_text=_('e.g. NGN, XAF'))
    # currency_symbol = models.CharField(_('Currency Symbol'), max_length=10, default='', help_text=_('e.g. ₦, FCFA'))
    exchange_rate = models.DecimalField(_('Exchange Rate'), max_digits=12, decimal_places=4, default=1.0, help_text=_('Rate relative to the base currency (e.g. 1 USD = X XAF)'))
    default_language = models.CharField(_('Default Language'), max_length=5, choices=LANGUAGE_CHOICES, default='en')
    is_default = models.BooleanField(_('Is Default'), default=False, help_text=_('Only one country should be set as default'))
    is_active = models.BooleanField(_('Is Active'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Country')
        verbose_name_plural = _('Countries')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            if len(base_slug) > 10:
                base_slug = base_slug[:10]
            slug = base_slug
            counter = 1
            q = Country.objects.filter(slug=slug)
            if self.pk:
                q = q.exclude(pk=self.pk)
            while q.exists():
                slug = f"{base_slug[:8]}-{counter}"
                counter += 1
                q = Country.objects.filter(slug=slug)
                if self.pk:
                    q = q.exclude(pk=self.pk)
            self.slug = slug

        if self.is_default:
            # Ensure only one country is the default
            Country.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)
        
        from django.core.cache import cache
        cache.delete(f"country_slug_{self.slug}")
        cache.delete("country_default")

    def delete(self, *args, **kwargs):
        from django.core.cache import cache
        cache.delete(f"country_slug_{self.slug}")
        cache.delete("country_default")
        super().delete(*args, **kwargs)

from django.conf import settings

class UserDevice(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='devices',
        help_text=_('Null if the user is unauthenticated.')
    )
    fingerprint = models.CharField(_('Fingerprint'), max_length=64, db_index=True)
    device_type = models.CharField(_('Device Type'), max_length=20)
    browser = models.CharField(_('Browser'), max_length=100)
    os = models.CharField(_('OS'), max_length=100)
    device_family = models.CharField(_('Device Family'), max_length=100)
    ip_address = models.GenericIPAddressField(_('IP Address'), null=True, blank=True)
    last_seen = models.DateTimeField(_('Last Seen'), auto_now=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)

    class Meta:
        verbose_name = _('User Device')
        verbose_name_plural = _('User Devices')
        unique_together = ('user', 'fingerprint')

    def __str__(self):
        return f"{self.user or 'Anonymous'} - {self.device_type} ({self.os})"
