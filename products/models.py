from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class Category(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    name = models.CharField(_('Name'), max_length=100)
    slug = models.SlugField(_('Slug'), max_length=100, unique=True)
    description = models.TextField(_('Description'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Product(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(_('Name'), max_length=200)
    slug = models.SlugField(_('Slug'), max_length=200, unique=True)
    description = models.TextField(_('Description'), blank=True)
    base_price = models.DecimalField(
        _('Base Price'), max_digits=12, decimal_places=2,
        help_text=_('Base price in the default currency (e.g., USD)')
    )
    stock = models.PositiveIntegerField(_('Stock'), default=0)
    is_active = models.BooleanField(_('Is Active'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Product')
        verbose_name_plural = _('Products')
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            q = Product.objects.filter(slug=slug)
            if self.pk:
                q = q.exclude(pk=self.pk)
            while q.exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
                q = Product.objects.filter(slug=slug)
                if self.pk:
                    q = q.exclude(pk=self.pk)
            self.slug = slug
        super().save(*args, **kwargs)


class ProductViewLog(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='view_logs')
    country = models.ForeignKey('common.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='product_views')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='product_views')
    ip_address = models.GenericIPAddressField(_('IP Address'), null=True, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Product View Log')
        verbose_name_plural = _('Product View Logs')
        ordering = ['-viewed_at']

    def __str__(self):
        return f"{self.product.name} viewed at {self.viewed_at}"


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_images')
    image_thumb = models.ImageField(_('Thumbnail'), upload_to='products/thumbs/', null=True, blank=True)
    image_medium = models.ImageField(_('Medium'), upload_to='products/medium/', null=True, blank=True)
    image_large = models.ImageField(_('Large'), upload_to='products/large/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Product Image')
        verbose_name_plural = _('Product Images')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} image ({self.id})"


class CategoryImage(models.Model):
    category = models.OneToOneField(Category, on_delete=models.CASCADE, related_name='category_image')
    image_thumb = models.ImageField(_('Thumbnail'), upload_to='categories/thumbs/', null=True, blank=True)
    image_medium = models.ImageField(_('Medium'), upload_to='categories/medium/', null=True, blank=True)
    image_large = models.ImageField(_('Large'), upload_to='categories/large/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Category Image')
        verbose_name_plural = _('Category Images')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.category.name} image"


class ProductSearchLog(models.Model):
    query = models.CharField(_('Query'), max_length=255)
    country = models.ForeignKey('common.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='product_searches')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='product_searches')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Product Search Log')
        verbose_name_plural = _('Product Search Logs')
        ordering = ['-created_at']

    def __str__(self):
        return f"'{self.query}' searched at {self.created_at}"