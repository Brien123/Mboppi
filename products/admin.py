from django.contrib import admin
from django.db import models
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.widgets import UnfoldAdminImageFieldWidget
from .models import Category, Product, CategoryImage, ProductImage, ProductSearchLog, ProductViewLog


class CategoryImageInline(StackedInline):
    model = CategoryImage
    extra = 0
    max_num = 1
    fields = ['image_large']
    formfield_overrides = {
        models.ImageField: {'widget': UnfoldAdminImageFieldWidget},
    }

    def has_add_permission(self, request, obj=None):
        if obj and hasattr(obj, 'category_image'):
            return False
        return super().has_add_permission(request, obj)


class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image_large']
    formfield_overrides = {
        models.ImageField: {'widget': UnfoldAdminImageFieldWidget},
    }


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ["name", "slug", "created_at"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CategoryImageInline]


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ["name", "category", "base_price", "stock", "is_active", "created_at"]
    list_filter = ["is_active", "category"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline]


@admin.register(ProductSearchLog)
class ProductSearchLogAdmin(ModelAdmin):
    list_display = ["user", "query", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["query"]

@admin.register(ProductViewLog)
class ProductViewLogAdmin(ModelAdmin):
    list_display = ["user", "product", "viewed_at"]
    