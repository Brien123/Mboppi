from rest_framework import serializers
from .models import Category, Product, ProductImage, CategoryImage, ProductSearchLog


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image_thumb', 'image_medium', 'image_large']


class CategoryImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryImage
        fields = ['id', 'image_thumb', 'image_medium', 'image_large']


class CategorySerializer(serializers.ModelSerializer):
    category_image = CategoryImageSerializer(read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'created_at', 'category_image']
        extra_kwargs = {'slug': {'read_only': True}}


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    local_price = serializers.SerializerMethodField()
    currency_code = serializers.SerializerMethodField()
    images = ProductImageSerializer(source='product_images', many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'category', 'category_name', 'name', 'slug',
            'description', 'base_price', 'local_price', 'currency_code',
            'stock', 'is_active', 'created_at', 'updated_at', 'images'
        ]
        extra_kwargs = {'slug': {'read_only': True}}

    def get_local_price(self, obj) -> float:
        request = self.context.get('request')
        if request and hasattr(request, 'country') and request.country:
            exchange_rate = request.country.exchange_rate
            return round(obj.base_price * exchange_rate, 2)
        return obj.base_price

    def get_currency_code(self, obj) -> str:
        request = self.context.get('request')
        if request and hasattr(request, 'country') and request.country:
            return request.country.currency_code
        from django.conf import settings
        return getattr(settings, 'BASE_CURRENCY', 'USD')


class CategoryResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = CategorySerializer()


class PaginatedCategoryDataSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = CategorySerializer(many=True)


class CategoryListResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = PaginatedCategoryDataSerializer()


class ProductResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = ProductSerializer()


class PaginatedProductDataSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = ProductSerializer(many=True)


class ProductListResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = PaginatedProductDataSerializer()


class ProductSearchRequestSerializer(serializers.Serializer):
    q = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        help_text="Search term (name, description, category)"
    )
    min_price = serializers.DecimalField(
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
        help_text="Minimum price filter"
    )
    max_price = serializers.DecimalField(
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
        help_text="Maximum price filter"
    )
    price_type = serializers.ChoiceField(
        required=False,
        choices=['base', 'local'],
        default='base',
        help_text="Currency type for price filters and sorting"
    )
    ordering = serializers.ChoiceField(
        required=False,
        choices=[
            'price', '-price',
            'created_at', '-created_at',
            'relevance', '-relevance'
        ],
        help_text="Sort order. Prefix with '-' for descending."
    )

    def validate(self, data):
        min_price = data.get('min_price')
        max_price = data.get('max_price')
        if min_price is not None and max_price is not None and min_price > max_price:
            raise serializers.ValidationError("min_price cannot be greater than max_price.")
        return data


class SearchSuggestionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.SlugField()


class SearchSuggestionResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = SearchSuggestionSerializer(many=True)

    
class ProductSearchLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSearchLog
        fields = ['query', 'created_at']


class ProductSearchLogResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = ProductSearchLogSerializer(many=True)

class PopularSearchSerializer(serializers.Serializer):
    query = serializers.CharField()
    count = serializers.IntegerField()


class PopularSearchResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = PopularSearchSerializer(many=True)


class ImageSearchSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)