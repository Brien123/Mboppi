from rest_framework import serializers
from django.conf import settings
from products.models import Product
from .models import Order, OrderItem, PaymentInstallment, PaymentPlan, DeliveryDetail
from cart.models import Cart
from django.utils.translation import gettext as _

class DeliveryDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryDetail
        fields = ['full_name', 'phone_number', 'address', 'city', 'state', 'postal_code']

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'quantity', 'base_price', 'local_price']

class PaymentInstallmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentInstallment
        fields = ['id', 'due_date', 'amount_base', 'amount_local', 'is_paid', 'paid_at']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    installments = PaymentInstallmentSerializer(many=True, read_only=True)
    delivery_detail = DeliveryDetailSerializer(read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'order_id', 'total_base_price', 'total_local_price', 'currency_code',
            'payment_plan', 'status', 'created_at', 'items', 'installments',
            'delivery_detail'
        ]

class CheckoutItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)

class CheckoutSerializer(serializers.Serializer):
    items = CheckoutItemSerializer(many=True)
    payment_plan = serializers.ChoiceField(choices=PaymentPlan.choices)
    delivery_details = DeliveryDetailSerializer()

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError(_("At least one item is required."))
        product_ids = [item['product_id'] for item in value]
        if Product.objects.filter(id__in=product_ids, is_active=True).count() != len(set(product_ids)):
            raise serializers.ValidationError(_("One or more products are unavailable."))
        return value

    def validate(self, data):
        request = self.context.get('request')
        user = request.user
        profile = user.profile
        country = getattr(request, 'country', None)

        # Calculate total base price
        total_base = 0
        for item_data in data['items']:
            product = Product.objects.get(id=item_data['product_id'])
            total_base += product.base_price * item_data['quantity']

        limit_usd = profile.kyc_spending_limit_usd

        if total_base > limit_usd:
            # Convert limit to local currency
            if country:
                local_limit = round(limit_usd * country.exchange_rate, 2)
                currency = country.currency_code
            else:
                local_limit = limit_usd
                currency = 'USD'

            if profile.kyc_level == 'none':
                message = _("Please complete Basic KYC to place orders.")
            elif profile.kyc_level == 'basic':
                message = _("This order exceeds your current limit of {limit} {currency}. Please complete document verification to increase your limit.").format(limit=local_limit, currency=currency)
            else:
                message = _("This order exceeds the maximum limit of {limit} {currency}.").format(limit=local_limit, currency=currency)
            
            raise serializers.ValidationError(message)

        return data

    def create(self, validated_data):
        request = self.context['request']
        user = request.user
        country = getattr(request, 'country', None)

        items_data = validated_data['items']
        payment_plan = validated_data['payment_plan']

        total_base = 0
        total_local = 0
        order_items = []

        for item_data in items_data:
            product = Product.objects.get(id=item_data['product_id'])
            quantity = item_data['quantity']
            
            base_price = product.base_price * quantity
            if country:
                local_price = round(base_price * country.exchange_rate, 2)
            else:
                local_price = base_price

            total_base += base_price
            total_local += local_price

            order_items.append(OrderItem(
                product=product,
                product_name=product.name,
                quantity=quantity,
                base_price=base_price,
                local_price=local_price
            ))

        currency_code = country.currency_code if country else getattr(settings, 'BASE_CURRENCY', 'USD')

        order = Order.objects.create(
            user=user,
            country=country,
            total_base_price=total_base,
            total_local_price=total_local,
            currency_code=currency_code,
            payment_plan=payment_plan
        )

        delivery_details_data = validated_data['delivery_details']
        DeliveryDetail.objects.create(order=order, **delivery_details_data)

        for item in order_items:
            item.order = order
        OrderItem.objects.bulk_create(order_items)

        # Clear cart
        Cart.objects.filter(user=user).delete()
        return order

class OrderResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = OrderSerializer()

class PaginatedOrderDataSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = OrderSerializer(many=True)

class OrderListResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = PaginatedOrderDataSerializer()