from rest_framework import serializers
from .models import Cart, CartItem
from products.serializers import ProductSerializer
from products.models import Product
from django.utils.translation import gettext_lazy as _

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity', 'total_price', 'created_at', 'updated_at']

    def get_total_price(self, obj) -> float:
        request = self.context.get('request')
        base_total = obj.total_price
        if request and hasattr(request, 'country') and request.country:
            exchange_rate = request.country.exchange_rate
            return round(base_total * exchange_rate, 2)
        return base_total

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()
    total_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'user', 'items', 'total_price', 'total_items', 'created_at', 'updated_at']

    def get_total_price(self, obj) -> float:
        request = self.context.get('request')
        base_total = obj.total_price
        if request and hasattr(request, 'country') and request.country:
            exchange_rate = request.country.exchange_rate
            return round(base_total * exchange_rate, 2)
        return base_total

class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate_product_id(self, value):
        try:
            product = Product.objects.get(id=value, is_active=True)
        except Product.DoesNotExist:
            raise serializers.ValidationError(_("Product not found or inactive."))
        return value

    def validate(self, data):
        product = Product.objects.get(id=data['product_id'])
        if product.stock < data['quantity']:
            raise serializers.ValidationError(_("Not enough stock available."))
        return data

class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)

    def validate(self, data):
        # We'll check stock against the item's product in the view
        return data

class CartResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = CartSerializer()