from rest_framework import serializers
from .models import FlutterwaveCustomer, PaymentMethod, Transaction

class FlutterwaveCustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlutterwaveCustomer
        fields = ['id', 'user', 'email', 'flutterwave_customer_id', 'created_at', 'updated_at']
        read_only_fields = ['flutterwave_customer_id', 'created_at', 'updated_at']

class CustomerCreateUpdateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=100, required=False)
    last_name = serializers.CharField(max_length=100, required=False)
    phone_number = serializers.CharField(max_length=20, required=False)

class FlutterwaveCustomerResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = FlutterwaveCustomerSerializer()

class PaginatedCustomerDataSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = FlutterwaveCustomerSerializer(many=True)

class FlutterwaveCustomerListResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = PaginatedCustomerDataSerializer()


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'flutterwave_payment_method_id', 'is_active', 'is_default', 
            'brand', 'last4', 'expiry_month', 'expiry_year', 'created_at'
        ]

        read_only_fields = ['flutterwave_payment_method_id', 'created_at']


class CardCreateSerializer(serializers.Serializer):
    card_number = serializers.CharField(max_length=255)
    cvv = serializers.CharField(max_length=255)
    expiry_month = serializers.CharField(max_length=255)
    expiry_year = serializers.CharField(max_length=255)
    nonce = serializers.CharField(max_length=12, required=True)



class PaymentMethodResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = PaymentMethodSerializer()


class PaymentMethodListResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = PaymentMethodSerializer(many=True)

class ChargeAuthorizationSerializer(serializers.Serializer):
    charge_id = serializers.CharField(max_length=255)
    mode = serializers.ChoiceField(choices=['pin', 'otp'])
    pin = serializers.CharField(max_length=255, required=False, allow_blank=True)
    otp = serializers.CharField(max_length=10, required=False, allow_blank=True)
    nonce = serializers.CharField(max_length=12, required=True)

    def validate(self, attrs):
        if attrs.get('mode') == 'pin' and not attrs.get('pin'):
            raise serializers.ValidationError({"pin": "PIN is required when mode is pin."})
        if attrs.get('mode') == 'otp' and not attrs.get('otp'):
            raise serializers.ValidationError({"otp": "OTP is required when mode is otp."})
        return attrs


class TransactionSerializer(serializers.ModelSerializer):
    payment_method = PaymentMethodSerializer(read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'flutterwave_charge_id', 'reference', 'amount', 
            'currency', 'status', 'payment_method', 'created_at'
        ]
        read_only_fields = fields


class TransactionListResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    data = TransactionSerializer(many=True)
